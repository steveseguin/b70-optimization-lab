"""CPU-only packet38 model-shape K2 admission tests."""
import json,unittest
from pathlib import Path
import k2_summary
P=Path(__file__).resolve().parent
class Gate(unittest.TestCase):
 def test_model_shape_coverage(self):
  entry=json.loads((P/'k2-class-registry.json').read_text())['classes']['qsa.attention']
  self.assertEqual(entry['workloads'],['qsa-c256-n'+str(n) for n in (88,104,120,136,152,256)])
  self.assertEqual(entry['shape']['context_lengths'],[88,104,120,136,152,256])
  self.assertEqual(entry['exactness_context_lengths'],list(range(88,153))+[256])
  self.assertEqual(entry['candidates'],['round2','p33.qsa.shape','p30.attention.sg32','p30.attention.score_softmax'])
 def test_each_shape_must_win(self):
  registry={'qsa.attention':{'workloads':['n88','n256']}}
  rows=[]
  for workload in ['n88','n256']:
   for rep in range(2):
    for role,cost in [('packet18',100),('specialised',50 if workload=='n88' else 101)]:
     rows.append(dict(class_='unused',**{'class':'qsa.attention','variant':role,'repetition':rep,'workload':workload,'stage_count':1,'start_ns':1,'end_ns':1+cost,'exact':True}))
  result=k2_summary.aggregate(rows,registry,repetitions=2)
  self.assertTrue(result['passed']);self.assertEqual(result['selection']['qsa.attention'],'packet18')
 def test_every_registered_length_must_win(self):
  workloads=['qsa-c256-n'+str(n) for n in (88,104,120,136,152,256)]
  for losing in workloads+[None]:
   rows=[]
   for workload in workloads:
    for rep in range(2):
     for variant in ('packet18','specialised'):
      cost=100 if variant=='packet18' else 91 if workload==losing else 50
      rows.append({'class':'qsa.attention','variant':variant,'repetition':rep,'workload':workload,'stage_count':1,'start_ns':1,'end_ns':1+cost,'exact':True})
   result=k2_summary.aggregate(rows,{'qsa.attention':{'workloads':workloads}},2)
   self.assertTrue(result['passed'])
   self.assertEqual(result['selection']['qsa.attention'],'packet18' if losing else 'specialised')
   for missing in workloads:
    self.assertFalse(k2_summary.aggregate([r for r in rows if r['workload']!=missing],{'qsa.attention':{'workloads':workloads}},2)['passed'])

 def test_summary_refuses_old_residency_or_wrong_kernel(self):
  import tempfile
  entry=json.loads((P/'k2-class-registry.json').read_text())['classes']['qsa.attention']
  entry['candidates']=['p30.attention.sg32']
  rows=[{'class':'qsa.attention','variant':v,'candidate':'p30.attention.sg32','implementation':'packet18' if v=='packet18' else 'p30.attention.sg32','workload':w,'repetition':r,'stage_count':1,'start_ns':1,'end_ns':101 if v=='packet18' else 51,'exact':True,'state_storage':'resident-overwrite'} for w in entry['workloads'] for r in range(200) for v in ('packet18','specialised')]
  with tempfile.TemporaryDirectory(dir=P/'build') as tmp:
   root=Path(tmp)
   def check():
    (root/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return k2_summary.summarize(root,classes={'qsa.attention':entry})
   self.assertTrue(check()['passed'])
   rows[0].pop('state_storage')
   result=check();self.assertFalse(result['passed']);self.assertEqual(result['selection']['qsa.attention'],'packet18')
   rows[0]['state_storage']='independent-preuploaded';self.assertFalse(check()['passed'])
   rows[0]['state_storage']='resident-overwrite';rows[0]['implementation']='round2';self.assertFalse(check()['passed'])

 def test_missing_capacity_refused(self):
  rows=[{'class':'qsa.attention','variant':v,'repetition':0,'workload':'n88','stage_count':1,'start_ns':1,'end_ns':101 if v=='packet18' else 51,'exact':True} for v in ('packet18','specialised')]
  result=k2_summary.aggregate(rows,{'qsa.attention':{'workloads':['n88','n256']}},repetitions=1)
  self.assertFalse(result['passed'])
if __name__=='__main__':unittest.main()
