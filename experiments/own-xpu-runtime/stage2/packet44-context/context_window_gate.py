"""CPU mocks exercise complete wrapper dispatch and post-run summaries; no binaries run."""
import errno,json,os,sys,tempfile,unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import window as w
import draft_window as dw
import pipeline as pp
from window_safety import environment_gate

WINDOWS=('K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs')

class ContextWindows(unittest.TestCase):
 def setUp(self):
  w.B.mkdir(exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(prefix='context-window-gate-',dir=w.B)
  self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def execute(self,name,context,cap=64,compression_failure=False,summary_failure=False):
  case=self.root/(name+str(context)+str(cap));case.mkdir()
  packet=case/'packet';packet.mkdir();builddir=packet/'build';builddir.mkdir()
  inp=packet/'input';inp.mkdir();(inp/'input.json').write_text(json.dumps(dict(tokens=[1],files={},model_dir='/model')))
  ledger={};(packet/'memory-plan.json').write_text(json.dumps(ledger))
  build=dict(passed=True,sources={},official_manifest_sha256='hash',memory_plan=ledger,
   artifacts_sha256={'device/p33-linked-fixtures':'hash','device/own-rt-iq3':'hash'},
   p33_linked_fixture_host_sha256='hash',nongemv_fixture_host_sha256_by_context={str(context):'host-'+str(context)},input_sha256='hash')
  (packet/'build-receipt.json').write_text(json.dumps(build))
  prereq=packet/'prereq.json';prereq.write_text(json.dumps(dict(pids=[101,102])))
  dispatch=packet/'dispatch.json';dispatch.write_text('{}')
  manifest=packet/'suite.json';manifest.write_text(json.dumps(dict(cap=cap,requests=[{}]*12)))
  output=builddir/'result'
  argv=['window.py','--authorized-device-window','--window',name,'--context',str(context),'--card','1','--output',str(output),'--input',str(inp),'--oracle',str(packet/'oracle'),'--dispatch',str(dispatch),'--controller','native','--suite-manifest',str(manifest)]
  for key in ('k0','k1a','k1b','k2','w0p','kd'):argv+=['--'+key,str(prereq)]
  calls=[];fixture_checks=[]
  def prerequisite(path,key,identity):
   return dict(pids=[101,102] if key=='K1a' else [103,104],candidate_dispatch_sha256='hash',dispatch_sha256='hash')
  def fixtures(a,out,env,watch):
   calls.append(('fixture',a.context,env.copy()))
   (out/'children.json').write_text(json.dumps(dict(pids=[103,104])))
   for i in (0,1):
    d=out/f'run{i}';d.mkdir();(d/'receipt.json').write_text(json.dumps(dict(cards=1,kernel_execution=False,explicit_allocations=0,kernels_per_device=1)))
   return {}
  def summary(root,identity):
   calls.append(('summary',identity['context']))
   if summary_failure:raise OSError(errno.ENOSPC,'No space left on device')
   for f in ('dispatch-measured.json','summary.json'):(root/f).write_text('{}')
   (root/'events.jsonl').write_text('')
   return dict(passed=True)
  def run(args,env,*hooks):
   calls.append(('run',args.context,args.tokens,args.draft,env.copy(),args.controller))
   args.output.mkdir(parents=True,exist_ok=True);(args.output/'receipt.json').write_text('{}')
   if name in ('WS','WSs'):return dict(passed=True,decode_median_tok_s=None,submission_median_tok_s=None,token_cap=args.tokens)
   return dict(tokens=list(range(64)),diagnostic=False,decode_tok_s=None)
  with ExitStack() as stack:
   for obj,key,value in ((w,'P',packet),(w,'B',builddir),(w,'ROOT',case)):
    stack.enter_context(patch.object(obj,key,value))
   stack.enter_context(patch.object(sys,'argv',argv))
   stack.enter_context(patch.dict(os.environ,{'LD_LIBRARY_PATH':'/literal path::relative/'},clear=True))
   stack.enter_context(patch.object(w.os,'getpriority',return_value=0 if name.startswith('W') else 19))
   stack.enter_context(patch.object(w,'sha',return_value='hash'))
   stack.enter_context(patch.object(w,'prerequisites',side_effect=prerequisite))
   stack.enter_context(patch.object(w,'validate'))
   stack.enter_context(patch.object(w,'memory_snapshot',return_value={'MemAvailable':128*1024**3}))
   stack.enter_context(patch.object(w,'admit',return_value={}))
   stack.enter_context(patch.object(w,'foreign_engines',return_value={}))
   stack.enter_context(patch.object(w,'journal',return_value=('', 'cursor')))
   stack.enter_context(patch.object(w.Watch,'postflight'))
   stack.enter_context(patch.object(w,'ldd_preflight',return_value={}))
   stack.enter_context(patch.object(w,'run_fixtures',side_effect=fixtures))
   stack.enter_context(patch.object(w,'fixture_receipt_gate',side_effect=lambda root,b:fixture_checks.append(b['nongemv_fixture_host_sha256'])))
   stack.enter_context(patch.object(w,'linked_fixture_gate',return_value={}))
   stack.enter_context(patch.object(w,'summarize',side_effect=summary))
   stack.enter_context(patch.object(w,'concurrency_canary',side_effect=lambda a,o,e,watch:calls.append(('canary',a.context,e.copy()))))
   stack.enter_context(patch.object(dw,'run',side_effect=lambda a,o,e,watch,b:(calls.append(('draft',a.context,e.copy())) or ({},[1,2]))))
   stack.enter_context(patch.object(pp,'run',side_effect=run))
   stack.enter_context(patch.object(w,'oracle_gate',return_value=({},list(range(64)))))
   import suite
   stack.enter_context(patch.object(suite,'validate_manifest',return_value=cap))
   stack.enter_context(patch.object(w,'compress_evidence',side_effect=OSError(errno.ENOSPC,'No space left on device') if compression_failure else lambda *a:None))
   result=w.main()
  record=json.loads((output/'window.json').read_text());json.dumps(record)
  self.assertEqual(record['context'],context)
  self.assertEqual(record['environment']['native']['LD_LIBRARY_PATH'],'/literal path::relative/')
  self.assertFalse((builddir/'FAULT.json').exists())
  if summary_failure:self.assertEqual(result,1);self.assertFalse(record['passed'])
  else:self.assertEqual(result,0);self.assertTrue(record['passed'])
  if compression_failure:self.assertTrue(record['raw_evidence_retained']);self.assertIn('retention_error',record)
  if name=='K2' and not summary_failure:self.assertIn(('summary',context),calls);self.assertEqual(len(record['rank_dispatches']),2)
  if name in ('K1a','K1b'):self.assertEqual(fixture_checks,['host-'+str(context)])
  if name in ('WS','WSs'):self.assertEqual(record['token_cap'],cap);self.assertEqual(record['summary']['token_cap'],cap)
  return record
 def test_every_window_context_and_summaries(self):
  for context in (4096,32768):
   for name in WINDOWS:
    for cap in ((64,128) if name in ('WS','WSs') else (64,)):
     with self.subTest(window=name,context=context,cap=cap):self.execute(name,context,cap)
 def test_compression_failure_preserves_pass(self):self.execute('K2',4096,compression_failure=True)
 def test_full_disk_during_summary_fails_without_latch(self):self.execute('K2',32768,summary_failure=True)
 def watch(self):
  with patch.object(w,'journal',return_value=('Fault response: historical','old-cursor')):watch=w.Watch(self.root,'boot',600)
  watch.mark_launched(123)
  return watch
 def test_latch_requires_new_fault_or_contacted_failed_owner(self):
  watch=self.watch();owner=self.root/'owner';owner.mkdir()
  error=pp.DeviceOwnerFailure('rank failed with exit 1',owner)
  with patch.object(w,'save') as saved:
   for reason in (ValueError('receipt failure'),OSError(errno.ENOSPC,'No space left on device'),error):watch.latch(reason)
   saved.assert_not_called()
   (owner/'device-contact.json').write_text('{"device_contact":true}')
   watch.latch(error);self.assertEqual(saved.call_count,1)
   (owner/'receipt.json').write_text('{"error":"write receipt: No space left on device"}')
   watch.latch(error);self.assertEqual(saved.call_count,1)
   (owner/'receipt.json').unlink();watch.cancelled=[15];watch.latch(error);self.assertEqual(saved.call_count,1)
   watch.new_gpu_fault=True;watch.latch(OSError('receipt failed'));self.assertEqual(saved.call_count,2)
 def test_old_fault_not_replayed(self):
  watch=self.watch()
  with patch.object(w,'journal',return_value=('', 'fresh')) as journal,patch.object(w,'save') as saved:
   watch.check();journal.assert_called_once_with('old-cursor');saved.assert_not_called()
 def test_missing_rssanon_exited_snapshot(self):
  from memory_gate import snapshot
  proc=self.root/'proc';p=proc/'123';(p/'fdinfo').mkdir(parents=True);(p/'status').write_text('Name: exited\n')
  self.assertEqual(snapshot(123,proc)['status'],[])
  self.assertTrue(snapshot(124,proc)['process_exited'])
 def test_ld_only_environment_and_affinity(self):
  affinity=os.sched_getaffinity(0);value='/literal path::relative/'
  self.assertEqual(environment_gate({'LD_LIBRARY_PATH':value})['native'],dict(LD_LIBRARY_PATH=value,OMP_NUM_THREADS='2'))
  self.assertEqual(os.sched_getaffinity(0),affinity)
 def test_fixture_launch_arguments_both_capacities(self):
  from types import SimpleNamespace
  for context in (4096,32768):
   for name in ('K0','K1a','K1b','K2'):
    with self.subTest(context=context,window=name):
     out=self.root/(name+str(context));out.mkdir();calls=[]
     class Child:
      returncode=0
      def __init__(self,pid):self.pid=pid
      def poll(self):return self.returncode
     class Watch:
      def check(self):pass
      def mark_launched(self,pid):pass
      def latch(self,error):raise AssertionError(error)
     def launch(argv,**kw):
      calls.append((argv,kw));dest=Path(argv[argv.index('--output')+1]);dest.mkdir()
      (dest/'receipt.json').write_text('{"passed":true}');(dest/'output.bin').write_bytes(b'fixture')
      return Child(100+len(calls))
     a=SimpleNamespace(window=name,card=1,context=context,seconds=None,dispatch=None)
     env={'LD_LIBRARY_PATH':'/literal::exact/','OMP_NUM_THREADS':'2'}
     with patch.object(w,'admit'),patch.object(w,'ldd_preflight'),patch.object(w,'sha',return_value='hash'),patch.object(w.subprocess,'Popen',side_effect=launch):
      result=w.run_fixtures(a,out,env,Watch())
     self.assertTrue(result)
     for argv,kw in calls:
      self.assertEqual(kw['env'],env)
      if any(x.endswith(('nongemv-fixtures','k2-fixtures')) for x in argv):self.assertEqual(argv[argv.index('--context')+1],str(context))
 def test_draft_two_fresh_owners_both_capacities(self):
  from types import SimpleNamespace
  for context in (4096,32768):
   with self.subTest(context=context):
    packet=self.root/str(context);packet.mkdir();builddir=packet/'build';builddir.mkdir();out=builddir/'out';out.mkdir()
    reference=builddir/'reference';(reference/'row-0').mkdir(parents=True);(reference/'row-0/logits.bf16').write_bytes(b'fixture')
    inp=packet/'input';inp.mkdir();(inp/'input.json').write_text('{"model_dir":"/model"}')
    (packet/f'capture-run-incident-retrospective-c{context}.json').write_text(json.dumps(dict(output=str(reference),binary_sha256='hash',table_sha256='hash')))
    (packet/'capture-input-incident-retrospective.json').write_text(json.dumps(dict(table_sha256='hash',streams={})))
    build=dict(artifacts_sha256={'gnu-host/own-rt-iq3':'hash'},draft_capture_fixture_sha256_by_context={str(context):{'row-0/logits.bf16':'hash'}},draft_capture_input_sha256={'incident-retrospective':'hash'})
    a=SimpleNamespace(input=inp,context=context,card=1,dispatch=packet/'dispatch.json');calls=[]
    class Child:
     returncode=0
     def __init__(self,pid):self.pid=pid
     def poll(self):return self.returncode
    class Watch:
     last=0
     def check(self):pass
     def mark_launched(self,pid):pass
     def latch(self,error):raise AssertionError(error)
    def launch(argv,**kw):
     calls.append((argv,kw));dest=Path(argv[argv.index('--output')+1]);(dest/'row-0').mkdir(parents=True)
     (dest/'row-0/logits.bf16').write_bytes(b'fixture')
     (dest/'receipt.json').write_text(json.dumps(dict(passed=True,device_executed=True,teardown=[dict(safe_to_exit=True,in_flight=0,live_bytes=0)])))
     return Child(100+len(calls))
    env={'LD_LIBRARY_PATH':'/literal::exact/','OMP_NUM_THREADS':'2'}
    import fixture_support
    with patch.object(dw,'P',packet),patch.object(dw,'B',builddir),patch.object(dw,'sha',return_value='hash'),patch.object(dw,'admit'),patch.object(fixture_support,'ldd_preflight'),patch.object(dw.subprocess,'Popen',side_effect=launch),patch.object(dw,'compress_completed_log',side_effect=OSError(errno.ENOSPC,'No space left on device')):
     receipts,pids=dw.run(a,out,env,Watch(),build)
    self.assertEqual(len(set(pids)),2);self.assertEqual(len(receipts),6)
    for argv,kw in calls:
     self.assertEqual(argv[argv.index('--context')+1],str(context));self.assertEqual(argv[argv.index('--card')+1],'2');self.assertEqual(kw['env'],env)
    for i in (0,1):
     self.assertTrue((out/f'owner{i}.log').exists());self.assertTrue((out/f'owner{i}-retention-errors.json').exists())
 def test_storage_floor_and_six_gb_cap(self):
  import storage
  from types import SimpleNamespace
  with patch.object(storage,'build_size',return_value=5_999_999_999),patch.object(storage.subprocess,'run',return_value=SimpleNamespace(stdout='Filesystem Size Used Avail\nx 1 1 9000000000\n')):
   storage.admit(0)
   with self.assertRaises(RuntimeError):storage.admit(1)
  with patch.object(storage,'build_size',return_value=0),patch.object(storage.subprocess,'run',return_value=SimpleNamespace(stdout='Filesystem Size Used Avail\nx 1 1 7999999999\n')):
   with self.assertRaises(RuntimeError):storage.admit(0)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContextWindows))
 (w.P/'context-window-gates.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,window_cases=22,device_executed=False,scope='mocked orchestration including summaries; no native binaries/device calls'),indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
