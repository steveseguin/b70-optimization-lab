import copy,json,tempfile,unittest
from pathlib import Path
from census_contract import *
from analyze import analyze,write_report

def oracle(i):return read(P/'lineage/oracle128'/(i+'.json'))['tokens'][:TOKENS]

def probes(cls,index,saving=.4):
    rows=[]
    for rank in (0,1):
        for k in range(REPEATS):
            rows.append(dict(schema='packet168.body-probe.v2',diagnostic_only=True,reported_tokens=0,rank=rank,
              arm=ARM_CODES[cls],prompt_index=index,repeat=k,control_ms=7.,arm_ms=7.-saving/2-CLASSES.index(cls)*.01,
              skipped_sites=24,restore_exact=True,repair_exact=True,route_identity_preserved=k!=1,
              class_coverage_complete=True,matched_native_emission_interval=False))
    return rows

def fixture():
    rows=[]
    for v in ORDER:
        for index,i in enumerate(IDS):
            if v in CONTROLS:
                rows.append(dict(view=v,prompt_id=i,tokens=oracle(i),arithmetic=ARITHMETIC,cached_tokens=0,
                  full_reset=True,repairs_complete=True,interval_ms={'C0':17.,'C1':17.01,'C2':17.02}[v]))
            else:
                rows.append(dict(view=v,prompt_id=i,tokens=oracle(i),diagnostic_only=True,reported_tokens=0,
                  setup_exact=True,arm_code=ARM_CODES[v],probes=probes(v,index)))
    return dict(schema='packet168.census.v2',diagnostic_only=True,model_loads=1,order=list(ORDER),
      report_classes=list(REPORT_CLASSES),engine_identity='packet136-bundle8',
      measurement_scope='native_exact_controls_plus_isolated_body_class_probes',
      tokens_per_request=TOKENS,repeats_per_probe=REPEATS,observations=rows)

def arm_row(d,cls='attention'):return next(r for r in d['observations'] if r['view']==cls)

class Tests(unittest.TestCase):
    def test_valid_synthetic(self):
        r=analyze(fixture());self.assertTrue(r['passed']);self.assertEqual(len(r['ranked']),6)
        self.assertEqual({x['kernel_class'] for x in r['ranked']},set(CLASSES))
        self.assertFalse(r['residual']['causally_isolated'])
        for v in CONTROLS:
            self.assertAlmostEqual(r['residual']['paired_control_residual_ms'][v],
              r['control_means_ms'][v]-sum(x['measured_marginal_ms_per_body_pass'] for x in r['ranked']))
        # Per-rank saving .2+.01*index, summed over two ranks.
        self.assertEqual(r['ranked'][0]['kernel_class'],'norms_glue')
        self.assertAlmostEqual(r['ranked'][0]['measured_marginal_ms_per_body_pass'],.5)
        self.assertEqual(r['ranked'][0]['route_identity_changed_probes'],24)
        self.assertEqual(len(r['top_two_conditional_ceilings']),2)
    def test_probe_refusals(self):
        for field,value in [('restore_exact',False),('repair_exact',False),('reported_tokens',1),('diagnostic_only',False),
          ('class_coverage_complete',False),('skipped_sites',0),('arm',9),('prompt_index',5),('schema','packet168.isolated-prototype.v1'),
          ('arm_ms',float('nan')),('control_ms',-1.),('route_identity_preserved',None)]:
            d=fixture();arm_row(d)['probes'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):analyze(d)
    def test_probe_coverage(self):
        d=fixture();arm_row(d)['probes'].pop()
        with self.assertRaises(ValueError):analyze(d)
        d=fixture();p=arm_row(d)['probes'];p[0],p[3]=p[3],p[0]
        with self.assertRaisesRegex(ValueError,'chronology'):analyze(d)
        d=fixture();arm_row(d)['setup_exact']=False
        with self.assertRaises(ValueError):analyze(d)
        d=fixture();arm_row(d)['tokens'][0]^=1
        with self.assertRaises(ValueError):analyze(d)
        d=fixture();arm_row(d)['arm_code']=3
        with self.assertRaises(ValueError):analyze(d)
    def test_control_oracle(self):
        d=fixture();d['observations'][0]['tokens'][0]^=1
        with self.assertRaises(ValueError):analyze(d)
        d=fixture();d['observations'][0]['tokens']=d['observations'][0]['tokens'][:40]
        with self.assertRaises(ValueError):analyze(d)
    def test_drift(self):
        d=fixture()
        for r in d['observations']:
            if r['view']=='C2':r['interval_ms']=17.3
        with self.assertRaisesRegex(ValueError,'drift'):analyze(d)
        d=fixture();next(r for r in d['observations'] if r['view']=='C1')['interval_ms']=18
        r=analyze(d);self.assertGreater(r['per_prompt_control_drift_max'],.05);self.assertLessEqual(r['control_drift'],.01)
    def test_scope_and_bounds(self):
        for key,value in [('measurement_scope','matched_native_emission_interval'),('model_loads',2),('tokens_per_request',32),
          ('repeats_per_probe',1),('schema','packet168.census.v1'),('engine_identity','other')]:
            d=fixture();d[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):analyze(d)
    def test_coverage_and_order(self):
        for mode in ('missing-residual','extra-class','residual-arm','reorder','missing-view','chronology'):
            d=fixture()
            if mode=='missing-residual':d['report_classes'].pop()
            elif mode=='extra-class':d['report_classes'].append('lm_head_argmax')
            elif mode=='residual-arm':d['observations'].append(dict(view='residual',prompt_id=IDS[0]))
            elif mode=='reorder':d['order'][1:3]=reversed(d['order'][1:3])
            elif mode=='missing-view':d['observations'].pop()
            else:d['observations'][12],d['observations'][13]=d['observations'][13],d['observations'][12]
            with self.subTest(mode=mode),self.assertRaises(ValueError):analyze(d)
    def test_negative_residual_is_not_clipped(self):
        d=fixture()
        for r in d['observations']:
            if r['view'] in CLASSES:
                for p in r['probes']:p['arm_ms']=p['control_ms']-3
        self.assertLess(analyze(d)['residual']['residual_ms_per_token'],0)
    def test_failed_report_has_no_ranking(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture();d['observations'].pop();r=write_report(d,t)
            self.assertEqual(r['ranked'],[]);self.assertEqual(r['top_two_conditional_ceilings'],[])
            self.assertNotIn('| attention |',(Path(t)/'CENSUS.md').read_text())
        with tempfile.TemporaryDirectory() as t:
            r=write_report(fixture(),t);self.assertTrue(r['passed'])
            self.assertIn('residual (not causally isolated)',(Path(t)/'CENSUS.md').read_text())
    def test_contract_consistency(self):
        self.assertEqual(NATIVE_ORDER,tuple(0 if v in CONTROLS else ARM_CODES[v] for v in ORDER))
        native=(P/'native_arm_order.hpp').read_text()
        self.assertIn('{'+','.join(map(str,NATIVE_ORDER))+'}',native)
        self.assertNotIn(RESIDUAL,ARM_CODES)
if __name__=='__main__':unittest.main()
