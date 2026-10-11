#!/usr/bin/env python3
"""Only GNU C++ host compilation; no native/device configuration or discovery."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STAGE=ROOT/'experiments/own-xpu-runtime/stage2'
OWNER=ROOT/'experiments/own-xpu-runtime/stage1/packet3-prep/src'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(scratch):
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    scratch=Path(scratch).resolve();scratch.mkdir(exist_ok=False)
    receipt=dict(schema='iq3-arithmetic-identity-v1.build',device_executed=False,commands=[])
    def run(cmd):
        p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
        receipt['commands'].append(dict(argv=list(map(str,cmd)),returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        if p.returncode:raise RuntimeError(p.stderr+p.stdout)
        return p.stdout
    try:
        base=['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off']
        run(base+['-shared','-fPIC',HERE/'matmul.cpp','-o',scratch/'matmul.so'])
        includes=['-I'+str(p) for p in [OWNER,STAGE/'packet2/kernels',STAGE/'packet2/loader',STAGE/'packet13-integrate']]
        # Scheduling-only CPU overlay: disjoint rows, unchanged per-row math.
        original=(STAGE/'packet13-integrate/performance.cpp').read_text()
        needle='        for(size_t row=0;row<m.rows;++row) {'
        assert original.count(needle)==1
        parallel=original.replace(needle,'        #pragma omp parallel for schedule(static) num_threads(8)\n'+needle)
        (scratch/'performance-cpu.cpp').write_text(parallel)
        receipt['cpu_row_parallel_overlay']=dict(source_sha256=sha(STAGE/'packet13-integrate/performance.cpp'),
            generated_sha256=sha(scratch/'performance-cpu.cpp'),search=needle,
            replacement='        #pragma omp parallel for schedule(static) num_threads(8)\n'+needle)
        run(base+['-DOWN_RT_HOST_ONLY','-fopenmp']+includes+[HERE/'oracle.cpp',scratch/'performance-cpu.cpp',STAGE/'packet4/kernels.cpp',STAGE/'packet4/owner_retire.cpp',STAGE/'packet2/loader/gguf.cpp',OWNER/'owner.cpp','-lcrypto','-o',scratch/'oracle'])
        run(base+[STAGE/'packet13-integrate/authority_test.cpp','-o',scratch/'authority-test'])
        receipt['production_shape_proof']=run([scratch/'authority-test'])
        run(base+['-I'+str(STAGE/'packet2/tests'),'-I'+str(STAGE/'packet2/kernels'),STAGE/'packet8-kopt3/tests/host.cpp','-o',scratch/'fixture-test'])
        deps=run(['readelf','-d',scratch/'oracle'])
        assert not any(s in deps.lower() for s in ['libsycl','ze_loader','opencl','libcuda'])
        receipt['dynamic_dependencies']=deps
        # Packet13's consumer binds this exact broad dependency map. Verify it;
        # never silently refresh an old receipt to accept changed arithmetic.
        authority=json.loads((STAGE/'packet13-integrate/build-receipt.json').read_text())
        for name,digest in authority['arithmetic_sources'].items():
            assert sha(ROOT/name)==digest, name
        identity=dict(schema='iq3.arithmetic-identity.v1',order_version=1,
            arithmetic=authority['arithmetic'],arithmetic_sources=authority['arithmetic_sources'],
            defining_header='experiments/own-xpu-runtime/stage2/packet13-integrate/arithmetic.hpp',
            defining_header_sha256=sha(STAGE/'packet13-integrate/arithmetic.hpp'),
            scope='runtime dispatch, packed dequant, separate FP32 multiply/add, BF16 boundaries, shared nonlinear core',
            device_qualified=False)
        (HERE/'arithmetic.json').write_text(json.dumps(identity,indent=2)+'\n')
        receipt['sources']={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'oracle.cpp',HERE/'matmul.cpp',HERE/'build.py']}
        receipt['compiler']=run(['g++','--version'])
        receipt['binaries']={p.name:sha(p) for p in scratch.iterdir() if p.is_file()}
        receipt['passed']=True
    finally:
        (HERE/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':build(sys.argv[1])
