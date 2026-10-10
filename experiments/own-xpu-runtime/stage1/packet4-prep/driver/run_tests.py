#!/usr/bin/env python3
"""Run CPU-only driver tests and save their receipt. Scratch is auto-removed."""
import datetime
import io
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import window_driver as w

if __name__ == '__main__':
    w.require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2','nice19 OMP2 required')
    capture=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(w.HERE),pattern='test_driver.py')
    result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    print(capture.getvalue())
    w.write(w.HERE/'test-receipt.json',{
        'schema':'own-xpu-runtime.packet4.driver-cpu-tests.v1',
        'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skips':len(result.skipped),'passed':result.wasSuccessful(),'nice':19,'OMP_NUM_THREADS':'2',
        'python':sys.executable,'native_runtime_imported':False,'native_executed':False,
        'scope':'certified init_worker dispatch AST with mock dependencies; four CPU subprocess workers; real Recorder hook transport; admission/oracle/shutdown controls',
        'not_proven':'XPU hook neutrality, full census, native shutdown and hardware health',
        'preregistration_sha256':w.sha(w.PREREG),'driver_seal_sha256':w.sha(w.HERE/'driver-seal.json'),
        'scratch':'TemporaryDirectory contexts removed all test scratch', 'log':capture.getvalue()})
    sys.exit(not result.wasSuccessful())
