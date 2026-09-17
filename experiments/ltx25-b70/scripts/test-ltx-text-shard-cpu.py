#!/usr/bin/env python3
"""CPU check of the text-encoder shard install against a fake stack and a stub ModelPatcher."""
import sys, types
from pathlib import Path
import torch, torch.nn as nn
sys.path.insert(0, str(Path(__file__).resolve().parent))

class FakePatcher:
    def __init__(self, model, load_device, offload_device):
        self.model, self.load_device, self.offload_device = model, load_device, offload_device
        self.size = 0; self.additional_models = {}
    def is_dynamic(self): return False
    def loaded_size(self): return 0
    def model_dtype(self): return torch.bfloat16
    def model_size(self): return sum(p.numel() * p.element_size() for p in self.model.parameters())
    def set_additional_models(self, key, models): self.additional_models[key] = models
    def get_additional_models_with_key(self, key): return self.additional_models[key]
mp = types.ModuleType('comfy.model_patcher'); mp.ModelPatcher = FakePatcher
sys.modules.setdefault('comfy', types.ModuleType('comfy')); sys.modules['comfy.model_patcher'] = mp
import ltx_text_shard as ts

class Layer(nn.Module):
    def __init__(self): super().__init__(); self.lin = nn.Linear(8, 8)
    def forward(self, x): return self.lin(x)
class Stack(nn.Module):
    def __init__(self): super().__init__(); self.layers = nn.ModuleList([Layer() for _ in range(6)])
    def forward(self, x):
        outs = []
        for i, layer in enumerate(self.layers):
            x = layer(x); outs.append(x.clone())
        return torch.cat(outs, 0)
stack = Stack(); before = stack(torch.ones(1, 8))
clip = types.SimpleNamespace(patcher=FakePatcher(stack, torch.device('cpu'), torch.device('cpu')))
layers = list(stack.layers)
# shard install must be type-checked against the fake ModelPatcher (it is the class we stubbed)
shard = ts.install(clip, stack, layers, torch.device('cpu'), torch.device('cpu'), 4)
assert isinstance(stack.layers, tuple) and len(stack.layers) == 6
assert len(list(stack._ltx_primary_layers)) == 4 and len(list(shard.model.layers)) == 2
main_params = {id(p) for p in stack.parameters()}; shard_params = {id(p) for p in shard.model.parameters()}
assert not (main_params & shard_params) and len(main_params) == 8 and len(shard_params) == 4
assert torch.equal(stack(torch.ones(1, 8)), before), 'forward through the tuple must be unchanged'
assert clip.patcher.additional_models[ts.KEY] == [shard] and stack._ltx_text_shard_identity['split_index'] == 4
assert ts.verify_placement(clip, stack)['layer_count'] == 6
try:
    ts.install(clip, stack, layers, torch.device('cpu'), torch.device('cpu'), 4); raise SystemExit('double install accepted')
except RuntimeError as e:
    assert 'already sharded' in str(e)
print('text shard CPU checks: ok')
