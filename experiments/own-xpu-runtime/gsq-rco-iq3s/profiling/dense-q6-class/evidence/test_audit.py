import importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('dense_class_actual_audit',P/'device-a/audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Audit(unittest.TestCase):
 def fixture(self):
  rows=[dict(rank=r,op=1,position=p,fixture=max(0,p-85),speculative=False,gpu_ms=float(r+1)) for p in range(214) for r in (0,1)]
  result=dict(tokens=[2]*128,stats=dict(guesses=0,hits=0,misses=0),rank_trace=rows)
  classes={str(r):dict(report=dict(classes=[dict(device_ms=214.*(r+1)+0.5)])) for r in (0,1)}
  return result,classes
 def test_both_ranks_boundary_and_signed_residual(self):
  result,classes=self.fixture();classes['1']['report']['classes'][0]['device_ms']=427.5;got=A.derive_phases(result,classes)
  self.assertEqual([got['0']['groups'][n]['halves'] for n in ('prompt_only','first_output','later_decode')],[86,1,127]);self.assertEqual(got['0']['TTFT_positions_device_ms_sum'],87.);self.assertEqual(got['1']['groups']['later_decode']['device_ms_sum'],254.);self.assertEqual(got['0']['class_minus_half_device_ms'],0.5);self.assertEqual(got['1']['class_minus_half_device_ms'],-0.5)
 def test_bad_trace_identity_and_duration_refuse(self):
  for kind in ('missing','duplicate','fixture','speculation','nan','draft'):
   r,c=self.fixture()
   if kind=='missing':r['rank_trace'].pop()
   elif kind=='duplicate':r['rank_trace'][4]['position']=1
   elif kind=='fixture':r['rank_trace'][172]['fixture']=0
   elif kind=='speculation':r['rank_trace'][0]['speculative']=True
   elif kind=='nan':r['rank_trace'][0]['gpu_ms']=float('nan')
   else:r['rank_trace'].append(dict(op=9))
   with self.subTest(kind=kind),self.assertRaises(ValueError):A.derive_phases(r,c)
 def test_exact_plan_binary_ledger_paths(self):
  p=A.read(P/'device-a/plan.json');self.assertEqual(A.sha(P/'device-a/plan.json'),A.PLAN_SHA);self.assertEqual(p['adapter']['binary_sha256'],A.BINARY);self.assertEqual(p['adapter']['build_receipt_sha256'],A.BUILD_SHA);self.assertEqual(p['suite']['candidate_actual_review_sha256'],A.ACTUAL_SHA)
  source=(P/'device-a/audit.py').read_text();self.assertIn("L/'dense-q6-p33/operating/candidate-ledger.json'",source)
if __name__=='__main__':unittest.main(verbosity=2)
