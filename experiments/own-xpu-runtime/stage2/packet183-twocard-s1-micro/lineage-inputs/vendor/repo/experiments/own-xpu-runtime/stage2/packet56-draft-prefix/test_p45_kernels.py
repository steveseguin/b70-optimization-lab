"""Merged candidates and measured per-token threshold admission; CPU only."""
import json, tempfile, unittest
from pathlib import Path
import k2_summary as k2
from merge_dispatch import validate
P=Path(__file__).resolve().parent
class Gate(unittest.TestCase):
 def rows(self,old=50000,ratio=.95,workloads=(None,)):
  return [dict(**{'class':'test'},variant=arm,repetition=i,workload=w,stage_count=1,start_ns=1,end_ns=1+old*(ratio if arm=='specialised' else 1),exact=True) for w in workloads for i in range(2) for arm in ('packet18','specialised')]
 def result(self,rule,**kw):return k2.aggregate(self.rows(**kw),{'test':rule},2)
 def test_heavy_three_percent(self):
  r=self.result({'groups_per_token':48});self.assertTrue(r['passed']);self.assertEqual(r['selection']['test'],'specialised');self.assertEqual(r['classes']['test']['required_improvement'],.03)
 def test_light_ten_percent(self):self.assertEqual(self.result({'groups_per_token':36})['selection']['test'],'packet18')
 def test_boundary_strict(self):
  self.assertEqual(self.result({'groups_per_token':40})['classes']['test']['required_improvement'],.1)
  self.assertEqual(self.result({'groups_per_token':48},ratio=.97)['selection']['test'],'packet18')
 def test_context_cases_do_not_inflate_token(self):
  r=self.result({'groups_per_token':12,'workloads':['short','long']},old=100000,workloads=('short','long'));self.assertEqual(r['classes']['test']['required_improvement'],.1)
 def test_gate_format_frequency(self):
  r=self.result({'workload_groups_per_token':{'iq2':47,'iq3':1}},workloads=('iq2','iq3'));self.assertEqual(r['classes']['test']['incumbent_class_ns_per_token'],2400000)
 def test_registered_candidates(self):
  registry=json.loads((P/'kernel-registry.json').read_text());validate(json.loads((P/'dispatch-p45.json').read_text()))
  self.assertTrue(all(k2.registry_for_context(256)[k]['shape']['width']==320 for k in ('hc.a.act','hc.f.act','final.act')));self.assertIn('p42.gate.packed',registry['gemv']['expsgate']);self.assertNotIn('p42.dense.fourparts',json.dumps(registry))
  for key in ('expert-checks-iq2','expert-checks-iq3','down-status','hc-low-act','shared-up-act-q6','shared-up-act-q8','attention-combine','shared-down-combine'):self.assertIn('p39.epilogue',registry['fusions'][key])
 def test_hc_winners_survive_declined_producer_fusion(self):
  names=('hc.a.act','hc.f.act','final.act','fusion:p39.hc-low-act');classes={n:k2.registry_for_context(256)[n] for n in names};rows=[]
  for name in names:
   fused=name.startswith('fusion:');candidate='p39.epilogue' if fused else 'p42.tiny.range'
   for i in range(200):
    for arm in ('packet18','specialised'):rows.append(dict(**{'class':name},variant=arm,candidate=candidate,implementation='packet18' if arm=='packet18' else candidate,repetition=i,stage_count=1,start_ns=1,end_ns=101 if arm=='packet18' else 121 if fused else 81,exact=True,timing_mode='reread'))
  with tempfile.TemporaryDirectory(dir=P/'build') as tmp:
   root=Path(tmp);(root/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));result=k2.summarize(root,classes=classes)
   self.assertTrue(result['passed'],result['failures']);self.assertEqual(result['final_dispatch']['fusions']['hc-low-act'],'packet18')
   for name in names[:3]:self.assertEqual(result['final_dispatch']['classes'][name],'p42.tiny.range')
 def test_full_fused_stage_sequence_required(self):
  rows=self.rows();rows[-1]['stage_count']=2;self.assertFalse(k2.aggregate(rows,{'test':{}},2)['passed'])
 def test_p39_chain_comparison_summary(self):
  classes={k:v for k,v in k2.registry_for_context(256).items() if k.startswith('fusion:p39.')};rows=[]
  for name,entry in classes.items():
   rotated='rotated' in entry['timing_modes']
   for i in range(200):
    for arm,ns in [('packet18',100000),('specialised',80000)]:
     stages=3 if arm=='packet18' else 1
     for stage in range(stages):rows.append(dict(**{'class':name},variant=arm,candidate='p39.epilogue',implementation='packet18' if arm=='packet18' else 'p39.epilogue',exact=True,candidate_available=True,repetition=i,event=i*10+stage,stage_count=stages,start_ns=1,end_ns=1+ns/stages,timing_mode='rotated' if rotated else 'reread',rotation_copies=8 if rotated else 1,buffer_copy=(i+(4 if arm=='specialised' else 0))%8 if rotated else 0,payload_bytes=123456,full_payload_bytes=123456))
  with tempfile.TemporaryDirectory(dir=P/'build') as tmp:
   root=Path(tmp);(root/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));result=k2.summarize(root,classes=classes)
   self.assertTrue(result['passed'],result.get('failures'));self.assertEqual(len(result['classes']),8)
if __name__=='__main__':unittest.main()
