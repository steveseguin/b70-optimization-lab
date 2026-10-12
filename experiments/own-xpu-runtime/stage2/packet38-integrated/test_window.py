"""CPU-only admission tests and host profiling gate; no device execution."""
import json,tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
import window as w
from window_safety import environment_gate,memory_snapshot
class Gate(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=w.B,prefix="window-tests-");self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def identity(self):return dict(boot_id="boot",artifacts_sha256={"binary":"hash"},environment={"native":{}},card=1,build_receipt_sha256="build")
 def receipt(self):
  child=self.root/'receipt.json';child.write_text('{}')
  row=dict(self.identity(),window='K0',passed=True,receipts={'receipt.json':w.sha(child)})
  path=self.root/'window.json';path.write_text(json.dumps(row));return path,row
 def test_watchdogs(self):
  for name,(estimate,_) in w.CONFIG.items():
   self.assertGreaterEqual(w.watchdog(name),max(300,4*(estimate+17)))
   with self.assertRaises(ValueError):w.watchdog(name,299)
 def test_expected_budget_refuses_before_launch(self):
  from unittest.mock import patch
  with patch.dict(w.CONFIG,{'K2':(3000,10800)}):
   with self.assertRaisesRegex(ValueError,'quarter'):w.watchdog('K2')
  with self.assertRaises(ValueError):w.watchdog('K2',0)
  self.assertEqual(w.CONFIG['K2'][0],6*216+300)

 def test_prerequisite(self):
  path,_=self.receipt();w.prerequisites(path,'K0',self.identity())
 def test_prerequisite_identity(self):
  path,row=self.receipt()
  for field in ('boot_id','artifacts_sha256','environment','card','build_receipt_sha256'):
   with self.assertRaises(ValueError):w.prerequisites(path,'K0',dict(self.identity(),**{field:'changed'}))
 def test_prerequisite_bytes(self):
  path,_=self.receipt();(self.root/'receipt.json').write_text('changed')
  with self.assertRaises(ValueError):w.prerequisites(path,'K0',self.identity())
 def test_missing_prerequisite(self):
  with self.assertRaises(ValueError):w.prerequisites(None,'K0',self.identity())
 def test_failed_prerequisite(self):
  path,row=self.receipt();row['passed']=False;path.write_text(json.dumps(row))
  with self.assertRaises(ValueError):w.prerequisites(path,'K0',self.identity())
 def test_wrong_window(self):
  path,_=self.receipt()
  with self.assertRaises(ValueError):w.prerequisites(path,'W0p',self.identity())
 def test_closed_environment(self):
  for key in ('NEOReadDebugKeys','OverrideDefaultFP64Settings','UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS','LD_PRELOAD'):
   with self.assertRaises(ValueError):environment_gate({key:''})
 def test_masks_refused(self):
  for key in ('ONEAPI_DEVICE_SELECTOR','ZE_AFFINITY_MASK','SYCL_DEVICE_FILTER'):
   with self.assertRaises(ValueError):environment_gate({key:'0'})
 def test_native_allowlist(self):
  e=environment_gate(dict(PATH='/usr/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/runtime',CODEX_TEST='hidden',USER='steve'))
  self.assertEqual(e['native'],dict(PATH='/usr/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/runtime'))
 def test_memory_bytes(self):
  p=self.root/'meminfo';p.write_text('MemAvailable: 100 kB\n')
  self.assertEqual(memory_snapshot(p)['MemAvailable'],102400)
 def test_memory_missing(self):
  p=self.root/'meminfo';p.write_text('')
  with self.assertRaises(ValueError):memory_snapshot(p)
 def engine(self,n):
  p=self.root/'123/fdinfo/4';p.parent.mkdir(parents=True,exist_ok=True)
  p.write_text(f'drm-pdev: 0000:01:00.0\ndrm-client-id: 2\ndrm-engine-compute: {n} ns\n')
 def test_foreign_idle(self):
  self.engine(4)
  with patch.object(w.time,'sleep'):self.assertEqual(w.foreign_engines(self.root)['active'],[])
 def test_foreign_active(self):
  self.engine(4)
  with patch.object(w.time,'sleep',side_effect=lambda _:self.engine(5)):
   with self.assertRaisesRegex(ValueError,'foreign engine'):w.foreign_engines(self.root)
 def test_ldd_only(self):
  calls=[]
  def runner(cmd,**kwargs):calls.append(cmd);return type('R',(),dict(returncode=0,stdout='libraries found',stderr=''))()
  w.ldd_preflight(Path('/never-execute'),runner)
  self.assertEqual(calls[0][-2:],['ldd','/never-execute'])
 def test_ldd_missing(self):
  def runner(*args,**kwargs):return type('R',(),dict(returncode=0,stdout='library not found',stderr=''))()
  with self.assertRaises(ValueError):w.ldd_preflight(Path('/never-execute'),runner)
 def test_fault_signatures(self):
  for line in ('Fault response','Engine memory CAT error','engine reset','timed-out job','devcoredump'):
   self.assertTrue(w.FAULT.search(line))
  self.assertFalse(w.FAULT.search('ordinary filesystem change'))
 def test_watch_latches_fault(self):
  with patch.object(w,'journal',return_value=('',1)):watch=w.Watch(self.root,'boot',600)
  watch.mark_launched(123)
  with patch.object(w,'journal',return_value=('Fault response',2)),patch.object(w,'save') as save:
   with self.assertRaises(ValueError):watch.check()
   self.assertEqual(save.call_args.args[1]['boot_id'],'boot')
 def test_prelaunch_refusal_never_latches(self):
  with patch.object(w,'journal',return_value=('', 'initial')):watch=w.Watch(self.root,'boot',600)
  with patch.object(w,'save') as saved:
   watch.latch('ldd refused before first launch');saved.assert_not_called()
  with patch.object(w,'journal',return_value=('Fault response', 'fresh')),patch.object(w,'save') as saved:
   with self.assertRaisesRegex(ValueError,'GPU fault'):watch.check()
   saved.assert_not_called()
 def test_reviewed_historical_fault_not_replayed(self):
  with patch.object(w,'journal',return_value=('Fault response: old reviewed incident', 'own-boundary')) as initial:
   watch=w.Watch(self.root,'boot',600)
  watch.mark_launched(123)
  with patch.object(w,'journal',return_value=('', 'new-boundary')) as fresh,patch.object(w,'save') as saved:
   watch.check();fresh.assert_called_once_with('own-boundary');saved.assert_not_called()
  self.assertEqual(watch.cursor,'new-boundary')
  self.assertIn('old reviewed incident',(self.root/'kernel-preflight.txt').read_text())
 def test_library_path_exact_bytes(self):
  value='/coordinator/a::/coordinator b/:relative/'
  e=environment_gate(dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=value))
  self.assertEqual(e['native']['LD_LIBRARY_PATH'],value)
 def test_pipeline_rank_arguments_environment_and_affinity(self):
  import pipeline as pp
  a=pp.parser().parse_args(['--output',str(self.root),'--mini','--host-path','legacy','--argument-audit','--audit-prepare-each'])
  launches=[]
  class Child:
   pid=123
  def child(argv,**kwargs):launches.append((argv,kwargs));return Child()
  affinity=set(os.sched_getaffinity(0));library='/coordinator/a::/coordinator b/'
  t=pp.Transport.__new__(pp.Transport)
  try:
   with patch.object(pp.subprocess,'Popen',side_effect=child),patch.object(pp.Transport,'receive'),patch.dict(os.environ,{'LD_LIBRARY_PATH':library}):
    t.__init__(a,self.root,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':library})
   self.assertEqual(len(launches),2)
   for rank,(argv,kw) in enumerate(launches):
    self.assertEqual(argv[argv.index('--card')+1],str(a.card+rank))
    self.assertEqual(argv[argv.index('--host-path')+1],'legacy')
    self.assertIn('--argument-audit',argv);self.assertIn('--audit-prepare-each',argv)
    self.assertEqual(kw['env']['LD_LIBRARY_PATH'],library)
    record=json.loads((self.root/f'rank{rank}-launch.json').read_text())
    self.assertEqual(record['cpu_affinity'],sorted(affinity));json.dumps(record)
   self.assertEqual(os.sched_getaffinity(0),affinity)
  finally:
   if hasattr(t,'mapping'):t.mapping.close()
   if hasattr(t,'stop_read'):os.close(t.stop_read);os.close(t.stop_write)
   for sock in getattr(t,'sockets',[]):sock.close()
   for log in getattr(t,'logs',[]):log.close()
 def test_changed_library_path_refused(self):
  import pipeline as pp
  a=pp.parser().parse_args(['--output',str(self.root),'--mini'])
  t=pp.Transport.__new__(pp.Transport)
  try:
   with patch.dict(os.environ,{'LD_LIBRARY_PATH':'/actual'}),patch.object(pp.subprocess,'Popen') as child:
    with self.assertRaisesRegex(ValueError,'LD_LIBRARY_PATH changed'):t.__init__(a,self.root,{'LD_LIBRARY_PATH':'/different'})
    child.assert_not_called()
  finally:
   if hasattr(t,'mapping'):t.mapping.close()
   if hasattr(t,'stop_read'):os.close(t.stop_read);os.close(t.stop_write)
 def linked_receipt(self):
  root=self.root/'linked';root.mkdir();(root/'output.bin').write_bytes(b'fixture-bytes')
  digest=w.sha(root/'output.bin')
  row=dict(schema='packet37.p33-linked-fixtures.v1',passed=True,device_executed=True,reference_exact=True,checks=216,type_k_families=18,split_instantiations=36,modes_per_instantiation=6,output_rows=1512,argument_limit_bytes=1024,owner_cards=1,card=1,output_sha256=digest,teardown=dict(safe_to_exit=True,exit_code=0,live_bytes=0,in_flight=0))
  (root/'receipt.json').write_text(json.dumps(row))
  build=dict(artifacts_sha256={'device/p33-linked-fixtures':'binaryhash'},p33_linked_fixture_host_sha256=digest)
  return root,row,build
 def test_linked_fixture_gate(self):
  root,row,build=self.linked_receipt();gate=w.linked_fixture_gate(root,build,1)
  self.assertEqual(gate['checks'],216);self.assertEqual(gate['binary_sha256'],'binaryhash')
 def test_linked_fixture_coverage_refused(self):
  root,row,build=self.linked_receipt()
  for key,value in (('checks',215),('split_instantiations',35),('type_k_families',17),('modes_per_instantiation',5),('output_rows',1511),('argument_limit_bytes',2048),('owner_cards',2),('reference_exact',False),('device_executed',False),('passed',False)):
   altered=dict(row,**{key:value});(root/'receipt.json').write_text(json.dumps(altered))
   with self.assertRaises(ValueError):w.linked_fixture_gate(root,build,1)
 def test_linked_fixture_teardown_refused(self):
  root,row,build=self.linked_receipt()
  for key,value in (('safe_to_exit',False),('live_bytes',1),('in_flight',1),('exit_code',1)):
   altered=dict(row,teardown=dict(row['teardown'],**{key:value}));(root/'receipt.json').write_text(json.dumps(altered))
   with self.assertRaises(ValueError):w.linked_fixture_gate(root,build,1)
 def test_linked_fixture_output_and_host_binding(self):
  root,row,build=self.linked_receipt()
  with self.assertRaises(ValueError):w.linked_fixture_gate(root,dict(build,p33_linked_fixture_host_sha256='wrong'),1)
  (root/'output.bin').write_bytes(b'changed')
  with self.assertRaises(ValueError):w.linked_fixture_gate(root,build,1)
 def test_fresh_k1_owners(self):
  w.fresh_k1_owners({'pids':[1,2]},{'pids':[3,4]})
  for pids in ([1,3],[3,3],[3],['3',4]):
   with self.assertRaises(ValueError):w.fresh_k1_owners({'pids':[1,2]},{'pids':pids})
 def test_k1_launches_linked_after_first_exit(self):
  from types import SimpleNamespace
  build=self.root/'build';(build/'device').mkdir(parents=True)
  for name in ('nongemv-fixtures','p33-linked-fixtures'):(build/'device'/name).write_bytes(name.encode())
  out=self.root/'window';out.mkdir();calls=[];children=[]
  class Child:
   returncode=0
   def __init__(self,pid):self.pid=pid
   def poll(self):return self.returncode
  class Watch:
   def check(self):pass
   def mark_launched(self,pid):pass
   def latch(self,error):raise AssertionError(error)
  def launch(argv,**kwargs):
   self.assertTrue(all(child.poll()==0 for child in children))
   calls.append((argv,kwargs));child=Child(100+len(children));children.append(child)
   dest=Path(argv[argv.index('--output')+1]);dest.mkdir();(dest/'receipt.json').write_text('{"passed":true}');(dest/'output.bin').write_bytes(b'bytes')
   return child
  a=SimpleNamespace(window='K1a',card=1,seconds=None,dispatch=Path('/candidate.json'))
  env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':'/coordinator::exact/'}
  with patch.object(w,'admit'),patch.object(w,'B',build),patch.object(w,'ldd_preflight'),patch.object(w.subprocess,'Popen',side_effect=launch):receipts=w.run_fixtures(a,out,env,Watch())
  self.assertEqual(len(calls),2)
  for argv,kw in calls:
   self.assertEqual(argv[argv.index('--card')+1],'1');self.assertIn('--stop-fd',argv);self.assertEqual(kw['env'],env)
  self.assertIn('--dispatch',calls[0][0]);self.assertNotIn('--dispatch',calls[1][0]);self.assertIn('--seconds',calls[1][0])
  self.assertEqual(set(receipts),{'run0/receipt.json','linked/receipt.json','linked/output.bin'})
  entries=json.loads((out/'children.json').read_text())['entries']
  self.assertEqual([e['binary'] for e in entries],['nongemv-fixtures','p33-linked-fixtures']);json.dumps(entries)
 def test_second_fixture_loader_refusal_is_prelaunch(self):
  from types import SimpleNamespace
  out=self.root/'window';out.mkdir()
  a=SimpleNamespace(window='K1a',card=0,seconds=None,dispatch=None)
  with patch.object(w,'journal',return_value=('', 'boundary')):watch=w.Watch(out,'boot',10800)
  with patch.object(w,'admit'),patch.object(w,'B',self.root),patch.object(w,'ldd_preflight',side_effect=[None,ValueError('second loader refused')]),patch.object(w.subprocess,'Popen') as launch,patch.object(w,'journal',return_value=('', 'next')):
   with self.assertRaisesRegex(ValueError,'second loader refused'):w.run_fixtures(a,out,{},watch)
   launch.assert_not_called();self.assertEqual(watch.launched,[]);self.assertFalse((self.root/'FAULT.json').exists())
 def test_k0_no_execution(self):
  text=(w.P/'jit_smoke.cpp').read_text();self.assertIn('sycl::build(input,{d})',text)
  for token in ('.parallel_for(','.submit(','.single_task(','sycl::malloc_','sycl::queue '):self.assertNotIn(token,text)
 def test_class_diagnostic_contract(self):
  import pipeline
  from cpu_gates import host
  binary=w.B/'gnu-host/own-rt-iq3';host(binary)
  out=self.root/'class-run'
  args=pipeline.parser().parse_args(['--binary',str(binary),'--output',str(out),'--mini','--tokens','2','--timing','class'])
  result=pipeline.run(args)
  self.assertTrue(result['diagnostic']);self.assertIsNone(result['decode_tok_s'])
  self.assertEqual(len(result['decode_rank_metrics']),2)
  for rank in (0,1):
   profile=json.loads((out/f'rank{rank}/class-times.json').read_text())
   self.assertIn('rejected and redone',profile['scope'])
   row=result['decode_rank_metrics'][rank]
   self.assertAlmostEqual(row['busy_ms']+row['idle_and_coordination_ms'],result['decode_wall_ms'],places=5)
 def test_memory_margin(self):
  from memory_gate import check
  ledger=dict(capacity_bytes=34_242_297_856,minimum_free_bytes=1_500_000_000,rank1_total_bytes=31_201_069_770)
  def census(n):return dict(totals={'device':n},allocations=[dict(bytes=n,live=True,memory='device')])
  self.assertTrue(check(census(31_201_069_770),ledger,1,True)['passed'])
  for n in (31_201_069_771,33_000_000_000):
   with self.assertRaises(ValueError):check(census(n),ledger,1,True)
  with self.assertRaises(ValueError):check(census(33_000_000_000),ledger,0)
 def test_ready_memory_snapshot(self):
  from memory_gate import snapshot
  d=self.root/'4321';(d/'fdinfo').mkdir(parents=True)
  (d/'status').write_text('Name: test\nVmRSS: 12 kB\nRssAnon: 7 kB\nCpus_allowed_list: 4-15\n')
  (d/'fdinfo/7').write_text('pos: 0\ndrm-pdev: card\ndrm-resident-vram: 99 KiB\n')
  row=snapshot(4321,self.root)
  self.assertEqual(len(row['status']),3);self.assertEqual(len(row['drm_fdinfo']['7']),2)
  self.assertIn('including draft load',row['phase'])
 def test_poll_after_deadline(self):
  with patch.object(w,'journal',return_value=('',1)):watch=w.Watch(self.root,'boot',600)
  watch.end=0;watch.cancelled=[15];watch.mark_launched(123)
  with patch.object(w,'journal',return_value=('Fault response',2)),patch.object(w,'save') as save:
   with self.assertRaisesRegex(ValueError,'GPU fault'):watch.poll_kernel()
   self.assertTrue(save.called)
 def test_guard(self):self.assertIn('sizeof(F)<=1024',(w.P/'kernel_guard.hpp').read_text())
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Gate))
 (w.P/'window-tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,device_executed=False),indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
