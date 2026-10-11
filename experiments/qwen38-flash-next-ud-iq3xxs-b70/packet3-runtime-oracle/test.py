#!/usr/bin/env python3
"""Prove the C ABI on hash-bound packet2/6-9 fixtures and independent FP32 trees."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STAGE=ROOT/'experiments/own-xpu-runtime/stage2'
sys.path.insert(0,str(HERE.parent/'packet2-cpu-oracle'))
sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/stage1/packet1b'))
from packed import decode
from loaders.dequant import dequantize
KINDS={0:'F32',1:'F16',30:'BF16',8:'Q8_0',11:'Q3_K',14:'Q6_K',18:'IQ3_XXS',20:'IQ4_NL',21:'IQ3_S',22:'IQ2_S'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(scratch):
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    scratch=Path(scratch);fixtures=STAGE/'packet2/build/fixtures/device-fixtures'
    records=json.loads((STAGE/'packet2/cpu-receipt.json').read_text())['fixtures']
    known={r['label']+'.fixture':r['fixture_sha256'] for r in records if r['label'].startswith(('random','real-'))}
    if not fixtures.exists():
        sys.path.insert(0,str(STAGE/'packet6-kopt/tests'))
        import fixtures as regen
        fixtures=scratch/'fixtures';fixtures.mkdir();regen.FIXTURES=fixtures;regen.regenerate(records)
    assert len(known)==27
    for name,digest in known.items():assert sha(fixtures/name)==digest,name
    native=[]
    for _ in range(2):
        native.append(subprocess.check_output([scratch/'fixture-test',fixtures],text=True))
    assert native[0]==native[1]
    lib=C.CDLL(str(scratch/'matmul.so'));lib.matmul.argtypes=[C.c_uint,C.c_void_p,C.c_void_p,C.c_void_p,C.c_uint,C.c_uint,C.c_uint,C.c_uint]
    lib.variant.argtypes=[C.c_uint]*4;lib.variant.restype=C.c_int
    comparisons=0;fingerprint=hashlib.sha256()
    def tree(x):
        while len(x)>1:x=x[::2]+x[1::2]
        return x[0]
    for name in sorted(known):
        raw=(fixtures/name).read_bytes();t,k,n,a,o=struct.unpack('<5I',raw[:20]);packed=raw[20:-k*2]
        try:w=decode(KINDS[t],packed).reshape(n,k)
        except ValueError:w=dequantize(KINDS[t],packed,(n,k)).numpy().astype(np.float32)
        bits=np.frombuffer(raw[-k*2:],dtype='<u2').copy()
        if a==1:bits=(bits.view('<f2').astype('<f4').view('<u4')>>16).astype('<u2')
        # Three input rows verify stride/batch independence, including sign-zero.
        x=np.stack([bits,bits^0x8000,np.where(np.arange(k)%2,0x8000,0).astype('<u2')])
        xf=(x.astype('<u4')<<16).view('<f4');wp=C.create_string_buffer(packed)
        for v in range(6):
            actual=np.zeros((3,n),np.float32)
            lib.matmul(t,wp,x.ctypes.data,actual.ctypes.data,n,k,3,v)
            expected=np.zeros_like(actual);splits=4 if v==1 or v>=4 else 1
            for b in range(3):
                for r in range(n):
                    parts=[]
                    for s in range(splits):
                        tiles=(k+255)//256;lo=min(k,(tiles*s//splits)*256);hi=min(k,(tiles*(s+1)//splits)*256)
                        lanes=np.zeros(32,np.float32)
                        for chunk in range(lo,hi,256):
                            for j in range(8):
                                ix=chunk+np.arange(32)*8+j;valid=ix<hi
                                lanes[valid]=lanes[valid]+w[r,ix[valid]]*xf[b,ix[valid]]
                        parts.append(tree(lanes))
                    expected[b,r]=tree(np.array(parts,np.float32))
            assert np.array_equal(actual.view('<u4'),expected.view('<u4')),(name,v,actual,expected)
            fingerprint.update(actual.tobytes());comparisons+=actual.size
    census=json.loads((HERE.parent/'packet1/tensor-census.json').read_text())['tensors'];dispatch=[]
    for t in census:
        shape=t['shape']
        if len(shape)<2 or t['component'] in ('embedding','ple_lookup'):continue
        v=lib.variant(t['type_id'],shape[-2],shape[-1],shape[0] if len(shape)==3 else 1)
        assert v>=0,t['name']
        dispatch.append(dict(name=t['name'],type=t['type'],shape=shape,variant=v))
    assert lib.variant(0,99,123,1)==-1
    report=dict(passed=True,fixtures=known,fp32_bit_comparisons=comparisons,output_sha256=fingerprint.hexdigest(),
        packet8_native=json.loads(native[0]),native_fresh_process_repeat=True,production_tensors=dispatch,
        activation_note='C ABI is BF16-only; historical F16 inputs are derived BF16. Native packet8 checks original F16/BF16 fixtures.',
        binary_sha256=sha(scratch/'matmul.so'),device_executed=False)
    (HERE/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',comparisons,'FP32 values;',len(dispatch),'production matrix bindings')
if __name__=='__main__':main(sys.argv[1])
