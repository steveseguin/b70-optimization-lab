import copy,unittest
import micro_gate as G
def rows(ratio=0.8):
 result=[]
 for name in G.CANDIDATES:
  result.append(dict(kind='correctness',view=name,rows=640,columns=2560,experts=512,selected_experts=10,bf16_exact=True,status_exact=True))
  for rep in range(40):
   for pos in range(2):
    view=name if pos^(rep&1) else 'production'
    result.append(dict(kind='sample',pair=name,view=view,repeat=rep,position=pos,event_ns=100*ratio if view==name else 100,rows=640,columns=2560,sg=32,wg=64,experts=512,selected_experts=10,diagnostic_only=True))
 result.append(dict(kind='summary',passed=True,drained=True,rows=640,columns=2560,diagnostic_only=True))
 return result
class Gate(unittest.TestCase):
 def test_threshold(self):
  self.assertEqual(tuple(G.analyze(rows())['qualified']),G.CANDIDATES)
  self.assertEqual(G.analyze(rows(.86))['qualified'],[])
 def test_missing_pair(self):
  r=rows();del r[3]
  with self.assertRaises(ValueError):G.analyze(r)
 def test_wrong_order(self):
  r=rows();r[1]['view']='bad'
  with self.assertRaises(ValueError):G.analyze(r)
 def test_wrong_bank(self):
  r=rows();r[1]['experts']=10
  with self.assertRaises(ValueError):G.analyze(r)
 def test_wrong_output(self):
  r=rows();r[0]['bf16_exact']=False
  with self.assertRaises(ValueError):G.analyze(r)
 def test_wrong_shape(self):
  r=rows();r[1]['rows']=17
  with self.assertRaises(ValueError):G.analyze(r)
 def test_one_order_fails(self):
  r=rows()
  for x in r:
   if x.get('kind')=='sample' and x['view']!='production':x['event_ns']=70 if x['repeat']%2 else 90
  self.assertEqual(G.analyze(r)['qualified'],[])
 def test_no_runtime_evidence(self):
  import tempfile
  with tempfile.TemporaryDirectory() as p:
   with self.assertRaises(ValueError):G.require_qualified(p)
if __name__=='__main__':unittest.main()
