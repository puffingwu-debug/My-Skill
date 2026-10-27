#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Locally decrypt QQ Music musicex V1 files and verify audio before publishing."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import tempfile
import urllib.error
import urllib.request

from qmc_crypto import decrypt, parse_key

API = 'https://u.y.qq.com/cgi-bin/musicu.fcg'
PREFERENCES = Path.home() / 'Library/Containers/com.tencent.QQMusicMac/Data/Library/Preferences/com.tencent.QQMusicMac.plist'
EXTENSIONS = {'.mflac', '.mgg'}


def parse_footer(data):
    if len(data) < 16 or data[-8:] != b'musicex\0':
        raise ValueError('不支持：需要 musicex V1 尾部，旧 QMC/QTag/STag 不受支持')
    size, version = struct.unpack('<II', data[-16:-8])
    if version != 1 or size < 156 or size >= len(data):
        raise ValueError('musicex 尾部版本或长度无效')
    meta = data[-size:-16]
    mid = meta[12:72].decode('utf-16le').split('\0')[0]
    filename = meta[72:140].decode('utf-16le').split('\0')[0]
    extension = Path(filename).suffix.lower()
    if not mid or not filename or extension not in EXTENSIONS:
        raise ValueError('musicex 歌曲标识缺失或音频类型不受支持')
    return {'version': version, 'footer_size': size, 'media_mid': mid,
            'resource': filename, 'extension': '.flac' if extension == '.mflac' else '.ogg'}


def credentials():
    if not PREFERENCES.exists():
        raise ValueError('找不到 QQ 音乐偏好文件；请在本机 QQ 音乐中登录')
    outer = plistlib.loads(PREFERENCES.read_bytes())
    archive = outer.get('AutoLoginUserInfo')
    if not isinstance(archive, bytes):
        raise ValueError('QQ 音乐没有可用的自动登录状态；请重新登录')
    objects = plistlib.loads(archive).get('$objects', [])
    def resolve(value):
        return objects[value.data] if isinstance(value, plistlib.UID) else value
    for obj in objects:
        if isinstance(obj, dict) and 'strAuthst' in obj:
            auth = resolve(obj['strAuthst'])
            uin = resolve(obj.get('strUserAccount')) or obj.get('nCurrUseId')
            if auth and uin:
                return str(uin), auth
    raise ValueError('QQ 音乐登录字段缺失；请重新登录')


def fetch_key(meta):
    uin, auth = credentials()
    body = {'comm': {'authst': auth, 'ct': '19', 'cv': '1859', 'uin': uin, 'tmeLoginType': '3'},
            'req_1': {'module': 'music.vkey.GetEVkey', 'method': 'CgiGetEVkey', 'param': {
                'filename': [meta['resource']], 'guid': '10000', 'songmid': [meta['media_mid']],
                'songtype': [1], 'uin': uin, 'loginflag': 1, 'platform': '20', 'ctx': 1}}}
    request = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
        'Content-Type': 'application/json', 'Referer': 'https://y.qq.com/',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError('QQ 音乐接口发生重定向，已停止发送登录信息')
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise ValueError(f'QQ 音乐接口 HTTP {error.code}') from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError('无法连接 QQ 音乐接口；请检查网络后重试') from None
    req = payload.get('req_1', {})
    items = (req.get('data') or {}).get('midurlinfo') or []
    if payload.get('code') != 0 or req.get('code') != 0:
        raise ValueError(f'QQ 音乐接口拒绝：code={payload.get("code")}, req_1.code={req.get("code")}')
    if not items or items[0].get('result') != 0 or not items[0].get('ekey'):
        result = items[0].get('result') if items else 'missing'
        raise ValueError(f'QQ 音乐未返回歌曲密钥：result={result}；请确认登录状态与歌曲访问权限')
    return parse_key(items[0]['ekey'])


def pcm_check(path, sample_format):
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error',
                                    '-i', str(path), '-map', '0:a:0', '-f', sample_format, '-'],
                                   stdout=subprocess.PIPE, stderr=errors)
        digest, count = hashlib.md5(), 0
        with process.stdout:
            for chunk in iter(lambda: process.stdout.read(1024 * 1024), b''):
                digest.update(chunk)
                count += len(chunk)
        status = process.wait()
        errors.seek(0)
        clean = status == 0 and not errors.read()
    return digest.hexdigest(), count, clean


def strict_decode(path):
    result = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-xerror',
                             '-i', str(path), '-map', '0:a:0', '-f', 'null', '-'], capture_output=True)
    if result.returncode or result.stderr:
        raise ValueError('音频未通过全曲严格解码校验，不交付该输出')


