"""Physical dimensions, stagger, region ownership, cuttable blanks and quantities."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union
from layout_engine import calculate, world

ROOT=Path(__file__).resolve().parents[1]


class ProLayoutTests(unittest.TestCase):
    def setUp(self):
        self.p=json.loads((ROOT/'references/example-project.json').read_text())

    def test_confirmed_four_by_seven(self):
        d=calculate(self.p);f=d['faces'][0]
        self.assertEqual(d['summary']['pv_count'],25)
        self.assertEqual(d['summary']['companion_half_count'],6)
        self.assertEqual(d['summary']['companion_full_count'],0)
        self.assertEqual(d['summary']['capacity_kwp'],1.75)
        for r in range(7):
            row=[t for t in f['tiles'] if t['row']==r]
            self.assertEqual(len(row),4 if r%2==0 else 5)
            self.assertEqual([t['kind'] for t in row],['pv']*4 if r%2==0 else ['companion']+['pv']*3+['companion'])
        a,b=[t for t in f['tiles'] if t['row']==0][:2]
        self.assertAlmostEqual(Polygon(a['footprint']).intersection(Polygon(b['footprint'])).area,.020*.390)

    def test_stagger_and_course_pitch(self):
        f=calculate(self.p)['faces'][0]
        a=next(t for t in f['tiles'] if t['row']==0)
        b=next(t for t in f['tiles'] if t['row']==1)
        self.assertAlmostEqual(a['virtual_center'][0]-b['virtual_center'][0],.610)
        self.assertAlmostEqual(b['center'][1]-a['center'][1],.340)

    def test_only_full_pv_and_clipped_companions(self):
        f=self.p['faces'][0]
        f['boundary']=[[0,0],[4.8,0],[3.9,2.3],[0,2.3]]
        f['pv_regions']=[f['boundary']]
        f['obstacles']=[{'id':'SK1','polygon':[[2,.7],[2.5,.7],[2.5,1.1],[2,1.1]],'clearance_m':.1}]
        r=calculate(self.p)['faces'][0]
        allowed=Polygon(f['boundary']).difference(Polygon(f['obstacles'][0]['polygon']).buffer(.1,join_style=2))
        for tile in r['tiles']:
            if tile['kind']=='pv':
                self.assertTrue(allowed.buffer(1e-8).covers(Polygon(tile['footprint'])))
                self.assertAlmostEqual(Polygon(tile['footprint']).area,1.24*.39)
                self.assertEqual(tile['power_w'],70)
            else:
                self.assertIn(tile['stock_type'],['full','half'])
                self.assertEqual(tile['power_w'],0)
        self.assertLess(r['coverage_difference_m2'],1e-8)

    def test_reserve_is_not_filled_with_main_tiles(self):
        f=self.p['faces'][0];f['tile_regions']=[[[.065,0],[4.835,0],[4.835,2.43],[.065,2.43]]]
        d=calculate(self.p)['faces'][0]
        for t in d['tiles']:
            for part in t['parts']:
                self.assertGreaterEqual(Polygon(part['outer']).bounds[0],.065-1e-8)
                self.assertLessEqual(Polygon(part['outer']).bounds[2],4.835+1e-8)
        self.assertAlmostEqual(d['trim_reserved_area_m2'],.13*2.43)

    def test_strict_slope_and_developed_coordinates(self):
        for slope in [0,12]:
            p=copy.deepcopy(self.p);p['faces'][0]['tilt_deg']=slope
            with self.assertRaises(ValueError):calculate(p)
        self.p['faces'][0]['tilt_deg']=12.001
        calculate(self.p)
        self.p['faces'][0]['coordinate_space']='projected'
        with self.assertRaises(ValueError):calculate(self.p)

    def test_same_unfolded_size_different_projected_size(self):
        a=calculate(self.p)['faces'][0];self.p['faces'][0]['tilt_deg']=45
        b=calculate(self.p)['faces'][0]
        self.assertEqual(a['pv_count'],b['pv_count'])
        self.assertAlmostEqual(world(b,[0,2.43])[1],2.43/math.sqrt(2))
        self.assertAlmostEqual(b['area_m2'],4.9*2.43)

    def test_owner_regions_and_spares_do_not_generate(self):
        a=calculate(self.p)
        self.p['spare_pct']=10;b=calculate(self.p)
        self.assertEqual(a['summary']['capacity_kwp'],b['summary']['capacity_kwp'])
        self.p['faces'][0]['pv_regions']=[]
        c=calculate(self.p)
        self.assertEqual(c['summary']['pv_count'],0)
        self.assertEqual(c['summary']['capacity_kwp'],0)

    def test_shared_edges_once_and_unconfirmed_length(self):
        self.p['edges']=[{'id':'R1','type':'ridge','start':[0,1,4],'end':[5,1,4]}]
        d=calculate(self.p);self.assertIsNone(d['edges'][0]['count'])
        self.p['edges'].append(dict(self.p['edges'][0],id='R2'))
        with self.assertRaises(ValueError):calculate(self.p)

    def test_reject_other_products(self):
        for k,v in [('power_w',40),('lateral_pitch_m',.713),('course_pitch_m',.405),('units','mm')]:
            p=copy.deepcopy(self.p);p[k]=v
            with self.subTest(key=k),self.assertRaises(ValueError):calculate(p)


if __name__=='__main__':unittest.main()
