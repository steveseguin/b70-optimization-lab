#!/usr/bin/env python3
"""Offline CPU suite and reproducible receipt; refuses wrong priority/thread cap."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import unittest
import resource
from collections import Counter
from importlib.metadata import version

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':
    raise SystemExit('Run at nice 19 with OMP_NUM_THREADS=2')
import torch
# These control CPU workers only. No device API is queried or initialized.
torch.set_num_threads(2)
torch.set_num_interop_threads(1)
torch.use_deterministic_algorithms(True)

parser=argparse.ArgumentParser()
parser.add_argument('--receipt',type=Path)
args=parser.parse_args()
start=time.monotonic()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
class RecordedResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.test_ids=[]
    def startTest(self,test):
        self.test_ids.append(test.id())
        super().startTest(test)
result=unittest.TextTestRunner(verbosity=2,resultclass=RecordedResult).run(suite)
if args.receipt:
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.md','.txt') and p.name not in ('test-receipt.json','test-receipt-gate-correction.json'))
    files+=[ROOT.parent/'packet1/tensor-contract.json',ROOT.parent/'packet1/identity.json']
    receipt={'schema':'own-xpu-runtime.packet1b.cpu-tests.v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'host':platform.node(),'python':sys.version,'executable':sys.executable,'torch':torch.__version__,
             'torch_build':torch.__config__.show(),'nice':os.getpriority(os.PRIO_PROCESS,0),
             'OMP_NUM_THREADS':os.environ['OMP_NUM_THREADS'],'torch_threads':torch.get_num_threads(),
             'interop_threads':torch.get_num_interop_threads(),'device':'cpu','weights':'synthetic only; retained packet-1 headers also checked',
             'command':'nice -n 19 env OMP_NUM_THREADS=2 '+sys.executable+' -B '+str(ROOT.relative_to(ROOT.parents[3]))+'/run_tests.py --receipt '+str(args.receipt),
             'tests_run':result.testsRun,'test_ids':result.test_ids,'test_counts_by_module':dict(Counter(t.split('.')[0] for t in result.test_ids)),'jsonschema':version('jsonschema'),'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
             'passed':result.wasSuccessful(),'elapsed_seconds':time.monotonic()-start,
             'failures_detail':[(str(t),msg) for t,msg in result.failures+result.errors],
             'hashes':{str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
sys.exit(0 if result.wasSuccessful() else 1)
