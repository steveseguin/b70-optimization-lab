#!/usr/bin/env python3
"""Run one CPU suite; six owner-prohibited lane tests are explicitly skipped."""
import argparse
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('suite', choices=('lane','probe','teardown'))
parser.add_argument('--receipt',type=Path)
args=parser.parse_args()
paths={'lane':HERE.parent,'probe':HERE.parent/'probe','teardown':HERE/'tests'}
suite=unittest.defaultTestLoader.discover(str(paths[args.suite]),pattern='test_*.py')
excluded=[]
def restrict(tests):
    for test in tests:
        if isinstance(test,unittest.TestSuite):
            restrict(test)
        elif test.id().endswith('.test_guardian_records_native_signal_without_runtime_imports'):
            excluded.append(test.id())
            setattr(test,test._testMethodName,unittest.skip(
                'owner hard rule: never kill processes; test sends fatal SIGALRM')(
                    getattr(test,test._testMethodName)))
        elif (test.id().startswith('test_worker_init_rehearsal.') or
              test.id().endswith('.test_real_checkpoint_boundary_bytes_without_table_allocation')):
            excluded.append(test.id())
            setattr(test,test._testMethodName,unittest.skip(
                'owner hard rule: no protected model storage or torch.xpu rehearsal')(
                    getattr(test,test._testMethodName)))
restrict(suite)
if args.suite=='lane' and len(excluded)!=6:
    raise RuntimeError(f'Expected exactly six prohibited tests, got {excluded}')
result=unittest.TextTestRunner(verbosity=2).run(suite)
receipt=dict(suite=args.suite,discovered=result.testsRun,
             passed=result.testsRun-len(result.skipped)-len(result.errors)-len(result.failures),
             skipped=len(result.skipped),failures=len(result.failures),errors=len(result.errors),
             exclusions=excluded,native_cleanup_executed=False)
if args.receipt:
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
raise SystemExit(not result.wasSuccessful())
