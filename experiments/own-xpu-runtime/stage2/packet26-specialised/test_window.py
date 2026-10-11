#!/usr/bin/env python3
"""CPU-only protocol tests; device processes and journals are fake."""
import io
import json
from pathlib import Path
import signal
import tempfile
import unittest
import window as w
from k2_summary import aggregate

class Clock:
 def __init__(self):self.t=0
 def now(self):return self.t
 def sleep(self,s):self.t+=s
class Child:
 def __init__(self,clock,end=None,stop=True):self.clock=clock;self.end=end;self.stop=stop;self.signals=[];self.returncode=None
 def poll(self):
  if self.end is not None and self.clock.t>=self.end:self.returncode=0
  return self.returncode
 def send_signal(self,s):
  self.signals.append(s)
  if self.stop:self.returncode=-s
class Windows(unittest.TestCase):
 def setUp(self):
  (w.HERE/'build').mkdir(exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(dir=w.HERE/'build',prefix='window-test-');self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def write(self,path,row):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(row))
 def watch(self,child,clock,seconds=1,journal=lambda _:('','cursor')):
  requested=[];latched=[]
  result=w.supervise(child,seconds,'cursor',io.StringIO(),latched.append,lambda:None,requested,journal=journal,now=clock.now,sleep=clock.sleep,drain_seconds=2)
  return result,requested,latched
 def identity(self):return dict(boot_id='boot',artifacts_sha256={'device/model':'hash'},environment={})
 def receipt(self,name):
  root=self.root/name;native=root/'run/receipt.json';self.write(native,dict(passed=True))
  row=dict(self.identity(),schema=w.SCHEMA,window=name,passed=True,card=0,cards=2,native_receipt_sha256=w.sha(native))
  path=root/'window.json';self.write(path,row);return path,row
 def test_deadlines(self):
  for name in w.CONFIG:
   seconds=w.watchdog_seconds(name);r=w.deadline_record(name,seconds)
   self.assertGreaterEqual(seconds,300);self.assertGreaterEqual(seconds,4*r['expected_total_seconds']);self.assertFalse(r['expectation_enforced'])
   with self.assertRaises(ValueError):w.watchdog_seconds(name,299)
 def test_deadline_sigterm_once(self):
  c=Clock();p=Child(c);r,stop,_=self.watch(p,c)
  self.assertEqual(p.signals,[signal.SIGTERM]);self.assertIn('window deadline',stop);self.assertFalse(r['child_still_running'])
 def test_stuck_child_retained(self):
  c=Clock();p=Child(c,stop=False);r,_,_=self.watch(p,c)
  self.assertEqual(p.signals,[signal.SIGTERM]);self.assertTrue(r['child_still_running']);self.assertLessEqual(c.t,3.25)
 def test_fault_sigterm_once(self):
  c=Clock();p=Child(c);_,stop,_=self.watch(p,c,journal=lambda _:('xe Fault response','cursor'))
  self.assertEqual(p.signals,[signal.SIGTERM]);self.assertIn('new GPU fault signature',stop)
 def test_journal_failure_stops(self):
  def fail(_):raise RuntimeError('unavailable')
  c=Clock();p=Child(c);self.watch(p,c,journal=fail);self.assertEqual(p.signals,[signal.SIGTERM])
 def test_success_does_not_signal(self):
  c=Clock();p=Child(c,end=.5);r,stop,latch=self.watch(p,c,2)
  self.assertFalse(stop or latch or p.signals);self.assertEqual(r['returncode'],0)
 def test_expected_duration_does_not_signal(self):
  c=Clock();p=Child(c,end=95);self.watch(p,c,600);self.assertFalse(p.signals)
 def test_fault_signatures_specific(self):
  for x in ('Fault response','CAT error','engine reset','device coredump','timed out job'):self.assertRegex(x,w.p2.FAULT)
  self.assertNotRegex('ordinary change',w.p2.FAULT)
 def test_environment_unknown_even_empty(self):
  for key in ('NEOReadDebugKeys','EnableDeferBacking','FutureDriverKnob'):
   for value in ('','0','1'):
    with self.assertRaises(ValueError):w.environment_gate({'OMP_NUM_THREADS':'2',key:value})
 def test_environment_no_secret_forwarding(self):
  row=w.environment_gate({'OMP_NUM_THREADS':'2','PATH':'/bin','CODEX_TOKEN':'secret'})
  self.assertNotIn('secret',json.dumps(row));self.assertEqual(row['native'],{'OMP_NUM_THREADS':'2','PATH':'/bin'})
 def test_environment_mask_refused(self):
  for k in ('ZE_AFFINITY_MASK','ONEAPI_DEVICE_SELECTOR','SYCL_DEVICE_FILTER'):
   with self.assertRaises(ValueError):w.environment_gate({k:'1'})
 def test_k0_requires_matching_boot_binary_env(self):
  path,row=self.receipt('K0')
  w.k0_gate(path,self.identity(),dict(card=1,cards=1))
  for key in ('boot_id','artifacts_sha256','environment'):
   changed=dict(self.identity());changed[key]='wrong'
   with self.assertRaises(ValueError):w.k0_gate(path,changed,dict(card=1,cards=1))
 def test_k0_card_coverage(self):
  path,_=self.receipt('K0')
  with self.assertRaisesRegex(ValueError,'missing admitted card'):w.k0_gate(path,self.identity(),dict(card=2,cards=1))
 def test_native_receipt_hash_bound(self):
  path,_=self.receipt('K0');self.write(path.parent/'run/receipt.json',dict(passed=True,changed=True))
  with self.assertRaises(ValueError):w.k0_gate(path,self.identity(),dict(card=0,cards=1))
 def test_missing_prerequisite(self):
  with self.assertRaisesRegex(ValueError,'missing --w0'):w.prerequisite(None,'W0',self.identity())
 def test_k0_builds_only(self):
  text=(w.HERE/'jit_smoke.cpp').read_text();self.assertIn('sycl::build(input,{d})',text)
  for token in ('.parallel_for(','.submit(','.single_task(','sycl::malloc_','sycl::queue '):self.assertNotIn(token,text)
 def test_capture_guard_no_indirection(self):
  text=(w.HERE/'kernel_guard.hpp').read_text();self.assertIn('sizeof(F)<=1024',text)
  for token in ('submission_parameters','parameters('):self.assertNotIn(token,text)
 def test_failure_saved_before_shutdown(self):
  text=(w.HERE/'failure.hpp').read_text();self.assertLess(text.index('write(snapshot'),text.index('d.shutdown'))
  self.assertIn('if(r.in_flight)',text)
 def test_model_commands_are_unfused(self):
  for name in ('W1','W2','W2m','W2c'):
   cfg=dict(w.CONFIG[name],card=0);cmd=w.native_command(Path('/binary'),cfg,Path('/input'),'/weights',Path('/oracle'),Path('/out'),10800)
   self.assertNotIn('--fusion',cmd);self.assertNotIn('--kernels',cmd);self.assertEqual(cmd[cmd.index('--gemv')+1],'r5')
   self.assertEqual(cmd[cmd.index('--timing')+1],'class' if name=='W2c' else 'token')
 def test_dispatch_command(self):
  cmd=w.native_command(Path('/binary'),dict(w.CONFIG['W2m'],card=0),Path('/input'),'/weights',Path('/oracle'),Path('/out'),10800,Path('/dispatch'))
  self.assertEqual(cmd[cmd.index('--dispatch')+1],'/dispatch')
 def test_w1_optional_source(self):
  text=(w.HERE/'window.py').read_text();self.assertIn('if a.w1 is not None:',text)
  self.assertNotIn('w1_gate(a.w1',text)
 def test_token_phase_fields_enforced(self):
  import inspect
  source=inspect.getsource(w.compare_run)
  for name in ('prepare_ms','enqueue_loop_ms','wait_ms'):self.assertIn(name,source)
 def model_receipt(self,timing='token'):
  cfg=dict(w.CONFIG['W1'],count=2,steps=0,timing=timing)
  row=dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,device_executed=True,arithmetic=w.AUTHORITY,owner_cards=1,context=256,timing=timing,nongemv='parallel',gemv='r5',memory_mode='layer-streaming',tokens=[1,2],decode_tokens=1,decode_wall_ms=100,decode_tok_s=10,submission_budget_measured=timing!='token',submission_budget_ns=4000000000,max_submission_ns=1000,teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0)])
  self.write(self.root/'run/receipt.json',row)
  rows=[dict(kind='generated_token',generated_index=i+1,token_id=i+1,wall_ms=100,prepare_ms=1,enqueue_loop_ms=5,wait_ms=94,kernel_submissions=2181,host_waits=16) for i in range(2)]
  (self.root/'run/timings.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
  self.write(self.root/'run/class-times.json',dict(profiling=True,tokens=1,classes={'route':1}))
  return cfg,row
 def test_real_native_model_schema(self):
  cfg,row=self.model_receipt();result={};w.compare_run(self.root,cfg,{},[1,2],None,result)
  self.assertTrue(result['oracle_exact']);self.assertEqual(result['decode_tok_s'],10)
 def test_class_profile_has_no_speed_claim(self):
  cfg,row=self.model_receipt('class');result={};w.compare_run(self.root,cfg,{},[1,2],None,result)
  self.assertIsNone(result['decode_tok_s'])
 def test_missing_phase_refused(self):
  cfg,row=self.model_receipt();path=self.root/'run/timings.jsonl';rows=[json.loads(x) for x in path.read_text().splitlines()];del rows[0]['enqueue_loop_ms'];path.write_text('\n'.join(json.dumps(r) for r in rows))
  with self.assertRaisesRegex(ValueError,'token phase'):w.compare_run(self.root,cfg,{},[1,2],None,{})
 def test_profile_budget_refused(self):
  cfg,row=self.model_receipt('class');row['max_submission_ns']=4000000001;self.write(self.root/'run/receipt.json',row)
  with self.assertRaisesRegex(ValueError,'submission budget'):w.compare_run(self.root,cfg,{},[1,2],None,{})
 def test_model_wrong_arithmetic_refused(self):
  cfg,row=self.model_receipt();row['arithmetic']='old';self.write(self.root/'run/receipt.json',row)
  with self.assertRaisesRegex(ValueError,'identity'):w.compare_run(self.root,cfg,{},[1,2],None,{})
 def test_ldd_not_device_execution(self):
  calls=[]
  def runner(cmd,**kwargs):calls.append(cmd);return type('Result',(),dict(returncode=0,stdout='lib present',stderr=''))()
  w.ldd_preflight(Path('/never/execute'),runner);self.assertEqual(calls,[w.helper_command(['ldd','/never/execute'])])
 def test_ldd_failure(self):
  def runner(*a,**kw):return type('Result',(),dict(returncode=0,stdout='not found',stderr=''))()
  with self.assertRaises(ValueError):w.ldd_preflight(Path('/never/execute'),runner)
 def test_safe_teardown(self):
  base=dict(owner_cards=2,teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0)])
  self.assertTrue(w.safe_teardown(base,2));base['teardown'][0]['in_flight']=1;self.assertFalse(w.safe_teardown(base,2))
 def test_memory_snapshot(self):
  p=self.root/'meminfo';p.write_text('MemAvailable: 100 kB\nGPUActive: 20 kB\n')
  self.assertEqual(w.memory_snapshot(p)['MemAvailable'],102400);self.assertEqual(w.memory_snapshot(p)['GPUActive'],20480)
 def fixture(self,name,pid):
  path,row=self.receipt(name);root=path.parent/'run';(root/'output.bin').write_bytes(b'fixture')
  native=dict(schema='packet26.fixtures.v1',passed=True,device_executed=True,reference_exact=True,packet18_exact=True,fixtures=72,odd_lengths=20,ties=1,nan_routes=1,owner_cards=1,max_submission_ns=1000,output_sha256=w.sha(root/'output.bin'),teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0) for _ in range(3)])
  self.write(root/'receipt.json',native);row.update(pid=pid,card=0,cards=1,native_receipt_sha256=w.sha(root/'receipt.json'));self.write(path,row)
  return path,row,dict(nongemv_fixture_host_sha256=native['output_sha256'])
 def test_fixtures_bytes_bound(self):
  path,row,build=self.fixture('K1a',1);w.fixture_receipt_gate(path.parent/'run',build)
  (path.parent/'run/output.bin').write_bytes(b'changed')
  with self.assertRaises(ValueError):w.fixture_receipt_gate(path.parent/'run',build)
 def test_fixture_edge_coverage_required(self):
  path,row,build=self.fixture('K1a',1);p=path.parent/'run/receipt.json';native=w.read(p)
  for key in ('odd_lengths','ties','nan_routes'):
   self.write(p,dict(native,**{key:0}))
   with self.assertRaises(ValueError):w.fixture_receipt_gate(path.parent/'run',build)
 def test_fixture_submission_budget(self):
  path,row,build=self.fixture('K1a',1);p=path.parent/'run/receipt.json';native=w.read(p);native['max_submission_ns']=4e9;self.write(p,native)
  with self.assertRaises(ValueError):w.fixture_receipt_gate(path.parent/'run',build)
 def test_two_fresh_owners(self):
  first,_,build=self.fixture('K1a',1);second,row,_=self.fixture('K1b',2);row['k1a_sha256']=w.sha(first);self.write(second,row)
  w.k1_gate(first,second,self.identity(),build)
  row['pid']=1;self.write(second,row)
  with self.assertRaises(ValueError):w.k1_gate(first,second,self.identity(),build)
 def test_sequential_owner_coverage(self):
  row=dict(owner_cards=1,teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0) for _ in range(3)])
  self.assertTrue(w.sequential_teardown(row,3));self.assertFalse(w.sequential_teardown(row,2))
  row['teardown'][2]['in_flight']=1;self.assertFalse(w.sequential_teardown(row,3))
 def test_k1_candidate_identity_bound(self):
  first,a,build=self.fixture('K1a',1);second,b,_=self.fixture('K1b',2)
  a['candidate_dispatch_sha256']='candidate-a';self.write(first,a)
  b.update(candidate_dispatch_sha256='candidate-b',k1a_sha256=w.sha(first));self.write(second,b)
  with self.assertRaisesRegex(ValueError,'candidate dispatch changed'):w.k1_gate(first,second,self.identity(),build)
 def test_k2_dispatch_bound(self):
  p,row=self.receipt('K2');root=p.parent/'run'
  for name in ('events.jsonl','summary.json','dispatch-measured.json'):(root/name).write_text('{}')
  row.update(dispatch_sha256=w.sha(root/'dispatch-measured.json'),events_sha256=w.sha(root/'events.jsonl'),summary_sha256=w.sha(root/'summary.json'));self.write(p,row)
  w.k2_gate(p,self.identity(),root/'dispatch-measured.json');(root/'dispatch-measured.json').write_text('{"changed":true}')
  with self.assertRaises(ValueError):w.k2_gate(p,self.identity(),root/'dispatch-measured.json')

