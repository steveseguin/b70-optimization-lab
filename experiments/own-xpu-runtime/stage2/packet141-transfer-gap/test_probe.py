"""CPU-only safety, provenance and protocol checks; never numerical device evidence."""
import hashlib,json,os,resource,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
P=Path(__file__).resolve().parent
import capture_identity as I
import capture_worker as W
import run_capture as R
from input_gate import validate_manifest
from build_engine import sha

class Probe(unittest.TestCase):
 def test_fixed_inputs(self):
  row=validate_manifest(json.loads((P/'suite.snapshot.json').read_text()))
  self.assertEqual(len(row['prompts']),1)
  self.assertEqual(row['prompts'][0]['reference_kind'],'packet49 CPU oracle')
  self.assertEqual(row['prompts'][0]['expected_tokens'][46],10015)
 def test_capture_routes(self):
  binding=json.loads((P/'capture-binding.json').read_text());raw=(I.ROOT/binding['source']).read_bytes()
  self.assertEqual(hashlib.sha256(raw).hexdigest(),binding['source_sha256'])
  expected=b''.join(raw[(47*24+l)*26744:(47*24+l)*26744+120] for l in range(24))
  self.assertEqual(expected,(P/'routes.bin').read_bytes())
  self.assertEqual(hashlib.sha256(expected).hexdigest(),binding['routes_sha256'])
  for layer in range(24):
   rows=list(struct.iter_unpack('<III',expected[layer*120:(layer+1)*120]))
   self.assertEqual(len({r[0] for r in rows}),10)
   self.assertTrue(all(0<=e<512 and start==0 and count==2560 for e,start,count in rows))
 def test_parent_bytes(self):
  row=json.loads((P/'copy-provenance.json').read_text())
  for name,item in row['files'].items():self.assertEqual(sha(P/name),item['sha256'],name)
 def test_symlinks(self):
  row=json.loads((P/'symlinks.json').read_text());self.assertEqual(row['count'],182)
  for link in row['links']:self.assertEqual(os.readlink(P/link['path']),link['target'])
  self.assertTrue((P/'oracle').is_symlink())
 def test_selection(self):
  self.assertEqual((P/'selection.json').read_bytes(),(P.with_name('packet136-record-bundle')/'selection.json').read_bytes())
 def test_memory(self):
  _,row=I.memory();self.assertEqual([r['target_layers'] for r in row['ranks']],[24,24])
  self.assertEqual(json.loads((P/'memory-plan.json').read_text())['probe_bytes_rank0'],268697600)
 def test_budget(self):
  self.assertGreaterEqual(R.WATCHDOG['tp2'],4*R.EXPECTED_SECONDS[-1]);self.assertEqual(R.WRITES['tp2'],200000000)
 def test_unit(self):
  R.unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/screen-packet141b-probe-B.service')
  with self.assertRaises(ValueError):R.unit_gate('0::/app.slice/random.service')
 def test_library_path(self):
  self.assertEqual(R.parser().parse_args([]).library_path,'/opt/intel/oneapi/compiler/2026.0/lib')
  with self.assertRaises(SystemExit):R.parser().parse_args(['--library-path','/tmp/untrusted'])
 def test_import_does_not_install_caps(self):
  code='import resource; before=resource.getrlimit(resource.RLIMIT_AS); import capture_worker,run_capture,exec_limits; assert resource.getrlimit(resource.RLIMIT_AS)==before'
  cp=subprocess.run([sys.executable,'-B','-c',code],cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  self.assertEqual(cp.returncode,0,cp.stderr)
 def test_finite_limit_refused(self):
  code='import resource;resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));import exec_limits;exec_limits.check()'
  cp=subprocess.run([sys.executable,'-B','-c',code],cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  self.assertNotEqual(cp.returncode,0);self.assertIn('refuses finite RLIMIT_AS',cp.stderr)
 def test_drain_after_cancel(self):
  events=[]
  class Permit:
   def __init__(self,*a,**kw):pass
   def __enter__(self):events.append('permit');return self
   def __exit__(self,*a):events.append('release')
  class T:
   check=lambda self: (_ for _ in ()).throw(ValueError('cancelled'))
   def stop(self,*a):events.append('stop')
   def close(self,success):self.check();events.append('close')
  with patch.object(W,'Teardown',Permit):W.drain(T(),Path('/unused'),False,'cancelled')
  self.assertEqual(events,['permit','stop','close','release'])
 def test_drain_finish_interrupt(self):
  events=[]
  class Permit:
   def __init__(self,*a,**kw):pass
   def __enter__(self):events.append('permit');return self
   def __exit__(self,*a):events.append('release')
  class T:
   check=lambda self:None
   def stop(self,*a):events.append('stop')
   def close(self,success):
    if success:raise ValueError('stop during finish')
    self.check();events.append('close')
  with patch.object(W,'Teardown',Permit):
   with self.assertRaisesRegex(ValueError,'finish'):W.drain(T(),Path('/unused'),True)
  self.assertEqual(events,['permit','stop','close','release'])
 def worker(self,bad=False):
  sys.path.insert(0,str(W.P56));import pipeline,suite,launch_guard
  events=[];entry=json.loads((P/'suite.snapshot.json').read_text())['prompts'][0]
  class Transport:
   def __init__(self,*args,**kwargs):self.closed=False;self.stop_write=1;self.children=[];events.append('load')
   def call(self,rank,op,**kw):
    self.assertion=(rank,op,kw);events.append(self.assertion)
    dest=self.dest/'rank0';dest.mkdir(exist_ok=True);(dest/'p141-complete.json').write_text('{"passed":true}')
   def stop(self,*args):events.append('stop')
   def close(self,success):self.closed=True;events.append(('close',success))
  class Monitor:
   def __init__(self,lane,out):out.mkdir(parents=True,exist_ok=True);(out/'device-isolation.json').write_text('{"passed":true}')
   def poll(self,**kw):pass
   def register(self,*a):raise AssertionError('native launch attempted')
  def reset(t,dest):dest.mkdir(parents=True,exist_ok=True);t.dest=dest;events.append(('reset',dest.name))
  def request(t,a,prompt,count):
   events.append(('tokens',count));tokens=entry['expected_tokens'][:count]
   if bad:tokens=tokens[:-1]+[-1]
   return dict(tokens=tokens)
  with tempfile.TemporaryDirectory() as temp:
   out=Path(temp)/'run'
   identity=dict(lineage=str(P),binary=str(P/'build/device/own-rt-iq3'),dispatch=str(P/'dispatch-speed6.json'),selection_sha256=sha(P/'selection.json'),timing='token',lane='B')
   with patch.dict(os.environ,W.masked_environment('B',{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':'/opt/intel/oneapi/compiler/2026.0/lib'}),clear=True),patch.object(I,'verify_identity',return_value=(dict(draft_rank=1,target_split=0),SimpleNamespace())),patch.object(pipeline,'Transport',Transport),patch.object(W,'DeviceMonitor',Monitor),patch.object(suite,'reset',side_effect=reset),patch.object(suite,'run_request',side_effect=request),patch.object(W,'drain',side_effect=lambda t,o,s,*args:t.close(s)),patch.object(launch_guard,'install_native_guard'),patch('subprocess.Popen',side_effect=AssertionError('unexpected exec')):
    code=W.run(identity,out,4800)
   if not bad:self.assertEqual(len(json.loads((out/'report-inputs.json').read_text())['requests']),2)
  return code,events
 def test_real_worker_sequence_mock(self):
  code,events=self.worker();self.assertEqual(code,0)
  self.assertEqual(events,['load',('reset','incident-retrospective'),('tokens',47),(0,13,dict(token=10015,position=133)),('reset','post-probe'),('tokens',8),('reset','after-suite'),('close',True)])
 def test_token_mismatch_stops_before_probe(self):
  code,events=self.worker(True);self.assertEqual(code,1)
  self.assertFalse(any(isinstance(x,tuple) and x[:2]==(0,13) for x in events));self.assertIn(('close',False),events)

if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));unittest.main()
