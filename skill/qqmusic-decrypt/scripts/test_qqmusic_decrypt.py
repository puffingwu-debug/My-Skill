# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline regression checks; fixtures are generated tones, never user songs or keys."""

import contextlib
import io
import json
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import qmc_crypto as crypto
import qqmusic_decrypt as app


def wrapped(audio, extension='.mflac'):
    meta = bytearray(176)
    for start, value in [(12, 'fixtureMID'), (72, 'F0M0fixtureMID' + extension)]:
        text = value.encode('utf-16le')
        meta[start:start + len(text)] = text
    return audio + meta + struct.pack('<II', 192, 1) + b'musicex\0'


class ProtocolTests(unittest.TestCase):
    def test_known_tea_answer(self):
        ekey = 'VGhpcyBpcyBHFWEh4cjZ1Vi7rJ56XeoPlqGM1sxBGPg7mt89umKclFBr9iqfmFdS'
        self.assertEqual(crypto.parse_key(ekey), b'This is a test key for test purpose :D')

    def test_known_map_answer(self):
        self.assertEqual(crypto.decrypt(bytes(16), b'ABCDEFGHIJKLMNOP'),
                         bytes.fromhex('3f8ac1493f49c18a3f8ac1493f49c18a'))

    def test_legacy_and_invalid_version_rejected(self):
        for data in [bytes(200) + b'QTag', wrapped(b'a')[:-12] + struct.pack('<I', 2) + b'musicex\0']:
            with self.assertRaises(ValueError):
                app.parse_footer(data)

    def test_footer_and_utf16(self):
        meta = app.parse_footer(wrapped(b'fake-payload'))
        self.assertEqual(meta['media_mid'], 'fixtureMID')
        self.assertEqual(meta['resource'], 'F0M0fixtureMID.mflac')
        self.assertEqual(meta['footer_size'], 192)

    def test_archived_credentials_without_logging(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'prefs.plist'
            archive = {'$objects': ['$null', {'strUserAccount': plistlib.UID(2),
                       'strAuthst': plistlib.UID(3)}, 'fixture-account', 'fixture-secret']}
            p.write_bytes(plistlib.dumps({'AutoLoginUserInfo': plistlib.dumps(archive, fmt=plistlib.FMT_BINARY)}))
            with patch.object(app, 'PREFERENCES', p), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(app.credentials(), ('fixture-account', 'fixture-secret'))
            self.assertEqual(output.getvalue(), '')

    def test_api_denial_stops_and_does_not_expose_token(self):
        response = io.BytesIO(json.dumps({'code': 0, 'req_1': {'code': 0, 'data': {
            'midurlinfo': [{'result': 104005, 'ekey': ''}]}}}).encode())
        with patch.object(app, 'credentials', return_value=('fixture-account', 'fixture-secret')):
            with patch.object(app.urllib.request, 'build_opener') as opener:
                opener.return_value.open.return_value = response
                with self.assertRaises(ValueError) as caught:
                    app.fetch_key(app.parse_footer(wrapped(b'fake')))
                self.assertIn('104005', str(caught.exception))
                self.assertNotIn('fixture-secret', str(caught.exception))
                self.assertEqual(opener.return_value.open.call_count, 1)


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
class AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        native = Path(cls.temp.name) / 'fixture.flac'
        subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=440:sample_rate=44100:duration=0.2', '-ac', '2',
                        '-c:a', 'flac', str(native)], check=True)
        cls.audio = native.read_bytes()
        cls.key = bytes(range(256)) * 2

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def make_source(self, folder, audio=None):
        source = Path(folder) / '测试歌.mflac'
        source.write_bytes(wrapped(crypto.decrypt(self.audio if audio is None else audio, self.key)))
        return source

    def test_complete_offline_decryption_and_mp3(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.make_source(folder)
            before = source.read_bytes()
            out = Path(folder) / 'result'
            with patch.object(app, 'fetch_key', return_value=self.key):
                result = app.convert_one(source, out, 'both')
            self.assertTrue(result['flac_md5_verified'])
            self.assertTrue(result['full_decode_verified'])
            self.assertEqual(result['flac_samples'], 8820)
            self.assertEqual((out / '测试歌.flac').read_bytes(), self.audio)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(len(list(out.iterdir())), 2)

    def test_existing_output_never_overwritten_or_key_requested(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.make_source(folder)
            target = Path(folder) / '测试歌.mp3'
            target.write_bytes(b'existing-output')
            with patch.object(app, 'fetch_key') as fetch:
                with self.assertRaises(ValueError):
                    app.convert_one(source, Path(folder), 'mp3')
                fetch.assert_not_called()
            self.assertEqual(target.read_bytes(), b'existing-output')

    def test_wrong_key_produces_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.make_source(folder)
            out = Path(folder) / 'result'
            with patch.object(app, 'fetch_key', return_value=bytes([255]) * 512):
                with self.assertRaises(ValueError):
                    app.convert_one(source, out, 'both')
            self.assertFalse(out.exists())

    def test_corrupt_audio_is_not_published(self):
        with tempfile.TemporaryDirectory() as folder:
            damaged = bytearray(self.audio)
            damaged[-100] ^= 127
            source = self.make_source(folder, damaged)
            out = Path(folder) / 'result'
            with patch.object(app, 'fetch_key', return_value=self.key):
                with self.assertRaises(ValueError):
                    app.convert_one(source, out, 'both')
            self.assertEqual(list(out.iterdir()), [])

    def test_missing_md5_is_reported_honestly(self):
        with tempfile.TemporaryDirectory() as folder:
            data = bytearray(self.audio)
            data[26:42] = bytes(16)
            p = Path(folder) / 'no-md5.flac'
            p.write_bytes(data)
            result = app.validate_flac(p)
            self.assertFalse(result['flac_md5_verified'])
            self.assertEqual(result['trimmed_trailer_bytes'], 0)

    def test_truncated_audio_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'truncated.flac'
            p.write_bytes(self.audio[:-100])
            with self.assertRaises(ValueError):
                app.validate_flac(p)

    def test_batch_reports_failure_and_continues(self):
        with patch('sys.argv', ['qqmusic_decrypt.py', 'failed.mflac', 'next.mflac']):
            with patch.object(app, 'convert_one', side_effect=[ValueError('fixture-error'), {'status': 'ok'}]):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    status = app.main()
            lines = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(status, 1)
            self.assertEqual([line['status'] for line in lines], ['error', 'ok'])


if __name__ == '__main__':
    unittest.main()
