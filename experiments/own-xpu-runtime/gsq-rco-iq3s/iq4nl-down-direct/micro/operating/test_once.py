import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import importlib.util
P=Path(__file__).resolve().parent.parent
s=importlib.util.spec_from_file_location('iq4_final_once_test',P/'once.py');once=importlib.util.module_from_spec(s);s.loader.exec_module(once)
class Terminal(unittest.TestCase):
 def records(self):
  m=json.loads((once.P/'manifest.json').read_text());rows=[]
  for entry in m['schedule']:
   c=m['cases'][entry['case']];h=c['fixtures']['expected']['sha256'];rows.append(dict(warmup=entry['warmup'],cycle=entry['cycle'],layer=c['layer'],label=c['label'],A_status_sha256=c['fixtures']['status']['sha256'],B_status_sha256=c['fixtures']['status']['sha256'],expected_status_sha256=c['fixtures']['status']['sha256'],order=''.join(entry['order']),exact=True,A_sha256=h,B_sha256=h,expected_sha256=h,A_start_ns=1,A_end_ns=3,B_start_ns=4,B_end_ns=6))
  return rows
 def result(self):return dict(schema='gsq.iq4nl-direct.native-micro.v1',passed=True,safe_to_exit=True,backend_acknowledged=True,completed_exact_pairs=28,attempted_kernel_submissions=56,device_bytes=471974600,transfer_bytes=474741560,warmup_cycles=4,measured_cycles=24,error='',cleanup_error='',teardown=dict(safe_to_exit=True,exit_code=0,in_flight=0,live_bytes=0))
 def test_complete_and_wrong_output(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(once,'STAGE',Path(tmp)):
   f=Path(tmp)/'result/samples.jsonl';f.parent.mkdir();rows=self.records();f.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.assertTrue(once.exact_result(self.result()));rows[12]['B_sha256']='0'*64;f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaises(AssertionError):once.exact_result(self.result())
 def test_wrong_status(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(once,'STAGE',Path(tmp)):
   f=Path(tmp)/'result/samples.jsonl';f.parent.mkdir();rows=self.records();rows[0]['B_status_sha256']='0'*64;f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaises(AssertionError):once.exact_result(self.result())
 def test_missing_pair_and_failed_teardown(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(once,'STAGE',Path(tmp)):
   f=Path(tmp)/'result/samples.jsonl';f.parent.mkdir();f.write_text(''.join(json.dumps(r)+'\n' for r in self.records()[:-1]))
   with self.assertRaises(AssertionError):once.exact_result(self.result())
   r=self.result();r['teardown']['live_bytes']=1
   with self.assertRaises(AssertionError):once.exact_result(r)
 def test_ack_required_even_with_exact_kernels(self):
  r=self.result();r['backend_acknowledged']=False
  with self.assertRaises(AssertionError):once.exact_result(r)
if __name__=='__main__':unittest.main(verbosity=2)
