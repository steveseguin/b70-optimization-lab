#!/usr/bin/env python3
"""CPU synthetic controls only: no checkpoint, Comfy initialization or GPU calls."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['ZE_AFFINITY_MASK']='-1'
sys.dont_write_bytecode=True
import torch

def unavailable_factory():
    return lambda: False

def deny_factory():
    def deny(*a,**k): raise AssertionError('GPU access prohibited in CPU controls')
    return deny

assert not torch.cuda.is_initialized() and not torch.xpu.is_initialized()
for backend in (torch.cuda,torch.xpu):
    backend.is_available=unavailable_factory()
    backend.device_count=lambda:0
    for n in ('init','_lazy_init','current_device','set_device','synchronize','get_device_properties','get_device_capability'):
        if hasattr(backend,n):setattr(backend,n,deny_factory())
for n in ('_xpu_init','_xpu_getDeviceCount','_cuda_init','_cuda_getDeviceCount'):
    if hasattr(torch._C,n):setattr(torch._C,n,deny_factory())
OVERLAY=Path('/home/steve/ltx25-upstream99-dependencies/site-packages')
sys.path.insert(0,str(OVERLAY))
import comfy_kitchen as ck
import comfy_kitchen.backends.eager as eager
import comfy_kitchen.backends.eager.rope as rope
# Simulate only the normal quant_ops routing state; never initialize Comfy/models.
ck.registry.disable('cuda');ck.registry.disable('triton')
sys.modules['comfy.quant_ops']=types.SimpleNamespace(ck=ck)
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('rope_compat_under_test',HERE/'install_rope_compat.py')
C=importlib.util.module_from_spec(s);s.loader.exec_module(C)
ORIGINAL_CODE=rope.apply_rope_split_half1.__code__
OLD=C.definitions((HERE/'source-evidence/rope-0.2.33.py').read_bytes(),'old',torch)[C.FUNCTION]
NEW=C.definitions((HERE/'source-evidence/rope-0.2.37.py').read_bytes(),'new',torch)[C.FUNCTION]
RESULTS=[]

def bits(t):return t.contiguous().view(torch.uint8)

def fixtures():
    g=torch.Generator(device='cpu').manual_seed(990033)
    for dtype,freqtype,head,window in [(torch.bfloat16,torch.float32,256,64),
                                      (torch.float32,torch.float32,128,64),
                                      (torch.bfloat16,torch.bfloat16,128,64),
                                      (torch.bfloat16,torch.float32,256,128)]:
        x=torch.randn((1,16,window,head),generator=g,dtype=torch.float32).to(dtype)
        angle=torch.randn((1,1,window,head//2),generator=g,dtype=torch.float32).to(freqtype)
        cos,sin=angle.cos(),angle.sin()
        freq=torch.stack((cos,-sin,sin,cos),-1).unflatten(-1,(2,2))
        yield x,freq
        if dtype == torch.bfloat16 and freqtype == torch.float32 and window == 64:
            yield x.transpose(1,2).contiguous().transpose(1,2),freq

class Controls(unittest.TestCase):
    def setUp(self):
        rope.apply_rope_split_half1.__code__=ORIGINAL_CODE
        C._INSTALLED=False
    def tearDown(self):
        rope.apply_rope_split_half1.__code__=ORIGINAL_CODE
        C._INSTALLED=False
    def test_old_new_rounding_diff_and_restoration(self):
        receipt=C.install();different=0
        for x,f in fixtures():
            x_before,f_before=bits(x).clone(),bits(f).clone()
            old,new=OLD(x,f),NEW(x,f)
            restored=ck.apply_rope_split_half1(x,f)
            count=int((bits(old)!=bits(new)).sum())
            different+=count
            self.assertTrue(torch.equal(bits(old),bits(restored)))
            self.assertTrue(torch.equal(bits(restored),bits(ck.apply_rope_split_half1(x,f))))
            q,k=eager.apply_rope_split_half(x,x.clone(),f)
            self.assertTrue(torch.equal(bits(old),bits(q)))
            self.assertTrue(torch.equal(bits(old),bits(k)))
            inplace=x.clone();eager.apply_rope_split_half1_(inplace,f)
            self.assertTrue(torch.equal(bits(old),bits(inplace)))
            self.assertTrue(torch.equal(x_before,bits(x)))
            self.assertTrue(torch.equal(f_before,bits(f)))
            RESULTS.append(dict(dtype=str(x.dtype),frequency_dtype=str(f.dtype),shape=list(x.shape),strides=list(x.stride()),
                                old_new_different_bytes=count,restored_exact=True))
        self.assertGreater(different,0,'Control must actually expose the arithmetic difference')
        self.assertFalse(receipt['gpu_parity_qualified'])
        self.assertFalse(torch.xpu.is_initialized());self.assertFalse(torch.cuda.is_initialized())
    def test_repeat_refused(self):
        C.install()
        with self.assertRaisesRegex(RuntimeError,'repeat refused'):C.install()
    def test_source_drift_refused_before_mutation(self):
        real=C.regular
        with patch.object(C,'regular',side_effect=lambda p:real(p)+b'#changed\n' if p==C.NEW_PATH else real(p)):
            with self.assertRaisesRegex(RuntimeError,'Unexpected loaded'):C.install()
        self.assertIs(rope.apply_rope_split_half1.__code__,ORIGINAL_CODE)
    def test_loaded_bytecode_drift_refused(self):
        rope.apply_rope_split_half1.__code__=OLD.__code__
        with self.assertRaisesRegex(RuntimeError,'bytecode changed'):C.install()
    def test_foreign_alias_refused(self):
        with patch.object(eager,'apply_rope_split_half1',NEW):
            with self.assertRaisesRegex(RuntimeError,'alias/owner'):C.install()
    def test_wrong_routing_and_foreign_registry_refused(self):
        real=ck.registry.is_available
        with patch.object(ck.registry,'is_available',side_effect=lambda n:True if n=='triton' else real(n)):
            with self.assertRaisesRegex(RuntimeError,'Non-eager'):C.install()
        with patch.dict(ck.registry._backends,{'eager':object()}):
            with self.assertRaisesRegex(RuntimeError,'owner'):C.install()
    def test_missing_quant_ops_and_override_refused(self):
        q=sys.modules.pop('comfy.quant_ops')
        try:
            with self.assertRaisesRegex(RuntimeError,'quant_ops'):C.install()
        finally:sys.modules['comfy.quant_ops']=q
        with ck.registry.use_backend('eager'):
            with self.assertRaisesRegex(RuntimeError,'override'):C.install()
    def test_float64_dispatch_still_refused(self):
        C.install()
        x,f=next(fixtures())
        with self.assertRaises(Exception) as result:ck.apply_rope_split_half1(x,f.double())
        self.assertIn('dtype torch.float64',str(result.exception))
    def test_foreign_torch_binding_refused(self):
        with patch.object(rope,'torch',object()):
            with self.assertRaisesRegex(RuntimeError,'global module'):C.install()
    def test_tensor_exception_propagates(self):
        C.install()
        with self.assertRaises(RuntimeError):eager.apply_rope_split_half1(torch.ones(1,3),torch.ones(1,2,2))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    print(json.dumps({'status':'passed' if result.wasSuccessful() else 'failed','cases':RESULTS,
                      'tests':result.testsRun,'gpu_initialized':torch.xpu.is_initialized() or torch.cuda.is_initialized(),
                      'scope':'CPU synthetic arithmetic and real package dispatch with simulated quant_ops routing; no model qualification'},indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
