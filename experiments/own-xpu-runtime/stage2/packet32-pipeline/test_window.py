"""CPU-only admission tests and host profiling gate; no device execution."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import window as w
from window_safety import environment_gate,memory_snapshot
class Gate(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=w.B,prefix="window-tests-");self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def identity(self):return dict(boot_id="boot",artifacts_sha256={"binary":"hash"},environment={"native":{}},card=1)
 def receipt(self):
  child=self.root/'receipt.json';child.write_text('{}')
  row=dict(self.identity(),window='K0',passed=True,receipts={'receipt.json':w.sha(child)})
  path=self.root/'window.json';path.write_text(json.dumps(row));return path,row
 def test_watchdogs(self):
  for name,(estimate,_) in w.CONFIG.items():
   self.assertGreaterEqual(w.watchdog(name),max(300,4*(estimate+17)))
   with self.assertRaises(ValueError):w.watchdog(name,299)
 def test_prerequisite(self):
  path,_=self.receipt();w.prerequisites(path,'K0',self.identity())
 def test_prerequisite_identity(self):
  path,row=self.receipt()
  for field in ('boot_id','artifacts_sha256','environment','card'):
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
  with patch.object(w,'journal',return_value=('Fault response',2)),patch.object(w,'save') as save:
   with self.assertRaises(ValueError):watch.check()
   self.assertEqual(save.call_args.args[1]['boot_id'],'boot')
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
 def test_guard(self):self.assertIn('sizeof(F)<=1024',(w.P/'kernel_guard.hpp').read_text())
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Gate))
 (w.P/'window-tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,device_executed=False),indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
