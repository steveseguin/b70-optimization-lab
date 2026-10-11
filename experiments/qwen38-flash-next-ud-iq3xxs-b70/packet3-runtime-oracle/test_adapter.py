#!/usr/bin/env python3
"""Exercise Python stride, production dispatch, streaming tiles and expert offsets."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
import torch
from linear import Library, Linear
HERE=Path(__file__).resolve().parent
def main(build):
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    torch.set_num_threads(2)
    lib=Library(Path(build)/'matmul.so')
    class Store:
        def __init__(self,expert):
            self.tensors={'test':dict(type_id=0,shape=[512,2560])} if not expert else {'test':dict(type_id=21,shape=[512,640,2560])}
            self.calls=[]
        def raw(self,t,row,n):
            self.calls.append((row,n))
            if t['type_id']==0:
                w=np.arange(2560,dtype=np.float32)%19-9
                return np.tile(w,(n,1)).tobytes()
            # finite, nontrivial packed IQ3_S blocks, exact published format.
            block=bytearray((i*37)%256 for i in range(110));block[:2]=b'\x00\x24'
            return bytes(block)*(2560//256)*n
    cases=[]
    with torch.inference_mode():
        for expert in (None,0,511):
            s=Store(expert is not None);linear=Linear(lib,s,'test',expert)
            x=(torch.arange(5120).reshape(2,2560)%31-15).to(torch.bfloat16)
            y=linear(x)
            raw=s.raw(s.tensors['test'],linear.base,1);w=C.create_string_buffer(raw)
            expected=np.zeros((2,1),np.float32);bits=x.view(torch.int16).numpy()
            lib.lib.matmul(linear.t['type_id'],w,bits.ctypes.data,expected.ctypes.data,1,2560,2,linear.v)
            assert torch.equal(y,torch.from_numpy(expected).to(torch.bfloat16).expand_as(y))
            assert torch.equal(y[1:],linear(x[1:]))
            assert all(0<n<=128 and row>=linear.base for row,n in s.calls)
            cases.append(dict(expert=expert,variant=linear.v,shape=list(y.shape),sha256=hashlib.sha256(y.view(torch.uint8).numpy().tobytes()).hexdigest()))
        for e in (-1,512):
            try:Linear(lib,Store(True),'test',e)
            except ValueError:pass
            else:raise AssertionError('invalid expert accepted')
    (HERE/'adapter-proof.json').write_text(json.dumps(dict(passed=True,cases=cases,
        sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'linear.py',Path(__file__)]}),indent=2)+'\n')
    print('PASS Python adapter: dense, expert 0/511, 128-row tiles, batch/single independence')
if __name__=='__main__':main(sys.argv[1])
