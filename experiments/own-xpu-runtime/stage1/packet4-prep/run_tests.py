#!/usr/bin/env python3
"""CPU-only transport suite; temporary bundles are removed by TemporaryDirectory."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time
import unittest

sys.dont_write_bytecode = True
if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':
    raise SystemExit('requires nice 19 and OMP_NUM_THREADS=2')
import torch
torch.set_num_threads(2)
torch.set_num_interop_threads(1)
torch.use_deterministic_algorithms(True)
from common import HERE, LANE, file_hash

p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path);a=p.parse_args()
class Result(unittest.TextTestResult):
    def __init__(self,*args,**kw):super().__init__(*args,**kw);self.ids=[]
    def startTest(self,t):self.ids.append(t.id());super().startTest(t)
start=time.monotonic()
r=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.discover(str(HERE/'tests')))
if a.receipt:
    files=[f for f in HERE.rglob('*') if f.is_file() and f.suffix in ('.py','.md','.json') and not f.name.startswith('test-receipt')]
    files.extend([LANE/'stage1/packet1b/reference/math.py',LANE/'stage2/packet1b/reference.py',LANE/'stage1/packet1b/tests/fixture-extraction.schema.json'])
    receipt={'schema':'own-xpu-runtime.packet4-prep.cpu-tests.v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'host':platform.node(),'python':sys.version,'executable':sys.executable,'torch':torch.__version__,
        'nice':19,'OMP_NUM_THREADS':'2','torch_threads':2,'interop_threads':1,'device':'cpu',
        'weights':'synthetic only','command':'nice -n 19 env OMP_NUM_THREADS=2 '+sys.executable+' -B '+' '.join(sys.argv),
        'tests_run':r.testsRun,'test_ids':r.ids,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),
        'passed':r.wasSuccessful(),'elapsed_seconds':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'hashes':{os.path.relpath(f,HERE):file_hash(f) for f in sorted(files)},
        'failure_details':[(str(t),msg) for t,msg in r.failures+r.errors],
        'native_adapter_tested':False,
        'adapter_cpu_tests':sum(t.startswith('test_adapter.') for t in r.ids),
        'source_ast_roots':{k:os.environ.get(k) for k in ('PACKET4_A367_SOURCE','PACKET4_IMAGE_SOURCE')},
        'source_ast_symbols':len(json.loads((HERE/'adapters/names.json').read_text())['symbols']) if all(os.environ.get(k) for k in ('PACKET4_A367_SOURCE','PACKET4_IMAGE_SOURCE')) else 0,
        'native_extraction_ready':False,'scratch':'TemporaryDirectory contexts cleaned at suite exit'}
    a.receipt.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
sys.exit(not r.wasSuccessful())
