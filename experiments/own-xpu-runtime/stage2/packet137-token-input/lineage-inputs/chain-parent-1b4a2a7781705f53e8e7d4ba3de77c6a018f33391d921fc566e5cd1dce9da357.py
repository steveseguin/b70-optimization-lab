"""Run all inherited and packet40 Python regression tests; CPU backends only."""
import json,os,unittest,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
from seal40 import python_dependencies
roots=[Path(__file__).resolve(),*P.glob('test_*.py')]
before_sources=python_dependencies(roots,P)
suite=unittest.defaultTestLoader.discover(str(P),pattern='test_*.py')
with (P/'build/python-tests.log').open('w') as log:
 result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
after_sources=python_dependencies(roots,P)
row=dict(passed=result.wasSuccessful() and before_sources==after_sources,device_executed=False,tests=result.testsRun,sources_unchanged=before_sources==after_sources,
 failures=[(str(t),e) for t,e in result.failures],errors=[(str(t),e) for t,e in result.errors],skipped=[(str(t),e) for t,e in result.skipped],
 sources_sha256=before_sources)
(P/'python-regression-gates.json').write_text(json.dumps(row,indent=2)+'\n')
print(json.dumps(dict(passed=row['passed'],tests=row['tests'],failures=len(row['failures']),errors=len(row['errors']))))
raise SystemExit(not row['passed'])
