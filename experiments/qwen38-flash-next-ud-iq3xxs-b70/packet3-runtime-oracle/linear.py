"""Drop-in CPU Python matmul adapter for packet2's Store/Model.linear interface.

Full-model fixtures use oracle.cpp because rebasing only matmul leaves the
old Python nonlinear/PLE boundaries in place. This adapter is useful for
isolated operator comparisons and always uses the production matrix shape.
"""
import ctypes as C
import numpy as np
import torch

class Library:
    def __init__(self,path):
        self.lib=C.CDLL(str(path))
        self.lib.variant.argtypes=[C.c_uint]*4
        self.lib.variant.restype=C.c_int
        self.lib.matmul.argtypes=[C.c_uint,C.c_void_p,C.c_void_p,C.c_void_p,C.c_uint,C.c_uint,C.c_uint,C.c_uint]
        self.lib.matmul.restype=None

class Linear:
    def __init__(self,library,store,name,expert=None):
        self.lib,self.store,self.name=library.lib,store,name
        self.t=store.tensors[name];shape=self.t['shape']
        if len(shape) not in (2,3) or (len(shape)==3)!=(expert is not None):raise ValueError('matrix/expert shape')
        self.n,self.k=shape[-2:];self.base=0 if expert is None else expert*self.n
        if expert is not None and not 0<=expert<shape[0]:raise ValueError('expert range')
        self.v=self.lib.variant(self.t['type_id'],self.n,self.k,shape[0] if expert is not None else 1)
        if self.v<0:raise ValueError('unregistered production matrix')

    def __call__(self,x):
        if x.device.type!='cpu' or x.dtype!=torch.bfloat16 or x.ndim!=2 or x.shape[1]!=self.k:raise ValueError('CPU BF16 matrix input required')
        bits=x.contiguous().view(torch.int16).numpy()
        out=[]
        for start in range(0,self.n,128):
            n=min(128,self.n-start);raw=self.store.raw(self.t,self.base+start,n)
            packed=C.create_string_buffer(raw);y=np.empty((len(x),n),np.float32)
            self.lib.matmul(self.t['type_id'],packed,bits.ctypes.data,y.ctypes.data,n,self.k,len(x),self.v)
            if not np.isfinite(y).all():raise ValueError('nonfinite production output')
            out.append(torch.from_numpy(y).to(torch.bfloat16))
        return torch.cat(out,-1)
