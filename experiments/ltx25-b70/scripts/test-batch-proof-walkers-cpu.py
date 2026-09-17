#!/usr/bin/env python3
"""CPU check: the batch-proof walkers stack batch-1 rows, share dicts, and keep scalars."""
import sys, types
from pathlib import Path
import torch
sys.path.insert(0, str(Path(__file__).resolve().parent))
for name in ('comfy', 'comfy.patcher_extension', 'encoder_diagnostics'):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules['comfy.patcher_extension'].WrappersMP = types.SimpleNamespace(DIFFUSION_MODEL='dm', CALC_COND_BATCH='ccb')
sys.modules['encoder_diagnostics']._context = lambda: (None, {})
import concurrent_cfg_node as n
x = torch.randn(1, 4, 3); ctx = [torch.randn(1, 5, 2), torch.randn(1, 6, 2)]; opts = {'k': torch.ones(1), 'cache': {}}
args = [x, torch.tensor([0.5]), ctx, None, 25, opts]
g = torch.Generator(device='cpu'); g.manual_seed(1)
second = n._map_rows(list(args), lambda t: n._perturb(t, g))
assert second[0].shape == x.shape and not torch.equal(second[0], x) and second[4] == 25 and second[5] is opts
stacked = n._stack_rows(list(args), second)
assert stacked[0].shape == (2, 4, 3) and torch.equal(stacked[0][0], x[0]) and torch.equal(stacked[0][1], second[0][0])
assert stacked[1].shape == (2,) and stacked[2][0].shape == (2, 5, 2) and stacked[2][1].shape == (2, 6, 2)
assert stacked[3] is None and stacked[4] == 25 and stacked[5] is opts, 'dicts and scalars must pass through'
assert torch.equal(n._rows(stacked[0], 1), second[0])
assert n._bits_equal(x, x.clone()) and not n._bits_equal(x, second[0])
kw = {'a_timestep': torch.tensor([0.5]), 'audio_length': 26, 'transformer_options': {'sigmas': torch.tensor([0.5]), 'cond_or_uncond': [0], 'patches_replace': {}}}
g2 = torch.Generator(device='cpu'); g2.manual_seed(2)
skw = {k: n._map_rows(v, lambda t: n._perturb(t, g2)) for k, v in kw.items()}
skw['transformer_options'] = n._perturb_options(skw['transformer_options'], g2)
st = {k: n._stack_rows(v, skw[k]) for k, v in kw.items()}
st['transformer_options'] = n._double_batch_lists(kw['transformer_options'], skw['transformer_options'])
assert st['a_timestep'].shape == (2,) and st['audio_length'] == 26
assert st['transformer_options']['sigmas'].shape == (2,) and st['transformer_options']['cond_or_uncond'] == [0, 0]
assert st['transformer_options']['patches_replace'] is kw['transformer_options']['patches_replace']
print('batch-proof walkers: ok (kwargs and options too)')
