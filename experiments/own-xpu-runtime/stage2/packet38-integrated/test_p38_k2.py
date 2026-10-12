"""CPU-only packet38 model-shape K2 admission tests."""
import json,unittest
from pathlib import Path
import k2_summary
P=Path(__file__).resolve().parent
class Gate(unittest.TestCase):
 def test_model_shape_coverage(self):
  entry=json.loads((P/'k2-class-registry.json').read_text())['classes']['qsa.attention']
  self.assertEqual(entry['workloads'],['qsa-c256-n'+str(n) for n in list(range(88,153))+[256]])
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
 def test_missing_capacity_refused(self):
  rows=[{'class':'qsa.attention','variant':v,'repetition':0,'workload':'n88','stage_count':1,'start_ns':1,'end_ns':101 if v=='packet18' else 51,'exact':True} for v in ('packet18','specialised')]
  result=k2_summary.aggregate(rows,{'qsa.attention':{'workloads':['n88','n256']}},repetitions=1)
  self.assertFalse(result['passed'])
if __name__=='__main__':unittest.main()
