"""Reject stale, duplicated, mixed, reordered, and unsafe merged fixture owners."""
import copy,json,tempfile,unittest
from pathlib import Path
import fixture_support as f
class Owners(unittest.TestCase):
 def row(self):return dict(owner_cards=1,teardown=[dict(status='complete',exit_code=0,safe_to_exit=True,live_bytes=0,in_flight=0,sequence=['free:workspace:'+prefix+'0','context-released']) for _,prefix in f.FIXTURE_OWNER_SEQUENCE])
 def test_merged_contract(self):self.assertTrue(f.sequential_teardown(self.row()))
 def test_missing_extra_duplicate_and_reordered(self):
  row=self.row();states=row['teardown']
  for changed in (states[:-1],states+[states[-1]],states[:-1]+[states[0]],list(reversed(states))):
   with self.subTest(changed=changed):self.assertFalse(f.sequential_teardown(dict(row,teardown=changed)))
 def test_every_owner_safety(self):
  for index in range(len(f.FIXTURE_OWNER_SEQUENCE)):
   for key,value in (('status','failed'),('exit_code',1),('safe_to_exit',False),('live_bytes',1),('in_flight',1),('sequence',[]),('sequence',['free:workspace:unknown-0']),('live_bytes',False),('in_flight',False)):
    with self.subTest(owner=index,key=key):
     row=self.row();row['teardown'][index][key]=value;self.assertFalse(f.sequential_teardown(row))
 def test_card_and_mixed_owner(self):
  for value in (0,2,True,None):self.assertFalse(f.sequential_teardown(dict(self.row(),owner_cards=value)))
  row=self.row();row['teardown'][0]['sequence'].append('free:workspace:p39-fixture-1');self.assertFalse(f.sequential_teardown(row))
 def test_emitted_sequence_matches_driver(self):
  # This binds the named plan to the source's receipt assembly. In particular,
  # owner execution order differs from receipt order for GEMV and small GEMV.
  source=(f.HERE/'fixture_driver.cpp').read_text()
  import re
  names=re.findall(r'teardown\.insert\(teardown.size\(\)-1,","\+(\w+)\.teardown\)',source)
  self.assertEqual(names,['adapter','small','gemv','epilogues'])
  for filename,prefix in [('fixture_driver.cpp','fixture-'),('adapter_fixture.cpp','actual-adapter-fixture-'),('small_gemv_fixture.cpp','small-gemv-'),('gemv_timing.cpp','gemv-k2-'),('p39_fixture.cpp','p39-fixture-')]:
   self.assertIn('"'+prefix+'"',(f.HERE/filename).read_text())
 def test_full_receipt_gate_rejects_same_count_wrong_owner(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'output.bin').write_bytes(b'CPU validation output')
   digest=f.sha(root/'output.bin')
   row=dict(self.row(),schema='packet26.fixtures.v1',passed=True,device_executed=False,validation_only=True,reference_exact=False,packet18_exact=False,fixtures=218,odd_lengths=20,ties=1,nan_routes=1,max_submission_ns=0,output_sha256=digest)
   (root/'receipt.json').write_text(json.dumps(row))
   f.fixture_receipt_gate(root,dict(nongemv_fixture_host_sha256=digest),cpu_rehearsal=True)
   row['teardown'][-1]=copy.deepcopy(row['teardown'][0]);(root/'receipt.json').write_text(json.dumps(row))
   with self.assertRaisesRegex(ValueError,'sequential-owner'):
    f.fixture_receipt_gate(root,dict(nongemv_fixture_host_sha256=digest),cpu_rehearsal=True)
 def test_actual_device_receipts_read_only(self):
  # Historical receipt replay is optional on a clean clone; no binary runs.
  for rank in (0,1):
   path=f.HERE/f'build/c4096-dr{rank}-gpu/K1a/run0/receipt.json'
   if path.exists():self.assertTrue(f.sequential_teardown(json.loads(path.read_text())))
if __name__=='__main__':unittest.main()
