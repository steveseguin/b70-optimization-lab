#!/usr/bin/env python3
"""CPU check: the phased upsampler performs the sealed node's calls in order and returns its shape."""
import sys, types
from pathlib import Path
import torch
sys.path.insert(0, str(Path(__file__).resolve().parent))
calls = []
mm = types.ModuleType('comfy.model_management')
mm.load_models_gpu = lambda models, memory_required=0: calls.append(('load', len(models), memory_required))
mm.intermediate_device = lambda: torch.device('cpu')
sys.modules.setdefault('comfy', types.ModuleType('comfy')); sys.modules['comfy.model_management'] = mm
sys.modules.setdefault('encoder_diagnostics', types.ModuleType('encoder_diagnostics'))
sys.modules['encoder_diagnostics']._context = lambda: (None, {})
import phase_timed_upsampler_node as n
n._sync_all = lambda: None

class Stats(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.register_buffer('std-of-means', torch.full((4,), 2.0)); self.register_buffer('mean-of-means', torch.full((4,), 1.0))
    def un_normalize(self, x): calls.append(('un_normalize',)); return x * 2 + 1
    def normalize(self, x): calls.append(('normalize',)); return (x - 1) / 2
class Model(torch.nn.Module):
    def forward(self, x): calls.append(('forward', tuple(x.shape), x.dtype)); return torch.nn.functional.interpolate(x.flatten(0, 1).unsqueeze(0), scale_factor=(1, 2, 2))[0].reshape(x.shape[0], x.shape[1], x.shape[2], x.shape[3] * 2, x.shape[4] * 2)
up = types.SimpleNamespace(load_device=torch.device('cpu'), model=Model(), model_dtype=lambda: torch.float32)
vae = types.SimpleNamespace(first_stage_model=types.SimpleNamespace(per_channel_statistics=Stats()))
x = torch.randn(1, 4, 2, 3, 3, dtype=torch.bfloat16)
out, detail = n.phased_upsample({'samples': x, 'noise_mask': 1}, up, vae)
assert out['samples'].shape == (1, 4, 2, 6, 6) and out['samples'].dtype == torch.bfloat16 and 'noise_mask' not in out, out['samples'].shape
assert [c[0] for c in calls] == ['load', 'un_normalize', 'forward', 'normalize'], calls
assert calls[0][2] == 1 * 4 * 2 * 3 * 3 * 3000.0 and calls[2][1] == (1, 4, 2, 3, 3) and calls[2][2] == torch.float32
assert [p['phase'] for p in detail['phases']] == ['load_models_gpu', 'latent_to_model_device', 'un_normalize', 'forward', 'normalize', 'to_intermediate_device']
print('phase-timed upsampler CPU check passed:', detail['phases'])
