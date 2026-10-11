"""CPU-only protocol regressions. Synthetic timing below is never evidence."""
import json,unittest,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
import window,summary
from window_safety import environment_gate
P=Path(__file__).resolve().parent
class Protocol(unittest.TestCase):
 def test_deadlines(self):
  for w in ('K0','G2'):
   d=window.deadlines(w);self.assertGreaterEqual(d['watchdog_seconds'],300);self.assertGreaterEqual(d['watchdog_seconds'],4*d['expected_total_seconds']);self.assertFalse(d['expectation_enforced']);self.assertGreaterEqual(d['submission_budget_seconds']['logits'],.0088)
 def test_short_watchdog(self):
  for w in ('K0','G2'):
   with self.assertRaises(ValueError):window.deadlines(w,299)
 def test_environment(self):
  self.assertEqual(environment_gate({'OMP_NUM_THREADS':'2','PATH':'/usr/bin'})['native']['OMP_NUM_THREADS'],'2')
 def test_unknown_env(self):
  for key in ('SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS','UNREGISTERED','CODEX_ARBITRARY'):
   with self.assertRaises(ValueError):environment_gate({'OMP_NUM_THREADS':'2',key:'1'})
 def test_masked_env(self):
  for key in ('ZE_AFFINITY_MASK','ONEAPI_DEVICE_SELECTOR','SYCL_DEVICE_FILTER'):
   with self.assertRaises(ValueError):environment_gate({'OMP_NUM_THREADS':'2',key:'0'})
 def test_threads(self):
  with self.assertRaises(ValueError):environment_gate({'OMP_NUM_THREADS':'3'})
 def test_loader_failure(self):
  def fake(*a,**kw):return subprocess.CompletedProcess(a,0,'libsycl => not found','')
  with self.assertRaises(ValueError):window.ldd_preflight('/fake',fake)
 def test_ldd_before_latch(self):
  text=(P/'window.py').read_text();self.assertLess(text.index('loader = ldd_preflight'),text.index('require(not latch.exists()'))
 def test_fresh_owners(self):
  with self.assertRaises(ValueError):window.distinct_owners([{'unit':'same','pid':1},{'unit':'same','pid':1}],2)
 def test_stats(self):
  self.assertEqual(summary.stats(list(range(200)))['median_us'],99.5);self.assertEqual(summary.stats(list(range(200)))['p90_us'],179)
 def test_insufficient_stats(self):
  with self.assertRaises(AssertionError):summary.stats([1]*199)
 def test_event_sum(self):
  with tempfile.TemporaryDirectory(dir=P/'build') as d:
   p=Path(d);rows=[]
   for n in range(200):
    for e in (0,1):rows.append(dict(class_name='x',**{'class':'x'},workload='x',candidate='r5',current_kernel='actual',repetition=n,event_index=e,event_count=2,start_ns=10,end_ns=1010,exact=True))
   (p/'timing.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));got=summary.owner_summary(p);self.assertEqual(got[('x','x','r5')]['median_us'],2)
   rows.append(rows[0]);(p/'timing.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaises(AssertionError):summary.owner_summary(p)
 def test_unsafe_receipt(self):
  with tempfile.TemporaryDirectory(dir=P/'build') as d:
   p=Path(d);(p/'receipt.json').write_text(json.dumps(dict(passed=True,safe_to_exit=False)))
   with self.assertRaises(ValueError):window.native_gate(p,'G2')
 def test_no_invented_dispatch(self):
  with tempfile.TemporaryDirectory(dir=P/'build') as d:
   p=Path(d);(p/'window.json').write_text(json.dumps(dict(completed=False)))
   with self.assertRaises(AssertionError):summary.write_summary(p)
   self.assertFalse((p/'dispatch-gemv-measured.json').exists())
 def test_failure_before_signal(self):
  text=(P/'window.py').read_text();self.assertLess(text.index('failure(reasons[0])'),text.index('child.send_signal(signal.SIGTERM)'))
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Protocol))
 (P/'protocol-tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,device_executed=False,synthetic_test_times_not_measurements=True),indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful() else 1)
