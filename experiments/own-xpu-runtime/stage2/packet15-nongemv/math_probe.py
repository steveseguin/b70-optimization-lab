#!/usr/bin/env python3
"""Diagnose CPU elementary mismatch; do not patch packet1b or expected outputs."""
import ctypes
import json
from pathlib import Path
import torch
HERE=Path(__file__).resolve().parent
m=ctypes.CDLL(str(HERE/'build/host/libmath-probe.so'));fn=m.primitive
fn.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int]
torch.set_num_threads(2);x=torch.arange(-32,33,dtype=torch.float32)/32
rows=[]
for i,(name,operation) in enumerate([('exp',torch.exp),('log',torch.log),('sqrt',torch.sqrt),('sigmoid',torch.sigmoid),('rsqrt',torch.rsqrt)]):
    z=x if i in (0,3) else x+2;expected=operation(z);actual=torch.zeros_like(expected)
    fn(i,z.data_ptr(),actual.data_ptr(),z.numel())
    bad=(expected.view(torch.int32)!=actual.view(torch.int32)).nonzero().flatten()
    rows.append(dict(op=name,values=z.numel(),differing_bits=int(len(bad)),differences=[dict(input=float(z[k]),torch_bits=int(expected.view(torch.int32)[k]),cpp_bits=int(actual.view(torch.int32)[k])) for k in bad]))
print(json.dumps(dict(scope='CPU elementary census, not model or native quality',torch_version=torch.__version__,rows=rows),indent=2))
