#!/usr/bin/env python3
"""Offline compilation/IR inspection only. Never loads SYCL or opens a device."""
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
HERE=Path(__file__).resolve().parent
COMPILER='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
TRANSLATOR='/opt/intel/oneapi/compiler/2026.0/bin/compiler/llvm-spirv'
def inspect():
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise ValueError('nice19/OMP2')
    build=HERE/'build';build.mkdir(exist_ok=True)
    common=[COMPILER,'-fsycl','-fsycl-device-only','-O3','-std=c++20','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-I'+str(HERE.parent.parent/'stage1/packet3-prep/src'),str(HERE/'kernels.cpp')]
    receipt=dict(schema='own-runtime.iq3.packet8.offline-ir.v1',device_executed=False,commands=[],native_isa=False)
    def run(argv,required=True):
        p=subprocess.run(list(map(str,argv)),capture_output=True,text=True)
        receipt['commands'].append(dict(argv=list(map(str,argv)),returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        if required and p.returncode:raise RuntimeError(p.stderr)
        return p.returncode
    # Preserve the requested method's refusal, then take the supported offline route.
    run(common+['-S','-o',build/'decode-device.ll'],False)
    run(common+['-c','-o',build/'decode-device.bc'])
    run([TRANSLATOR,'--spirv-ext=+all','--spirv-text',build/'decode-device.bc','-o',build/'decode-device.spvasm'])
    text=(build/'decode-device.spvasm').read_text()
    counts=collections.Counter(line.split()[1] for line in text.splitlines() if len(line.split())>1 and line.split()[0].isdigit())
    receipt['module_opcode_counts']=dict(sorted(counts.items()))
    receipt['source_sha256']=hashlib.sha256((HERE/'kernels.cpp').read_bytes()).hexdigest()
    receipt['decode_sha256']=hashlib.sha256((HERE/'decode.hpp').read_bytes()).hexdigest()
    receipt['ir_sha256']=hashlib.sha256(text.encode()).hexdigest()
    receipt['ir_bytes']=len(text.encode())
    receipt['scope']='SPIR-V intermediate assembly, whole module static counts; not Xe ISA or executed instruction counts per 32 weights; no register/spill/occupancy claim'
    receipt['fma_lines']=[line for line in text.splitlines() if ' fma ' in line.lower() or ' mad ' in line.lower()]
    if receipt['fma_lines']:raise ValueError('unexpected contracted arithmetic')
    (HERE/'assembly-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Offline SPIR-V:',receipt['ir_bytes'],'bytes;',len(counts),'opcodes; no FMA/MAD')
    return receipt
if __name__=='__main__':inspect()
