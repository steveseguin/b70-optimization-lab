import json,tempfile,unittest,importlib.util
from pathlib import Path
from unittest.mock import patch
O=Path(__file__).resolve().parent

def load(n,f):
 s=importlib.util.spec_from_file_location(n,f);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
once=load('hc_once_mock',O/'once.py');prep=load('hc_manifest_mock',O/'prepare.py')
class Terminal(unittest.TestCase):
 def manifest(self):
  e=json.loads((O.parent/'evidence/extraction.json').read_text());cases,schedule=prep.cases_schedule(e);return dict(cases=cases,schedule=schedule)
 def rows(self,m):
  return [dict(warmup=e['warmup'],cycle=e['cycle'],layer=m['cases'][e['case']]['layer'],label=m['cases'][e['case']]['label'],order=''.join(e['order']),exact=True,A_sha256=m['cases'][e['case']]['fixtures']['expected']['sha256'],B_sha256=m['cases'][e['case']]['fixtures']['expected']['sha256'],expected_sha256=m['cases'][e['case']]['fixtures']['expected']['sha256'],A_start_ns=1,A_end_ns=3,B_start_ns=4,B_end_ns=6) for e in m['schedule']]
 def result(self):return dict(schema='gsq.hc-bf16-one-sg.native-micro.v1',passed=True,safe_to_exit=True,backend_acknowledged=True,completed_exact_pairs=56,attempted_kernel_submissions=112,device_bytes=6677776,transfer_bytes=6712768,warmup_cycles=4,measured_cycles=24,error='',cleanup_error='',teardown=dict(safe_to_exit=True,exit_code=0,in_flight=0,live_bytes=0))
 def test_actual_metadata_schedule_exact_outputs(self):
  m=self.manifest();self.assertEqual(len(m['schedule']),56);self.assertEqual([c['rows'] for c in m['cases']],[320,4])
  for warm,n in [(True,4),(False,24)]:
   counts={}
   for index,e in enumerate(x for x in m['schedule'] if x['warmup']==warm):
    k=(e['case'],''.join(e['order']),index%2);counts[k]=counts.get(k,0)+1
   self.assertEqual(len(counts),8);self.assertEqual(set(counts.values()),{n//4})
  with tempfile.TemporaryDirectory() as tmp,patch.object(once,'STAGE',Path(tmp)),patch.object(once,'MANIFEST',Path(tmp)/'manifest.json'):
   once.MANIFEST.write_text(json.dumps(m));f=Path(tmp)/'result/samples.jsonl';f.parent.mkdir();f.write_text(''.join(json.dumps(x)+'\n' for x in self.rows(m)));self.assertTrue(once.exact_result(self.result()))
 def test_wrong_output_case_order_missing_pair(self):
  m=self.manifest()
  with tempfile.TemporaryDirectory() as tmp,patch.object(once,'STAGE',Path(tmp)),patch.object(once,'MANIFEST',Path(tmp)/'manifest.json'):
   once.MANIFEST.write_text(json.dumps(m));f=Path(tmp)/'result/samples.jsonl';f.parent.mkdir()
   for bad in ['output','case','order','missing']:
    rows=self.rows(m)
    if bad=='output':rows[12]['B_sha256']='0'*64
    elif bad=='case':rows[12]['label']='blk.0.hc.a.low' if rows[12]['label'].endswith('inject') else 'blk.0.hc.a.inject'
    elif bad=='order':rows[12]['order']='BA' if rows[12]['order']=='AB' else 'AB'
    else:rows.pop()
    f.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    with self.subTest(bad=bad),self.assertRaises(AssertionError):once.exact_result(self.result())
 def test_ack_and_owner_cleanup_required(self):
  for bad in ['ack','live','exit','count','bytes']:
   r=self.result()
   if bad=='ack':r['backend_acknowledged']=False
   elif bad=='live':r['teardown']['live_bytes']=1
   elif bad=='exit':r['teardown']['exit_code']=1
   elif bad=='count':r['attempted_kernel_submissions']=111
   else:r['transfer_bytes']+=1
   with self.subTest(bad=bad),self.assertRaises(AssertionError):once.exact_result(r)
 def test_parent_guard_and_ack_source_retained(self):
  parent=once.LANE/'iq4nl-down-direct/micro';old=(parent/'once.py').read_text();new=(O/'once.py').read_text()
  for text in ["before['root_free_bytes'] > 27_250_000_000","observed_native_target_fd and backend_acknowledged and exact_result(result)","backend_acknowledged=ACK.publish_ack(STAGE/'result',native_identity,native_holders,target,snapshot,state)","snapshot['root_free_bytes'] < 27_000_000_000"]:
   self.assertIn(text,old);self.assertIn(text,new)
  self.assertEqual((once.P/'handshake.py').read_bytes(),(parent/'handshake.py').read_bytes());self.assertEqual(once.UNIT,'gsq-hc-bf16-one-sg-micro-a')
if __name__=='__main__':unittest.main(verbosity=2)
