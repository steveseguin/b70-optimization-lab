"""Pure CPU source/mocked orchestration gate; never executes a model binary."""
import gzip,hashlib,json,unittest
from pathlib import Path
import test_window,test_suite_long,test_suite_metrics,test_draft_window_cleanup,context_window_gate
P=Path(__file__).resolve().parent

def main():
 (P/'build').mkdir(exist_ok=True)
 suite=unittest.TestSuite(test_window.Gate(n) for n in unittest.defaultTestLoader.getTestCaseNames(test_window.Gate) if n!='test_class_diagnostic_contract')
 for cls in (test_suite_long.LongSuite,test_suite_long.LongPrerequisites,test_suite_metrics.Metrics,test_draft_window_cleanup.CleanupTests,test_draft_window_cleanup.TeardownTests,test_draft_window_cleanup.CompactionTests,context_window_gate.ContextWindows):
  suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
 with gzip.open(P/'wrapper-merge-tests.log.gz','wt') as log:r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
 names=['window.py','draft_window.py','suite.py','suite_metrics.py','context_window_gate.py','test_window.py','test_suite_long.py','test_suite_metrics.py','test_draft_window_cleanup.py','wrapper_cpu_gate.py','k2_summary.py']
 row=dict(passed=r.wasSuccessful(),tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),device_executed=False,rank_processes_started=0,window_cases=78,excluded=['test_window.Gate.test_class_diagnostic_contract: separately qualified host binary required'],sources={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in names})
 for name in ('wrapper-merge-tests.json','context-window-gates.json'):(P/name).write_text(json.dumps(row,indent=2)+'\n')
 print(json.dumps({k:v for k,v in row.items() if k!='sources'}))
 for t,e in r.failures+r.errors:print(str(t),e.splitlines()[-1][:700])
 return not r.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
