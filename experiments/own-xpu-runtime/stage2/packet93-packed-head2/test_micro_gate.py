import copy,unittest
from micro_gate import analyze,CANDIDATES
def samples(ratio=.84):
 rows=[]
 for name in CANDIDATES:
  rows.append(dict(kind='correctness',view=name,rows=248320,columns=2560,fp32_exact=True,bf16_exact=True,argmax_exact=True))
  for rep in range(40):
   for pos in (0,1):
    candidate=bool(pos^(rep&1));rows.append(dict(kind='sample',pair=name,view=name if candidate else 'production',repeat=rep,position=pos,event_ns=1000*ratio if candidate else 1000,rows=248320,columns=2560,sg=32,wg=32,diagnostic_only=True))
 rows.append(dict(kind='summary',passed=True,drained=True,rows=248320,columns=2560,diagnostic_only=True));return rows
class Gate(unittest.TestCase):
 def test_threshold(self):
  self.assertEqual(analyze(samples(.85))['qualified'],list(CANDIDATES))
  self.assertEqual(analyze(samples(.850001))['qualified'],[])
 def test_refusals(self):
  for kind in ('missing','duplicate','order','short','nan','negative','bad-exact','incomplete','geometry'):
   rows=samples();sample=next(r for r in rows if r['kind']=='sample')
   if kind=='missing':rows.pop(3)
   if kind=='duplicate':rows.insert(3,copy.deepcopy(rows[3]))
   if kind=='order':sample['position']=1
   if kind=='short':sample['rows']=10240
   if kind=='nan':sample['event_ns']=float('nan')
   if kind=='negative':sample['event_ns']=-1
   if kind=='bad-exact':rows[0]['fp32_exact']=False
   if kind=='incomplete':rows[-1]['passed']=False
   if kind=='geometry':sample['wg']=256
   with self.subTest(kind=kind),self.assertRaises(ValueError):analyze(rows)
 def test_order_bias_does_not_pass(self):
  rows=samples(.7)
  for row in rows:
   if row['kind']=='sample' and row['view']!='production' and row['repeat']%2:row['event_ns']=900
  self.assertEqual(analyze(rows)['qualified'],[])
if __name__=='__main__':unittest.main()
