import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import once
class Terminal(unittest.TestCase):
 def records(self):
  m=json.loads((once.P/'manifest.json').read_text());rows=[]
  for entry in m['schedule']:
   c=m['cases'][entry['case']];h=c['fixtures']['expected']['sha256'];rows.append(dict(warmup=entry['warmup'],cycle=entry['cycle'],layer=c['layer'],order=''.join(entry['order']),exact=True,A_sha256=h,B_sha256=h,expected_sha256=h,A_start_ns=1,A_end_ns=3,B_start_ns=4,B_end_ns=6))
  return rows
 def result(self):return dict(schema='gsq.attention-q8.native-micro.v1',passed=True,safe_to_exit=True,completed_exact_pairs=84,attempted_kernel_submissions=168,device_bytes=106481664,transfer_bytes=106000000,warmup_cycles=4,measured_cycles=24,error='',cleanup_error='',teardown=dict(safe_to_exit=True,exit_code=0,in_flight=0,live_bytes=0))
 def test_complete_and_wrong_output(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(once,'STAGE',Path(tmp)):
   f=Path(tmp)/'result/samples.jsonl';f.parent.mkdir();rows=self.records();f.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.assertTrue(once.exact_result(self.result()));rows[40]['B_sha256']='0'*64;f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaises(AssertionError):once.exact_result(self.result())
 def test_missing_pair_and_failed_teardown(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(once,'STAGE',Path(tmp)):
   f=Path(tmp)/'result/samples.jsonl';f.parent.mkdir();f.write_text(''.join(json.dumps(r)+'\n' for r in self.records()[:-1]))
   with self.assertRaises(AssertionError):once.exact_result(self.result())
   r=self.result();r['teardown']['live_bytes']=1
   with self.assertRaises(AssertionError):once.exact_result(r)
if __name__=='__main__':unittest.main(verbosity=2)
