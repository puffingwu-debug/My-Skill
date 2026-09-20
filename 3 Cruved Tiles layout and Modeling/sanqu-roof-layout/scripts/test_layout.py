"""Geometric and quantity invariants, independent of render appearance."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union
import ezdxf
from layout_engine import calculate, world
from deliverables import drawings, report

ROOT = Path(__file__).resolve().parents[1]


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.project = json.loads((ROOT/'references/example-project.json').read_text())

    def test_current_product_and_owner_regions(self):
        result = calculate(self.project)
        total = sum(t['kind']=='pv' for f in result['faces'] for t in f['tiles'])
        self.assertEqual(result['summary']['capacity_kwp'], total*.04)
        self.assertEqual(result['summary']['j_clip_count'], total*2)
        self.assertEqual(result['faces'][1]['pv_count'],0)
        f = result['faces'][0]
        first = [t for t in f['tiles'] if t['row']==0]
        starts = [min(p[0] for p in tile['footprint']) for tile in first]
        self.assertAlmostEqual(starts[1]-starts[0], .713)
        self.assertEqual(result['edges'][0]['effective_length_m'],.713)

    def test_complete_pv_avoids_holes_and_reserves(self):
        result = calculate(self.project)
        for f in result['faces']:
            allowed = unary_union([Polygon(p) for p in f['pv_regions']])
            for o in f.get('obstacles',[]):
                allowed = allowed.difference(Polygon(o['polygon']).buffer(o['clearance_m'],join_style=2))
            for tile in f['tiles']:
                if tile['kind']=='pv':
                    footprint = Polygon(tile['footprint'])
                    self.assertTrue(allowed.buffer(1e-8).covers(footprint))
                    self.assertAlmostEqual(footprint.area,.723*.5)

    def test_concave_roof_and_enclosed_hole_coverage(self):
        p=copy.deepcopy(self.project);p['faces']=p['faces'][:1];f=p['faces'][0]
        f['boundary']=[[0,0],[4,0],[4,2],[3,2],[3,3],[0,3]]
        f['pv_regions']=[f['boundary']];f['obstacles']=[]
        f['holes']=[[[1.45,1.05],[1.55,1.05],[1.55,1.15],[1.45,1.15]]]
        result=calculate(p)['faces'][0]
        roof=Polygon(f['boundary'],f['holes'])
        installed=unary_union([Polygon(part['outer'],part['holes']) for t in result['tiles'] for part in t['parts']])
        self.assertLess(roof.symmetric_difference(installed).area,1e-7)
        for t in result['tiles']:
            if t['kind']=='pv': self.assertTrue(roof.covers(Polygon(t['footprint'])))

    def test_no_cutting_or_spares_in_capacity(self):
        p=copy.deepcopy(self.project);base=calculate(p);p['spare_pct']=5;more=calculate(p)
        self.assertEqual(base['summary']['capacity_kwp'],more['summary']['capacity_kwp'])
        self.assertGreater(more['quantities'][0]['purchase_quantity'],more['quantities'][0]['quantity'])
        self.assertFalse(any('cut' in k for k in more['summary']))

    def test_shared_ridge_not_double_counted(self):
        p=copy.deepcopy(self.project);duplicate=dict(p['edges'][0],id='R2');p['edges'].append(duplicate)
        with self.assertRaises(ValueError): calculate(p)

    def test_reject_unconfirmed_legacy_inputs(self):
        for key,value in [('units','mm'),('power_w',45),('lateral_pitch_m',.7),('course_pitch_m',.413)]:
            p=copy.deepcopy(self.project);p[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): calculate(p)
        p=copy.deepcopy(self.project);del p['faces'][0]['pv_regions']
        with self.assertRaises(ValueError): calculate(p)

    def test_north_south_share_world_ridge(self):
        result=calculate(self.project);s,n=result['faces']
        for i in range(3): self.assertAlmostEqual(world(s,[0,4.55])[i],world(n,[8.4,4.55])[i])

    def test_valid_vector_and_cad_output(self):
        result=calculate(self.project)
        with tempfile.TemporaryDirectory() as tmp:
            drawings(result,tmp)
            for path in Path(tmp).glob('*.svg'): ET.parse(path)
            doc=ezdxf.readfile(Path(tmp)/'屋面总平面排布.dxf')
            self.assertEqual(doc.units,6)
            self.assertEqual(len(doc.modelspace().query('LWPOLYLINE[layer=="PV"]')),result['summary']['pv_count'])

    def test_report_inline_javascript_is_valid(self):
        node = shutil.which('node')
        if not node: self.skipTest('Node未安装，需浏览器核验页面')
        project=copy.deepcopy(self.project)
        project['project_name']='验证 "引号" 与换行\n及中文'
        result=calculate(project)
        energy={'status':'complete','method':'specific_yield','totals':{'annual_kwh':1000,'monthly_kwh':None},
                'assumptions':{'system_loss_applied':False},'limitations':['第一行\n第二行']}
        with tempfile.TemporaryDirectory() as tmp:
            report(project,result,energy,tmp,ROOT/'assets')
            page=(Path(tmp)/'屋面排布报告.html').read_text()
            script=page.split('<script>')[1].split('</script>')[0]
            checked=subprocess.run([node,'--check'],input=script,text=True,capture_output=True)
            self.assertEqual(checked.returncode,0,checked.stderr)


if __name__ == '__main__': unittest.main()