class Priority(unittest.TestCase):
 def test_priorities(self):
  from unittest.mock import patch
  for actual in (0,7,19):
   with patch.object(w.os,'getpriority',return_value=actual), patch.dict(w.os.environ,{'OMP_NUM_THREADS':'2'}):
    self.assertEqual(w.priority_gate(actual),dict(wrapper_nice=actual,native_nice=actual,helper_nice=19))
    for requested in (0,19):
     if actual!=requested:
      with self.assertRaisesRegex(ValueError,'must equal'):w.priority_gate(requested)
 def test_cpu_helpers_are_idle(self):
  from unittest.mock import patch
  with patch.object(w.subprocess,'check_output',return_value='abc  file\n') as run:
   self.assertEqual(w.sha(Path('/file')),'abc');self.assertEqual(run.call_args.args[0][:6],['nice','-n','19','ionice','-c','3'])
  result=type('Result',(),dict(returncode=0,stdout='hello\n-- cursor: end\n',stderr=''))()
  with patch.object(w.subprocess,'run',return_value=result) as run:
   self.assertEqual(w.journal(),('hello\n','end'));self.assertEqual(run.call_args.args[0][:6],['nice','-n','19','ionice','-c','3'])

class K2Summary(unittest.TestCase):
 def rows(self,new=80):return [dict(**{'class':'norm'},variant=v,repetition=i,start_ns=100,end_ns=100+(100 if v=='packet18' else new),exact=True) for v in ('packet18','specialised') for i in range(200)]
 def test_faster_exact_selected(self):
  r=aggregate(self.rows(),['norm']);self.assertTrue(r['passed']);self.assertEqual(r['selection']['norm'],'specialised')
 def test_exact_ten_percent_not_selected(self):self.assertEqual(aggregate(self.rows(90),['norm'])['selection']['norm'],'packet18')
 def test_slower_stays_reference(self):self.assertEqual(aggregate(self.rows(110),['norm'])['selection']['norm'],'packet18')
 def test_one_percent_bad_allowed(self):
  rows=self.rows()
  for r in rows[:4]:r['end_ns']=r['start_ns']
  out=aggregate(rows,['norm']);self.assertTrue(out['passed']);self.assertEqual(out['invalid_duration_rows'],4)
 def test_more_than_one_percent_bad_fails(self):
  rows=self.rows()
  for r in rows[:5]:r['end_ns']=r['start_ns']-1
  self.assertFalse(aggregate(rows,['norm'])['passed'])
 def test_nan_duration_counted(self):
  rows=self.rows();rows[0]['end_ns']=float('nan');self.assertEqual(aggregate(rows,['norm'])['invalid_duration_rows'],1)
 def test_nonexact_fails(self):
  rows=self.rows();rows[0]['exact']=False;self.assertFalse(aggregate(rows,['norm'])['passed'])
 def test_missing_repetition_fails(self):self.assertFalse(aggregate(self.rows()[:-1],['norm'])['passed'])
 def test_missing_class_fails(self):self.assertFalse(aggregate(self.rows(),['norm','route'])['passed'])
 def test_budget_fails(self):
  rows=self.rows();rows[0]['end_ns']=5e9;self.assertFalse(aggregate(rows,['norm'])['passed'])
 def test_partial_repetition_excluded(self):
  rows=self.rows();rows.append(dict(rows[0],start_ns=0,end_ns=0))
  r=aggregate(rows,['norm']);self.assertEqual(r['classes']['norm']['variants']['packet18']['execution_sum']['count'],199)
 def test_event_sequence_sum(self):
  rows=self.rows();rows += [dict(r) for r in rows]
  r=aggregate(rows,['norm']);self.assertTrue(r['passed']);self.assertEqual(r['classes']['norm']['variants']['specialised']['execution_sum']['median_ns'],160)
 def test_noninteger_repetition_refused(self):
  rows=self.rows();rows[0]['repetition']=True
  with self.assertRaises(ValueError):aggregate(rows,['norm'])
 def test_baseline_only_cannot_win_by_noise(self):
  rows=self.rows()
  for row in rows:row['candidate_available']=False
  result=aggregate(rows,['norm']);self.assertEqual(result['selection']['norm'],'packet18')
 def test_named_candidate_can_win(self):
  rows=self.rows()
  for row in rows:row['class']='gemv:gdn.qkv';row['candidate_available']=True;row['implementation']='p25.rows4' if row['variant']=='specialised' else 'r5'
  result=aggregate(rows,{'gemv:gdn.qkv':dict(candidate_available=False)})
  self.assertEqual(result['selection']['gemv:gdn.qkv'],'specialised')
 def test_one_format_cannot_hide_another_regression(self):
  rows=[]
  for workload,old,new in [('q6',1000,100),('q8',100,110)]:
   for row in self.rows(new):
    row.update({'class':'gemv:gdn.qkv','workload':workload,'candidate_available':True,'implementation':'p25.rows4' if row['variant']=='specialised' else 'r5'})
    if row['variant']=='packet18':row['end_ns']=row['start_ns']+old
    rows.append(row)
  result=aggregate(rows,{'gemv:gdn.qkv':{'workloads':['q6','q8']}})
  self.assertTrue(result['passed']);self.assertEqual(result['selection']['gemv:gdn.qkv'],'packet18')
 def test_missing_gemv_workload_fails(self):
  rows=self.rows()
  for row in rows:row.update({'class':'gemv:gdn.qkv','workload':'q6','candidate_available':True})
  self.assertFalse(aggregate(rows,{'gemv:gdn.qkv':{'workloads':['q6','q8']}})['passed'])
 def test_duplicate_workload_cannot_mask_missing_repetition(self):
  rows=[]
  for workload in ('q6','q8'):
   for row in self.rows():
    row.update({'class':'gemv:gdn.qkv','workload':workload,'candidate_available':True});rows.append(row)
  row=next(x for x in rows if x['workload']=='q6' and x['variant']=='specialised' and x['repetition']==0)
  row['workload']='q8'
  result=aggregate(rows,{'gemv:gdn.qkv':{'workloads':['q6','q8']}})
  self.assertFalse(result['passed']);self.assertTrue(any('missing repetitions' in x for x in result['failures']))
 def test_empty_fails(self):self.assertFalse(aggregate([],['norm'])['passed'])
