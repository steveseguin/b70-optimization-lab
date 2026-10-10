#!/usr/bin/env python3
"""Offline CPU receipt. No model directory, native API, network or runtime import."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':
    raise SystemExit('Run at nice 19 with OMP_NUM_THREADS=2')
import torch
torch.set_num_threads(2)
torch.set_num_interop_threads(1)
torch.use_deterministic_algorithms(True)
import test_reference
p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path);p.add_argument('--compare-receipt',type=Path);a=p.parse_args()
class Result(unittest.TextTestResult):
    def __init__(self,*args,**kw):super().__init__(*args,**kw);self.ids=[]
    def startTest(self,test):self.ids.append(test.id());super().startTest(test)
start=time.monotonic()
r=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromModule(test_reference))
repeat_ok=True
if a.compare_receipt:
    old=json.loads(a.compare_receipt.read_text())
    repeat_ok=(old['passed'] and old['output_sha256']==test_reference.DIGESTS and old['test_ids']==r.ids)
    print('Fresh-process output comparison:', 'PASS' if repeat_ok else 'FAIL')
if a.receipt:
    files=[p for p in ROOT.iterdir() if p.suffix in ('.py','.md','.json') and not p.name.startswith('test-receipt')]
    files.extend([ROOT.parent/'packet1/tensor-contract.json',ROOT.parent/'packet1/identity.json',ROOT.parents[1]/'STAGE2-PLAN.md',ROOT.parents[1]/'stage1/packet1b/loaders/headers.py'])
    receipt={'schema':'own-xpu-runtime.stage2.packet1b.cpu-tests.v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':platform.node(),'python':sys.version,'executable':sys.executable,'torch':torch.__version__,'torch_build':torch.__config__.show(),'nice':os.getpriority(os.PRIO_PROCESS,0),'OMP_NUM_THREADS':os.environ['OMP_NUM_THREADS'],'torch_threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads(),'device':'cpu','weights':'synthetic only; no model-file reads','tests_run':r.testsRun,'test_ids':r.ids,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'passed':r.wasSuccessful() and repeat_ok,'compare_receipt':str(a.compare_receipt) if a.compare_receipt else None,'fresh_process_equal':repeat_ok if a.compare_receipt else None,'command': 'nice -n 19 env OMP_NUM_THREADS=2 '+sys.executable+' -B '+' '.join(sys.argv),'elapsed_seconds':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'output_sha256':test_reference.DIGESTS,'hashes':{os.path.relpath(p,ROOT.parent):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},'failure_details':[(str(t),msg) for t,msg in r.failures+r.errors]}
    a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
sys.exit(not (r.wasSuccessful() and repeat_ok))
