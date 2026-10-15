"""Future CPU receipt producer, to run only after patch application and rebuild.

This does not reseal or authorize a device run. Existing seal source pins remain
fail-closed until the new allocation policy and fresh gates are explicitly bound.
"""
import hashlib,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in ('test_speed5','test_speed6'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sources=('main.cpp','strict_snapshot.hpp','memory_plan.py','memory_gate.py','window.py','pipeline.py',
             'memory-plan.json','test_speed5.py','test_speed6.py','speed7_memory_gate.py')
    row=dict(passed=result.wasSuccessful(),checks=result.testsRun,failures=len(result.failures),errors=len(result.errors),device_executed=False,weight_bytes_read=0,
             memory_plan_sha256=hashlib.sha256((P/'memory-plan.json').read_bytes()).hexdigest(),
             qualifying=False,scope='arena/card admission unit proof; not a device or seal receipt',
             source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in sources})
    (P/'speed7-memory-gates.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row));return not result.wasSuccessful()

if __name__=='__main__':raise SystemExit(main())
