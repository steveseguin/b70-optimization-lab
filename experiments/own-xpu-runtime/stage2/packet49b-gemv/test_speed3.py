import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import memory_gate,memory_plan,window
P=Path(__file__).resolve().parent

class Admission(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.plan=memory_plan.plan()
 def test_old_rows_unchanged(self):
  old=json.loads((P/'evidence/speed3/before-memory-plan.json').read_text())
  for dr in ('0','1'):
   self.assertEqual(old['placements'][dr],self.plan['placements'][dr])
   for context in (256,4096,32768):memory_gate.configuration(self.plan,context,int(dr))
 def test_new_4k(self):
  row=memory_gate.configuration(self.plan,4096,0,24)
  self.assertEqual([r['target_layers'] for r in row['ranks']],[24,24])
  self.assertEqual(row['ranks'][0]['free_with_mtp_bytes'],2316749746)
  for r in row['ranks']:
   census={'totals':{'device':r['total_with_mtp_bytes']},'allocations':[{'bytes':r['total_with_mtp_bytes'],'live':True,'memory':'device'}]}
   self.assertTrue(memory_gate.check(census,self.plan,r['rank'],True,4096,0,24)['passed'])
 def test_32k_refused(self):
  self.assertEqual(self.plan['placements']['0-split24']['capacities']['32768']['ranks'][0]['free_with_mtp_bytes'],1434110898)
  with self.assertRaisesRegex(ValueError,'context4096 only'):memory_gate.configuration(self.plan,32768,0,24)
 def test_window_32k_refused_before_admission(self):
  argv=['window.py','--authorized-device-window','--window','K0','--card','0','--context','32768','--draft-rank','0','--target-split','24','--output',str(P/'build/never-launched-speed3')]
  with patch('sys.argv',argv),patch.object(window,'environment_gate',side_effect=AssertionError('reached host/device admission')):
   with self.assertRaisesRegex(ValueError,'context4096 only'):window.main()
 def test_256_refused(self):
  with self.assertRaisesRegex(ValueError,'context4096 only'):memory_gate.configuration(self.plan,256,0,24)
 def test_unknown_split_refused(self):
  with self.assertRaises(ValueError):memory_gate.configuration(self.plan,4096,0,25)
 def test_unknown_placement_refused(self):
  with self.assertRaises(ValueError):memory_gate.configuration(self.plan,4096,2,24)
 def test_over_budget_plan_refused(self):
  ledger=copy.deepcopy(self.plan);ledger['placements']['0-split24']['capacities']['4096']['ranks'][0]['allocation_margin_passed']=False
  with self.assertRaisesRegex(ValueError,'margin'):memory_gate.configuration(ledger,4096,0,24)
 def test_census_over_limit_refused(self):
  r=memory_gate.configuration(self.plan,4096,0,24)['ranks'][0];n=r['total_with_mtp_bytes']+1
  with self.assertRaisesRegex(ValueError,'exceed'):memory_gate.check({'totals':{'device':n},'allocations':[{'bytes':n,'live':True,'memory':'device'}]},self.plan,0,True,4096,0,24)
 def test_split_prerequisite_identity(self):
  for diagnostic in (False,True):
   identity=dict(boot_id='mock',artifacts_sha256={'mock':'same'},environment={},card=0,context=4096,draft_rank=0,target_split=24,build_receipt_sha256='seal',diagnostic_unsealed=diagnostic,qualifying=not diagnostic)
   row=dict(identity,window='K0',passed=True,cpu_rehearsal=True,device_executed=False,receipts={})
   with tempfile.TemporaryDirectory(dir=P/'build') as d:
    p=Path(d)/'window.json';p.write_text(json.dumps(row))
    self.assertTrue(window.prerequisites(p,'K0',identity,cpu_rehearsal=True)['passed'])
    for other in (0,None):
     row['target_split']=other;p.write_text(json.dumps(row))
     with self.assertRaisesRegex(ValueError,'target_split'):window.prerequisites(p,'K0',identity,cpu_rehearsal=True)

if __name__=='__main__':unittest.main()
