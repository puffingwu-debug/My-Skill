import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

SCRIPT = Path(__file__).resolve().with_name('estimate_energy.py')
spec = importlib.util.spec_from_file_location('energy', SCRIPT)
energy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(energy)


def face(name='A', n=25, azimuth=180):
    return {'id': name, 'name': name, 'tilt_deg': 30, 'azimuth_deg': azimuth,
            'tiles': [{'id': str(i), 'kind': 'pv'} for i in range(n)] + [{'id': '配瓦', 'kind': 'accessory'}]}


def payload(value=100):
    return {'inputs': {'meteo_data': {'radiation_db': 'test-fixture'}},
            'outputs': {'monthly': {'fixed': [{'month': i, 'E_m': value} for i in range(1, 13)]},
                        'totals': {'fixed': {'E_y': 12 * value}}}}


class EnergyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.pvgis = {'location': {'latitude': 31.78, 'longitude': 119.97}, 'energy': {'method': 'pvgis'}}
        self.offline = {'energy': {'method': 'specific_yield', 'annual_specific_yield_kwh_kwp': 1000,
                                   'source': '演示假设，非真实气象'}}

    def run_estimate(self, project, faces):
        result = energy.estimate(project, {'faces': faces, 'power_kwp': 99999}, self.out)
        self.assertEqual(result, json.loads((self.out / 'energy.json').read_text()))
        return result

    def test_net_specific_yield_and_unique_face_count(self):
        self.offline['energy'].update(system_loss_pct=14, additional_shading_loss_pct=10)
        result = self.run_estimate(self.offline, [face('A', 3), face('B', 2)])
        self.assertEqual(result['totals']['power_kwp'], .2)
        self.assertEqual(result['totals']['pv_tiles'], 5)
        self.assertEqual(result['totals']['annual_kwh'], 158.4)
        self.assertIsNone(result['totals']['monthly_kwh'])
        self.assertFalse(result['assumptions']['system_loss_applied'])

    def test_monthly_yearly_consistency_and_small_values(self):
        self.offline['energy']['monthly_fractions'] = [1 / 12] * 12
        for specific_yield in [.0, .07, 1000.03]:
            self.offline['energy']['annual_specific_yield_kwh_kwp'] = specific_yield
            r = self.run_estimate(self.offline, [face()])
            vals = [v['energy_kwh'] for v in r['totals']['monthly_kwh']]
            self.assertTrue(all(v >= 0 for v in vals))
            self.assertAlmostEqual(sum(vals), r['totals']['annual_kwh'], places=8)

    def test_invalid_month_fractions(self):
        for fractions in ([.1] * 12, [1] * 11, [float('nan')] * 12, [-1] + [2 / 11] * 11):
            self.offline['energy']['monthly_fractions'] = fractions
            r = self.run_estimate(self.offline, [face()])
            self.assertEqual(r['status'], 'failed')
            self.assertIsNone(r['totals']['annual_kwh'])

    def test_missing_source_or_yield_rejected(self):
        for key in ('source', 'annual_specific_yield_kwh_kwp'):
            p = copy.deepcopy(self.offline)
            del p['energy'][key]
            self.assertEqual(self.run_estimate(p, [face()])['status'], 'failed')

    def test_no_pv_needs_no_coordinates_or_angles(self):
        with patch.object(energy, '_fetch') as fetch:
            r = self.run_estimate({'energy': {'method': 'pvgis'}}, [{'id': 'A', 'tiles': []}])
            self.assertEqual(r['status'], 'no_pv')
            self.assertEqual(r['totals']['annual_kwh'], 0)
            self.assertEqual(len(r['totals']['monthly_kwh']), 12)
            fetch.assert_not_called()

    def test_missing_method_does_not_invent_estimate(self):
        with patch.object(energy, '_fetch') as fetch:
            r = self.run_estimate({}, [face()])
            self.assertEqual(r['status'], 'not_requested')
            self.assertIsNone(r['totals']['annual_kwh'])
            fetch.assert_not_called()

    def test_duplicate_face_or_tile_ids_rejected(self):
        for faces in ([face(), face()], [{'id': 'A', 'tiles': [{'id': '1', 'kind': 'pv'}, {'id': '1', 'kind': 'pv'}]}]):
            r = self.run_estimate(self.offline, faces)
            self.assertEqual(r['status'], 'failed')
            self.assertIsNone(r['totals'])

    def test_cardinal_aspect_and_shading_once(self):
        self.pvgis['energy']['additional_shading_loss_pct'] = 10
        with patch.object(energy, '_fetch', return_value=(payload(), {})) as fetch:
            r = self.run_estimate(self.pvgis, [face(str(i), 25, i) for i in (0, 90, 180, 270, 360)])
            self.assertEqual([c.args[0]['aspect'] for c in fetch.call_args_list], [-180, -90, 0, 90, -180])
            self.assertTrue(all(c.args[0]['mountingplace'] == 'building' for c in fetch.call_args_list))
            self.assertEqual(r['totals']['annual_kwh'], 4752)
            self.assertAlmostEqual(sum(m['energy_kwh'] for m in r['totals']['monthly_kwh']), r['totals']['annual_kwh'])

    def test_partial_failure_has_null_project_total(self):
        with patch.object(energy, '_fetch', side_effect=[(payload(), {}), RuntimeError('offline')]):
            r = self.run_estimate(self.pvgis, [face('A'), face('B')])
            self.assertEqual(r['status'], 'partial')
            self.assertIsNone(r['totals']['annual_kwh'])
            self.assertIsNone(r['totals']['monthly_kwh'])
            self.assertEqual(r['totals']['successful_subtotal_annual_kwh'], 1056)
            self.assertEqual(r['totals']['failed_faces'], ['B'])

    def test_api_zero_is_valid_but_warned(self):
        with patch.object(energy, '_fetch', return_value=(payload(0), {})):
            r = self.run_estimate(self.pvgis, [face()])
            self.assertEqual(r['status'], 'complete')
            self.assertEqual(r['totals']['annual_kwh'], 0)
            self.assertTrue(r['faces'][0]['warnings'])

    def test_bad_api_months_or_totals_rejected(self):
        duplicate, negative, mismatch, missing = [payload() for _ in range(4)]
        duplicate['outputs']['monthly']['fixed'][0]['month'] = 2
        negative['outputs']['monthly']['fixed'][0]['E_m'] = -1
        mismatch['outputs']['totals']['fixed']['E_y'] = 2400
        del missing['outputs']['monthly']
        for fixture in (duplicate, negative, mismatch, missing, None):
            with patch.object(energy, '_fetch', return_value=(fixture, {})):
                r = self.run_estimate(self.pvgis, [face()])
                self.assertEqual(r['status'], 'failed')
                self.assertIsNone(r['totals']['annual_kwh'])

    def test_http_failure_saves_evidence_and_never_falls_back(self):
        self.pvgis['energy'].update(annual_specific_yield_kwh_kwp=1000, source='演示假设')
        error = HTTPError('https://example.invalid', 503, 'test failure', None, io.BytesIO(b'test unavailable'))
        with patch.object(energy, 'urlopen', side_effect=error):
            r = self.run_estimate(self.pvgis, [face()])
            self.assertEqual(r['status'], 'failed')
            self.assertIsNone(r['totals']['annual_kwh'])
            provenance = r['faces'][0]['provenance']
            self.assertEqual((self.out / provenance['response_file']).read_bytes(), b'test unavailable')
            record = json.loads((self.out / provenance['request_file']).read_text())
            self.assertEqual(record['http_status'], 503)

    def test_network_failure_has_request_and_no_response(self):
        with patch.object(energy, 'urlopen', side_effect=URLError('offline')):
            r = self.run_estimate(self.pvgis, [face()])
            self.assertEqual(r['status'], 'failed')
            provenance = r['faces'][0]['provenance']
            self.assertIsNone(provenance['response_file'])
            self.assertTrue((self.out / provenance['request_file']).exists())

    def test_missing_azimuth_is_not_guessed(self):
        f = face()
        del f['azimuth_deg']
        with patch.object(energy, '_fetch') as fetch:
            self.assertEqual(self.run_estimate(self.pvgis, [f])['status'], 'failed')
            fetch.assert_not_called()

    def test_cli_offline(self):
        p = self.out / 'project.json'
        l = self.out / 'layout.json'
        p.write_text(json.dumps(self.offline))
        l.write_text(json.dumps({'faces': [face()]}))
        run = subprocess.run([sys.executable, str(SCRIPT), '--project', str(p), '--layout', str(l), '--output', str(self.out / 'cli')], text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['totals']['annual_kwh'], 880)

    def test_factor_all_months_and_faces_preserves_sources_and_capacity(self):
        fixture = payload()
        source = copy.deepcopy(fixture)
        with patch.object(energy, '_fetch', return_value=(fixture, {})) as fetch:
            result = self.run_estimate(self.pvgis, [face('A'), face('B')])
        self.assertEqual(fixture, source)
        self.assertEqual([c.args[0]['peakpower'] for c in fetch.call_args_list], [1, 1])
        self.assertEqual(result['totals']['power_kwp'], 2)
        self.assertEqual(result['totals']['annual_kwh'], 2112)
        self.assertEqual(result['assumptions']['generation_factor'], .88)
        self.assertTrue(all(m['energy_kwh'] == 176 for m in result['totals']['monthly_kwh']))
        for f in result['faces']:
            self.assertEqual(f['source_annual_kwh'],1200)
            self.assertEqual(f['before_generation_factor']['annual_kwh'],1200)
            self.assertEqual(f['annual_kwh'],1056)
            self.assertTrue(all(m['energy_kwh']==88 for m in f['monthly_kwh']))

    def test_factor_balanced_rounding_and_no_double_application(self):
        values = [358.75,329.12,427.65,435.62,416.37,349.27,371.29,390.06,348.74,379.23,327.79,364.10]
        f = {'annual_kwh':4497.99,'monthly_kwh':[{'month':i+1,'energy_kwh':v} for i,v in enumerate(values)]}
        energy._apply_generation_factor(f)
        self.assertEqual(f['annual_kwh'],3958.23)
        self.assertAlmostEqual(sum(m['energy_kwh'] for m in f['monthly_kwh']),3958.23)
        for old,new in zip(values,f['monthly_kwh']):
            self.assertLessEqual(abs(new['energy_kwh']-old*.88),.01)
        snapshot = copy.deepcopy(f)
        energy._apply_generation_factor(f)
        self.assertEqual(f,snapshot)

    def test_repeated_estimate_uses_original_input_not_previous_output(self):
        self.offline['energy']['monthly_fractions'] = [1/12]*12
        first = self.run_estimate(self.offline,[face()])
        second = self.run_estimate(self.offline,[face()])
        self.assertEqual(first['totals'],second['totals'])
        self.assertEqual(second['totals']['annual_kwh'],880)
        self.assertAlmostEqual(sum(m['energy_kwh'] for m in second['totals']['monthly_kwh']),880)
        self.assertEqual(second['faces'][0]['annual_specific_yield_kwh_kwp'],1000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
