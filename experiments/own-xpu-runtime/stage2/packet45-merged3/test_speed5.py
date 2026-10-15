import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import memory_plan,memory_gate,window,pipeline
P=Path(__file__).resolve().parent
class Split23(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.ledger=memory_plan.plan()
 def test_old_rows_unchanged(self):
  from speed5_qualification import before
  for k,v in before()['memory_plan']['placements'].items():self.assertEqual(self.ledger['placements'][k],v)
 def test_exact_new_rows(self):
  expected={(4096,0):(3442503518,5212496022),(32768,0):(2695655262,4737228950),(4096,1):(7636189332,1858131808)}
  for (c,dr),free in expected.items():
   row=memory_gate.configuration(self.ledger,c,dr,23)
   self.assertEqual(tuple(r['free_with_mtp_bytes'] for r in row['ranks']),free)
   self.assertEqual([r['target_layers'] for r in row['ranks']],[23,25])
   for r in row['ranks']:
    n=r['total_with_mtp_bytes'];census={'totals':{'device':n},'allocations':[dict(bytes=n,live=True,memory='device')]}
    self.assertTrue(memory_gate.check(census,self.ledger,r['rank'],True,c,dr,23)['passed'])
 def test_32k_rank1_refused(self):
  self.assertEqual(self.ledger['placements']['1-split23']['capacities']['32768']['ranks'][1]['free_with_mtp_bytes'],1314969440)
  with self.assertRaisesRegex(ValueError,'margin'):memory_gate.configuration(self.ledger,32768,1,23)
 def test_refuse_before_output_or_device(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'must-not-exist'
   argv=['window.py','--authorized-device-window','--window','K0','--card','2','--context','32768','--draft-rank','1','--target-split','23','--output',str(out)]
   with patch('sys.argv',argv),patch.object(window,'environment_gate',side_effect=AssertionError('reached device admission')):
    with self.assertRaisesRegex(ValueError,'margin'):window.main()
   self.assertFalse(out.exists())
 def test_unknown_or_small_split_refused(self):
  for c,dr,s in ((256,0,23),(256,1,23),(4096,0,25),(4096,1,25),(4096,2,23)):
   with self.assertRaises(ValueError):memory_gate.configuration(self.ledger,c,dr,s)
 def test_boolean_cannot_override_floor(self):
  x=copy.deepcopy(self.ledger);r=x['placements']['1-split23']['capacities']['32768']['ranks'][1];r['allocation_margin_passed']=True
  with self.assertRaisesRegex(ValueError,'margin'):memory_gate.configuration(x,32768,1,23)
 def test_census_above_projected_limit(self):
  r=memory_gate.configuration(self.ledger,4096,1,23)['ranks'][1];n=r['total_with_mtp_bytes']+1
  with self.assertRaisesRegex(ValueError,'exceed'):memory_gate.check({'totals':{'device':n},'allocations':[dict(bytes=n,live=True,memory='device')]},self.ledger,1,True,4096,1,23)
 def test_pipeline_parser(self):
  self.assertEqual(pipeline.parser().parse_args(['--target-split','23','--output','/tmp/speed5-parser-only']).target_split,23)
 def test_prerequisite_split_identity(self):
  for diagnostic in (False,True):
   identity=dict(boot_id='mock',artifacts_sha256={'mock':'same'},environment={},card=2,context=4096,draft_rank=1,target_split=23,build_receipt_sha256='seal',diagnostic_unsealed=diagnostic,qualifying=not diagnostic)
   row=dict(identity,window='K0',passed=True,cpu_rehearsal=True,device_executed=False,receipts={})
   with tempfile.TemporaryDirectory() as d:
    f=Path(d)/'window.json';f.write_text(json.dumps(row));self.assertTrue(window.prerequisites(f,'K0',identity,cpu_rehearsal=True)['passed'])
    for other in (0,24,None):
     row['target_split']=other;f.write_text(json.dumps(row))
     with self.assertRaisesRegex(ValueError,'target_split'):window.prerequisites(f,'K0',identity,cpu_rehearsal=True)
if __name__=='__main__':unittest.main()
