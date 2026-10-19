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

def arm_row(d,cls='gdn'):return next(r for r in d['observations'] if r['view']==cls)

class Tests(unittest.TestCase):
    def test_valid_synthetic(self):
        r=analyze(fixture());self.assertTrue(r['passed']);self.assertEqual(len(r['ranked']),5)
        self.assertNotIn('attention',{x['kernel_class'] for x in r['ranked']})
        self.assertIn('attention (qsa_*; no arm since v3)',r['residual']['includes'])
        self.assertEqual({x['kernel_class'] for x in r['ranked']},set(CLASSES))
        self.assertFalse(r['residual']['causally_isolated'])
        for v in CONTROLS:
            self.assertAlmostEqual(r['residual']['paired_control_residual_ms'][v],
              r['control_means_ms'][v]-sum(x['measured_marginal_ms_per_body_pass'] for x in r['ranked']))
        # Per-rank saving .2+.01*index, summed over two ranks.
        self.assertEqual(r['ranked'][0]['kernel_class'],'norms_glue')
        self.assertAlmostEqual(r['ranked'][0]['measured_marginal_ms_per_body_pass'],2*(.2+.01*CLASSES.index('norms_glue')))
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
        self.assertNotIn('attention',ARM_CODES);self.assertIn(1,REFUSED_NATIVE_ARMS)
        self.assertEqual(CLASSES,('gdn','routed_experts','router_shared_expert','dense_hc','norms_glue'))
    def test_old_attention_arm_set_refused(self):
        # A v2-shaped stream (attention view/class) no longer matches the contract.
        d=fixture();d['order']=['C0','attention',*d['order'][1:]]
        with self.assertRaisesRegex(ValueError,'order'):analyze(d)
        d=fixture();d['report_classes']=['attention',*d['report_classes']]
        with self.assertRaisesRegex(ValueError,'coverage'):analyze(d)

# --- v3 sticky-error model (device-census-B-v2 root cause) -----------------
# qsa_select/qsa_attention are prepared with launch extent
# min(context,((P_admitted+32)//32)*32) (main.cpp admit_position/1285) and the
# device guard trips when pos>launch_extent-tokens (kernels.hpp position_limit,
# round2.hpp:11). The probe body pass runs at P=prompt+63 after the setup
# request admitted only P-1. Real launch plans of both ranks come from the v2
# device evidence. classify() mirrors native_probe.hpp exactly.
V2=P/'lineage/v2-root-cause'  # copies of the gitignored v2 device evidence
OLD_ORDER=('C0','attention','gdn','routed_experts','C1','router_shared_expert','dense_hc','norms_glue','C2')
OLD_ARM_CODES={'attention':1,**ARM_CODES}
def stage(label):
    if not label.startswith('blk.'):return -1
    end=label.find('.',4)
    if end==-1 or end==4 or not label[4:end].isdigit():return -1
    cls=label[end+1:]
    if not(cls.startswith('hc.a.') or cls.startswith('hc.f.')):return -1
    return {'norm':0,'low':1,'gate':2,'act':3,'mix':3,'inject':3}.get(cls[5:],-1)
def classify(l):
    op,n=l['op'],l['label']
    if n in('logits','argmax') or op in('handoff','handoff_result'):return -1
    if op in('begin','commit','check_status'):return 0
    if op.startswith('qsa_'):return 1
    if op in('gdn','conv','gdn_norm_gate'):return 2
    if op in('route','moe_combine') or 'router' in n or 'shexp' in n:return 3
    if op in('expert_gate_up','routed_gemv','expert_gather') or 'exps' in n:return 4
    if stage(n)==0:return 7
    if op=='gemv' or stage(n)>0:return 6
    return 7
def bound(pos):return min(4096,((pos+32)//32)*32)
def probe_positions():return {pid:len((P/'inputs'/pid/'tokens.txt').read_text().split())+TOKENS-1 for pid in IDS}
def sticky_trips(order,arm_codes,admit):
    trips=[];positions=probe_positions()
    for rank in (0,1):
        launches=json.loads((V2/f'rank{rank}-launch-plan.json').read_text())['launches']
        for view in order:
            if view in CONTROLS:continue
            for pid in IDS:
                pos=positions[pid];extent=bound(pos if admit else pos-1)
                for name,skip in (('control',0),('arm',arm_codes[view]),('repair',0)):
                    run=[l for l in launches if classify(l)>=0 and not(skip and classify(l)==skip)]
                    guarded=[l for l in run if l['op'] in('qsa_select','qsa_attention')]
                    if guarded and pos>extent-1:trips.append((rank,view,pid,name))
    return trips

class StickyGuard(unittest.TestCase):
    def test_v2_position_reproduced(self):
        # Device evidence: benchmark-analysis last half step 127, launch extent 128.
        self.assertEqual(probe_positions()['benchmark-analysis'],128)
        self.assertEqual([p for p,v in probe_positions().items() if v%32==0],['benchmark-analysis'])
        receipt=read(V2/'failure-receipt.json');row=receipt['setup_last_half_step']
        self.assertEqual((row['position'],row['launch_extent'],receipt['probe_position']),(127,128,128))
        self.assertEqual(receipt['rank0_probe_phases_recorded'],['packet168-before-control-snapshot'])
    def test_old_arm_set_fails(self):
        trips=sticky_trips(OLD_ORDER,OLD_ARM_CODES,admit=False)
        self.assertTrue(trips)
        self.assertEqual(trips[0],(0,'attention','benchmark-analysis','control'))
        self.assertEqual({t[2] for t in trips},{'benchmark-analysis'})
    def test_dropping_attention_alone_still_fails(self):
        # The control and repair passes always run qsa_*; the arm choice cannot fix it.
        trips=sticky_trips(ORDER,ARM_CODES,admit=False)
        self.assertTrue(trips);self.assertTrue(all(t[3] in('control','arm','repair') for t in trips))
        self.assertIn((0,'gdn','benchmark-analysis','control'),trips)
    def test_v3_every_arm_clear_after_admission(self):
        self.assertEqual(sticky_trips(ORDER,ARM_CODES,admit=True),[])
    def test_remaining_arms_never_skip_qsa_or_position_ops(self):
        for rank in (0,1):
            launches=json.loads((V2/f'rank{rank}-launch-plan.json').read_text())['launches']
            for arm in NATIVE_ARMS:
                if not arm:continue
                skipped=[l for l in launches if classify(l)==arm]
                self.assertTrue(skipped)
                self.assertFalse([l for l in skipped if l['op'].startswith('qsa_') or l['op'] in('begin','commit','check_status')])
if __name__=='__main__':unittest.main()
