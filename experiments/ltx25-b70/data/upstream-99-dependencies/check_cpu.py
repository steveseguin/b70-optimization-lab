#!/usr/bin/env python3
"""Bounded dependency import/API controls; GPU discovery disabled before app imports."""
import hashlib
import importlib
import importlib.metadata as md
import inspect
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
OVERLAY=ROOT/'site-packages'
receipt=json.loads((ROOT/'receipt.json').read_text())
assert not (ROOT/'cpu-check.json').exists()
assert {str(p.relative_to(OVERLAY)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OVERLAY.rglob('*') if p.is_file()} == receipt['files']
# Device visibility below is process-local; no persistent environment/settings changes.
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['ZE_AFFINITY_MASK']='-1'
blocked=[]
def deny_factory(tag):
    def deny(*args,**kwargs):
        raise RuntimeError('CPU dependency check forbids device initialization/discovery: '+tag)
    return deny
def unavailable_factory(tag):
    def unavailable():
        blocked.append(tag)
        return False
    return unavailable
# Torch import only loads the unchanged library; block app-triggered discovery next.
import torch
assert not torch.xpu.is_initialized() and not torch.cuda.is_initialized()
for backend in (torch.cuda,torch.xpu):
    backend.is_available=unavailable_factory(backend.__name__)
    backend.device_count=lambda:0
    for name in ('init','_lazy_init','get_device_properties','get_device_capability','current_device','set_device','synchronize'):
        if hasattr(backend,name):setattr(backend,name,deny_factory(backend.__name__+'.'+name))
for name in ('_xpu_init','_xpu_getDeviceCount','_xpu_getDeviceProperties','_cuda_init','_cuda_getDeviceCount'):
    if hasattr(torch._C,name):setattr(torch._C,name,deny_factory('torch._C.'+name))
sys.path.insert(0,str(OVERLAY))
origins={}
modules=('comfy_kitchen','comfy_aimdo.control','comfy_aimdo.host_buffer','comfy_aimdo.storage',
         'comfyui_frontend_package','comfyui_embedded_docs','comfyui_workflow_templates',
         'cryptography','cffi','pycparser')
for name in modules:
    module=importlib.import_module(name)
    paths=[str(Path(module.__file__).resolve())] if getattr(module,'__file__',None) else list(module.__path__)
    assert paths and all(Path(p).is_relative_to(OVERLAY) for p in paths),(name,paths)
    origins[name]=paths
ck=sys.modules['comfy_kitchen']
for name in ('int8_attention_is_available','na3d','rms_rope_','apply_rope_split_half','flash_attention_decode_is_available','sol_attn_is_available'):
    assert callable(getattr(ck,name))
assert not ck.int8_attention_is_available()
assert not ck.flash_attention_decode_is_available(torch.device('xpu'))
assert not ck.sol_attn_is_available(torch.device('xpu'))
control=sys.modules['comfy_aimdo.control']
assert control.lib is None and not control.devctxs
assert 'nvml_pressure' in inspect.signature(control.init).parameters
assert callable(sys.modules['comfy_aimdo.storage'].fast_disk)
assert callable(sys.modules['comfy_aimdo.host_buffer'].read_file_to_device)
source=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99-source/source')
sys.path.insert(1,str(source))
sys.argv=[str(Path(__file__)), '--cpu']
import comfy.options
comfy.options.enable_args_parsing()
import comfy.storage
assert Path(comfy.storage.__file__).resolve()==source/'comfy/storage.py'
assert comfy.storage.args.cpu
assert callable(comfy.storage.state_dict_fast_disk)
assert comfy.storage.state_dict_fast_disk({}) is False
origins['comfy.storage']=[comfy.storage.__file__]
na=importlib.import_module('comfy_kitchen.backends.eager.na')
assert hashlib.sha256(Path(na.__file__).read_bytes()).hexdigest()=='4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995'
assert ck.registry.is_available('eager')
rules=ck.registry.get_constraints('eager','na3d')
assert rules is not None
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
key=Ed25519PrivateKey.generate();message=b'CPU dependency availability test';key.public_key().verify(key.sign(message),message)
assert not torch.xpu.is_initialized() and not torch.cuda.is_initialized()
assert {str(p.relative_to(OVERLAY)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OVERLAY.rglob('*') if p.is_file()} == receipt['files']
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in receipt['baseline_runtime_sha256'].items())
result=dict(schema='ltx.upstream99.dependencies.cpu-check.v1',status='passed',runtime_qualified=False,
            overlay_root=str(OVERLAY),receipt_sha256=hashlib.sha256((ROOT/'receipt.json').read_bytes()).hexdigest(),
            checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),module_paths=origins,
            versions={n:md.version(n) for n in receipt['packages']},availability_calls_short_circuited=len(blocked),
            torch_version=torch.__version__,torch_path=torch.__file__,gpu_initialized=False,
            checks=['all 12 exact metadata versions','complete overlay hashes unchanged','all direct app imports from overlay',
                    'kitchen new API callables','XPU/CUDA discovery short-circuited','aimdo init never called','source99 comfy.storage imports under --cpu','accepted eager NA exact hash and registry',
                    'Ed25519 CPU sign and verify','baseline runtime bytes unchanged'],
            limitation='CPU import/API evidence only; does not establish native runtime or model output equivalence')
with (ROOT/'cpu-check.json').open('x') as f:
    json.dump(result,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps(result,indent=2))
