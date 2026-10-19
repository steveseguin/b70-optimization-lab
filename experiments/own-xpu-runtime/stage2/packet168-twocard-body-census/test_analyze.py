import copy,json,tempfile,unittest
from pathlib import Path
from census_contract import *
from analyze import analyze,write_report

def fixture():
    rows=[]
    for v in ORDER:
        for i in IDS:
            if v in CONTROLS:
                row=dict(view=v,prompt_id=i,tokens=read(P/'lineage/oracle128'/(i+'.json'))['tokens'][:32],
                  arithmetic=ARITHMETIC,cached_tokens=0,full_reset=True,repairs_complete=True,
                  interval_ms={'C0':17.,'C1':17.01,'C2':17.02}[v])
            else:
                row=dict(view=v,prompt_id=i,interval_ms=16.-CLASSES.index(v)*.05,
                  diagnostic_only=True,reported_tokens=0,snapshot_restored=True,repair_exact=True,
                  same_verified_schedule=True,class_coverage_complete=True,replacement_cost_included=True,
                  control_shape_sha256='0'*64,arm_shape_sha256='0'*64,control_token_count=32,arm_token_count=32,
                  restore_sensor_checks=6)
            rows.append(row)
    return dict(schema='packet168.census.v1',diagnostic_only=True,model_loads=1,order=list(ORDER),
      engine_identity='packet136-bundle8',measurement_scope='matched_native_emission_interval',observations=rows)

class Tests(unittest.TestCase):
    def test_valid_synthetic(self):
        r=analyze(fixture());self.assertTrue(r['passed']);self.assertEqual(len(r['ranked']),9)
        self.assertAlmostEqual(r['ranked'][0]['control_spread_ms'],.02)
        self.assertEqual(len(r['top_two_conditional_ceilings']),2)
    def test_refusals(self):
        for field,value in [('snapshot_restored',False),('repair_exact',False),('same_verified_schedule',False),
          ('class_coverage_complete',False),('replacement_cost_included',False),('reported_tokens',1),
          ('arm_shape_sha256','1'*64),('restore_sensor_checks',0),('interval_ms',float('nan'))]:
            doc=fixture();next(r for r in doc['observations'] if r['view']=='attention')[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):analyze(doc)
    def test_control_oracle(self):
        d=fixture();d['observations'][0]['tokens'][0]^=1
        with self.assertRaises(ValueError):analyze(d)
    def test_control_drift(self):
        d=fixture()
        for r in d['observations']:
            if r['view']=='C0':r['interval_ms']=20
        with self.assertRaisesRegex(ValueError,'drift'):analyze(d)
    def test_missing_duplicate_and_scope(self):
        for action in ('missing','duplicate','isolated'):
            d=fixture()
            if action=='missing':d['observations'].pop()
            if action=='duplicate':d['observations'].append(d['observations'][0])
            if action=='isolated':d['measurement_scope']='isolated_B_replay'
            with self.subTest(action=action),self.assertRaises(ValueError):analyze(d)
    def test_failed_output_has_no_rank(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture();d['observations'].pop();r=write_report(d,t)
            self.assertEqual(r['ranked'],[]);self.assertEqual(r['top_two_conditional_ceilings'],[])
            self.assertNotIn('| attention |',(Path(t)/'CENSUS.md').read_text())
if __name__=='__main__':unittest.main()
