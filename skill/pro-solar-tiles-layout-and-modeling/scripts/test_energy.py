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
            'tiles': [{'id': str(i), 'kind': 'pv'} for i in range(n)] + [{'id': '配瓦', 'kind': 'companion', 'stock_type': 'half'}]}


def payload(value=100):
    return {'inputs': {'meteo_data': {'radiation_db': 'test-fixture'}, 'pv_module': {'system_loss':0}},
            'outputs': {'monthly': {'fixed': [{'month': i, 'E_m': value} for i in range(1, 13)]},
                        'totals': {'fixed': {'E_y': 12 * value}}}}


class EnergyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.pvgis = {'location': {'latitude': 31.78, 'longitude': 119.97}, 'energy': {'method': 'pvgis'}}
        self.offline = {'energy': {'method': 'specific_yield', 'annual_specific_yield_kwh_kwp': 1000,
                                   'specific_yield_basis': 'before_system_losses',
                                   'source': '演示假设，非真实气象'}}

    def run_estimate(self, project, faces):
        result = energy.estimate(project, {'faces': faces, 'power_kwp': 99999}, self.out)
        self.assertEqual(result, json.loads((self.out / 'energy.json').read_text()))
        return result

    def test_baseline_specific_yield_and_unique_face_count(self):
        self.offline['energy'].update(system_loss_pct=12, additional_shading_loss_pct=10)
        result = self.run_estimate(self.offline, [face('A', 3), face('B', 2)])
        self.assertEqual(result['totals']['power_kwp'], .35)
        self.assertEqual(result['totals']['pv_tiles'], 5)
        self.assertEqual(result['totals']['annual_kwh'], 277.2)
        self.assertIsNone(result['totals']['monthly_kwh'])
        self.assertTrue(result['assumptions']['system_loss_applied'])

    def test_old_loss_and_conflicting_efficiency_rejected(self):
        for fields in ({'system_loss_pct':14}, {'system_efficiency':.86}):
            project = copy.deepcopy(self.pvgis)
            project['energy'].update(fields)
            with patch.object(energy, '_fetch') as fetch:
                self.assertEqual(self.run_estimate(project,[face()])['status'],'failed')
                fetch.assert_not_called()

    def test_net_or_undeclared_specific_yield_rejected(self):
        for basis in (None,'net_after_source_system_losses'):
            project = copy.deepcopy(self.offline)
            project['energy']['specific_yield_basis'] = basis
            self.assertEqual(self.run_estimate(project,[face()])['status'],'failed')

    def test_pvgis_efficiency_once_and_annual_rounding(self):
        fixture = payload(100.03)
        fixture['outputs']['totals']['fixed']['E_y'] = 1200.4
        with patch.object(energy, '_fetch', return_value=(fixture, {})) as fetch:
            result = self.run_estimate(self.pvgis, [face()])
            self.assertEqual(fetch.call_args.args[0]['loss'], 0)
            self.assertEqual(result['faces'][0]['baseline_annual_kwh'],1200.4)
            self.assertEqual(result['totals']['annual_kwh'],1056.35)
            self.assertAlmostEqual(sum(v['energy_kwh'] for v in result['totals']['monthly_kwh']),1056.35)

    def test_pvgis_rejects_already_derated_or_missing_loss_response(self):
        for module in ({'system_loss':14},{}):
            fixture = payload()
            fixture['inputs']['pv_module'] = module
            with patch.object(energy, '_fetch', return_value=(fixture, {})):
                self.assertEqual(self.run_estimate(self.pvgis,[face()])['status'],'failed')

    def test_positive_annual_without_month_weights_rejected(self):
        fixture = payload(0)
        fixture['outputs']['totals']['fixed']['E_y'] = .01
        with patch.object(energy, '_fetch', return_value=(fixture, {})):
            self.assertEqual(self.run_estimate(self.pvgis,[face()])['status'],'failed')

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
            self.assertTrue(all(c.args[0]['loss'] == 0 for c in fetch.call_args_list))
            self.assertAlmostEqual(r['totals']['annual_kwh'], 1200 * .88 * .9 * 5)
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

    def test_missing_coordinates_never_substituted(self):
        with patch.object(energy, '_fetch') as fetch:
            r = self.run_estimate({'energy': {'method': 'pvgis'}}, [face()])
            self.assertEqual(r['status'], 'failed')
            self.assertIsNone(r['totals']['annual_kwh'])
            fetch.assert_not_called()

    def test_no_half_generating_tile_or_unknown_kind(self):
        for tile in ({'kind': 'pv', 'stock_type': 'half'}, {'kind': 'accessory'}):
            r = self.run_estimate(self.offline, [{'id': 'A', 'tiles': [tile]}])
            self.assertEqual(r['status'], 'failed')
            self.assertIsNone(r['totals'])

    def test_pro_minimum_slope(self):
        for angle in (0, 12):
            f = face()
            f['tilt_deg'] = angle
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
        self.assertEqual(json.loads(run.stdout)['totals']['annual_kwh'], 1540)


if __name__ == '__main__':
    unittest.main(verbosity=2)