class K2Failures(unittest.TestCase):
 rows=K2Summary.rows
 def test_changed_gemv_identity_still_refused(self):
  from k2_summary import summarize
  with tempfile.TemporaryDirectory(dir=w.HERE/'build') as tmp:
   root=Path(tmp);rows=[dict(r,**{'class':'gemv:test'},implementation='r5' if r['variant']=='packet18' else 'p25.rows4',candidate_available=True) for r in self.rows()]
   rows[-1]['implementation']='p25.wide8'
   (root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
   report=summarize(root,classes={'gemv:test':dict(dispatch_section='gemv',dispatch_key='test')})
   self.assertFalse(report['passed']);self.assertTrue((root/'dispatch-measured.json').exists())
 def test_failed_candidates_continue_and_write_complete_table(self):
  from k2_summary import summarize
  with tempfile.TemporaryDirectory(dir=w.HERE/'build') as tmp:
   root=Path(tmp);rows=self.rows()
   rows += [dict(r,**{'class':'route'}) for r in self.rows() if r['variant']=='packet18']
   registry={k:dict(dispatch_section='classes',dispatch_key=k) for k in ('norm','route','streams')}
   rows += [dict(r,**{'class':'streams'}) for r in self.rows() if r['variant']=='packet18']
   (root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
   (root/'candidate-failures.jsonl').write_text('\n'.join(json.dumps(dict(**{'class':k},variant='specialised',error='mismatch')) for k in ('route','streams')))
   report=summarize(root,classes=registry)
   self.assertTrue(report['passed']);self.assertEqual(set(report['classes']),set(registry))
   dispatch=json.loads((root/'dispatch-measured.json').read_text())
   self.assertEqual(dispatch['classes'],dict(norm='specialised',route='packet18',streams='packet18'))
   # Excluding a candidate never waives its device execution budget.
   over=dict(self.rows()[0],**{'class':'route'},variant='specialised',end_ns=5e9)
   (root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows+[over]))
   self.assertFalse(summarize(root,classes=registry)['passed'])
   # A missing reference remains a failure even when its candidate was excluded.
   (root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows if not (r['class']=='route' and r['repetition']==1)))
   self.assertFalse(summarize(root,classes=registry)['passed'])
   self.assertTrue((root/'dispatch-measured.json').exists())

if __name__=='__main__':
 import hashlib
 suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
 result=unittest.TextTestRunner().run(suite)
 receipt=dict(passed=result.wasSuccessful(),returncode=0 if result.wasSuccessful() else 1,tests=result.testsRun,device_executed=False,source_sha256={name:hashlib.sha256((w.HERE/name).read_bytes()).hexdigest() for name in ('test_window.py','window.py','window_safety.py','k2_summary.py','k2-class-registry.json')})
 (w.HERE/'window-tests.json').write_text(json.dumps(receipt,indent=2)+'\n')
 raise SystemExit(receipt['returncode'])