def validate_flac(path):
    data = path.read_bytes()
    if len(data) < 42 or data[:4] != b'fLaC' or data[4] & 127 or data[5:8] != b'\0\0\x22':
        raise ValueError('FLAC STREAMINFO 无效')
    info = int.from_bytes(data[18:26], 'big')
    channels, bits, samples = ((info >> 41) & 7) + 1, ((info >> 36) & 31) + 1, info & ((1 << 36) - 1)
    width = (bits + 7) // 8
    sample_format = {1: 's8', 2: 's16le', 3: 's24le', 4: 's32le'}[width]
    expected = data[26:42].hex()
    has_md5 = data[26:42] != bytes(16)
    def matches(result):
        digest, count, _ = result
        return (not samples or count == samples * channels * width) and (not has_md5 or digest == expected)
    result = pcm_check(path, sample_format)
    if not matches(result):
        raise ValueError('解密后 FLAC 的样本数量或 PCM MD5 不符，不交付损坏音频')
    trimmed = 0
    if not result[2]:
        if not has_md5 or not samples:
            raise ValueError('FLAC 含解码错误且缺少完整校验依据，不自动修复')
        for trimmed in range(1, 17):
            path.write_bytes(data[:-trimmed])
            candidate = pcm_check(path, sample_format)
            if candidate[2] and matches(candidate):
                break
        else:
            raise ValueError('FLAC 尾部异常无法在完整性校验下修复')
    strict_decode(path)
    return {'flac_samples': samples, 'flac_md5_verified': has_md5, 'trimmed_trailer_bytes': trimmed}


def convert_one(source, output_dir, mode):
    original = source.read_bytes()
    sha = hashlib.sha256(original).hexdigest()
    meta = parse_footer(original)
    targets = []
    if mode in ('original', 'both'):
        targets.append(output_dir / (source.stem + meta['extension']))
    if mode in ('mp3', 'both'):
        targets.append(output_dir / (source.stem + '.mp3'))
    for target in targets:
        if target.exists():
            raise ValueError(f'输出已存在，未覆盖：{target}')
    key = fetch_key(meta)
    audio = decrypt(original[:-meta['footer_size']], key)
    del key
    magic = b'fLaC' if meta['extension'] == '.flac' else b'OggS'
    if not audio.startswith(magic):
        raise ValueError('解密后文件头不匹配，密钥或文件格式不兼容')
    output_dir.mkdir(parents=True, exist_ok=True)
    verification = {}
    with tempfile.TemporaryDirectory(prefix='.qqmusic-', dir=output_dir) as folder:
        work = Path(folder)
        native = work / ('audio' + meta['extension'])
        native.write_bytes(audio)
        if meta['extension'] == '.flac':
            verification = validate_flac(native)
        else:
            strict_decode(native)
        if mode in ('mp3', 'both'):
            result = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-xerror',
                '-n', '-i', str(native), '-map', '0:a:0', '-map_metadata', '0', '-c:a', 'libmp3lame',
                '-b:a', '320k', '-id3v2_version', '3', str(work / 'audio.mp3')], capture_output=True)
            if result.returncode or result.stderr:
                raise ValueError('MP3 转换失败，不交付该输出')
            strict_decode(work / 'audio.mp3')
        if hashlib.sha256(source.read_bytes()).hexdigest() != sha:
            raise ValueError('处理期间源文件发生变化，不交付此次输出')
        for target in targets:
            os.link(work / ('audio' + target.suffix), target)
    return {'status': 'ok', 'source': str(source), 'source_sha256': sha, 'source_unchanged': True,
            'outputs': [str(t) for t in targets], 'full_decode_verified': True, **verification}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path.cwd() / 'qqmusic-decoded')
    parser.add_argument('--format', choices=['mp3', 'original', 'both'], default='mp3')
    parser.add_argument('--recursive', action='store_true')
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    if not args.inspect and not shutil.which('ffmpeg'):
        parser.error('需要 FFmpeg；请先安装并确保 ffmpeg 可执行')
    paths = []
    for supplied in args.inputs:
        p = supplied.expanduser().resolve()
        if p.is_dir():
            files = p.rglob('*') if args.recursive else p.iterdir()
            paths.extend(sorted(f for f in files if f.is_file() and f.suffix.lower() in EXTENSIONS))
        else:
            paths.append(p)
    paths = list(dict.fromkeys(paths))
    if not paths:
        parser.error('未找到 .mflac 或 .mgg 文件')
    failed = False
    for p in paths:
        try:
            if args.inspect:
                result = {'status': 'inspected', 'source': str(p), **parse_footer(p.read_bytes())}
            else:
                result = convert_one(p, args.output_dir.expanduser().resolve(), args.format)
        except (OSError, ValueError, RuntimeError, plistlib.InvalidFileException) as error:
            failed = True
            result = {'status': 'error', 'source': str(p), 'error': str(error)}
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
