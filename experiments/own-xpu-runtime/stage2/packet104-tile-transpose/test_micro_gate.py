"""Protocol tests only. These are invented timings, never measurements."""
import json,unittest
from micro_gate import analyze,CANDIDATES,SHAPES
from build_engine import P
class Gate(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  rows=[]
  for name in CANDIDATES:
   nr,k,count,experts,wg,strata=SHAPES[name]
   shape=dict(rows=nr,columns=k,count=count,experts=experts)
   for route in range(strata or 384):
    rows.append(dict(kind='correctness',view=name,route=route,fp32_exact=True,bf16_exact=True,status_exact=True,**shape))
    for rep in range(40):
     for pos in range(2):
      candidate=bool(pos^(rep&1))
      rows.append(dict(kind='sample',pair=name,view=name if candidate else 'production',route=route,repeat=rep,position=pos,event_ns=80 if candidate else 100,sg=32,wg=wg,scrub_bytes=536870912,diagnostic_only=True,**shape))
  rows.append(dict(kind='summary',passed=True,drained=True,diagnostic_only=True,candidate_count=len(CANDIDATES),route_count=384));cls.rows=rows
 def reject(self,index,key,value):
  row=self.rows[index];before=row[key];row[key]=value
  try:
   with self.assertRaises(ValueError):analyze(self.rows,384)
  finally:row[key]=before
 def test_complete_pass(self):
  r=analyze(self.rows,384)
  self.assertEqual(len(r['qualified']),len(CANDIDATES))
  self.assertIn('draft-gate-tile16',r['qualified'])
  self.assertTrue(r['candidates']['draft-gate-tile16']['qualified'])
 def test_missing_route(self):
  with self.assertRaises(ValueError):analyze(self.rows[:-81]+self.rows[-1:],384)
 def test_duplicate_correctness(self):
  self.reject(81,'route',0)
 def test_order(self):self.reject(1,'view','target-gate-tile16')
 def test_nonfinite_time(self):self.reject(1,'event_ns',float('nan'))
 def test_wrong_shape(self):self.reject(1,'rows',2560)
 def test_wrong_kernel_geometry(self):self.reject(1,'wg',128)
 def test_missing_scrub(self):self.reject(1,'scrub_bytes',0)
 def test_failed_exactness(self):self.reject(0,'fp32_exact',False)
 def test_failed_drain(self):self.reject(-1,'drained',False)
 def test_single_stratum_fail_blocks_candidate(self):
  indices=[i for i,r in enumerate(self.rows[:81]) if r.get('view')=='target-gate-tile16' and r.get('kind')=='sample']
  for i in indices:self.rows[i]['event_ns']=90
  try:self.assertNotIn('target-gate-tile16',analyze(self.rows,384)['qualified'])
  finally:
   for i in indices:self.rows[i]['event_ns']=80
 def test_one_order_fails_despite_good_combined_median(self):
  indices=[i for i,r in enumerate(self.rows[:81]) if r.get('view')=='target-gate-tile16' and r.get('kind')=='sample']
  for i in indices:self.rows[i]['event_ns']=90 if self.rows[i]['repeat']%2 else 50
  try:self.assertNotIn('target-gate-tile16',analyze(self.rows,384)['qualified'])
  finally:
   for i in indices:self.rows[i]['event_ns']=80
 def test_selected_baseline(self):
  selection=json.loads((P/'baseline-selection.json').read_text())
  self.assertEqual(selection['choices']['experts'],'down-tile16')
  for key in ('gate_up','down','shared_gate','shared_up','shared_down','fuse_expert_activation','fuse_shared_activation'):self.assertEqual(selection['draft'][key],'production')
  dispatch=json.loads((P/'baseline-dispatch-speed6.json').read_text())['gemv']
  self.assertEqual(dispatch['shexpdown'],'p33.dense.segment')
  self.assertEqual(dispatch['shexpgate'],'r5');self.assertEqual(dispatch['shexpup'],'r5')
if __name__=='__main__':unittest.main()
