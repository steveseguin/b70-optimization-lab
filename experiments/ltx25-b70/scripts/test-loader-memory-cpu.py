#!/usr/bin/env python3
"""Tiny Torch CPU gate for the exact candidate AST; no Comfy/model imports."""
import ast
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

assert os.environ.get('OMP_NUM_THREADS') == '1'
assert os.environ.get('MKL_NUM_THREADS') == '1'

LANE = Path(__file__).resolve().parents[1]
CANDIDATE = LANE / 'data/loader-memory-candidate-02'
OUTPUT = LANE / 'data/loader-memory-cpu-01'
OUTPUT.mkdir(exist_ok=False)
manifest_bytes = (CANDIDATE / 'manifest.json').read_bytes()
manifest = json.loads(manifest_bytes)
assert manifest['parent_manifest_sha256'] == 'f1fc467a4620caabac9065e72fb7fd1628db437d1c977c86237bb0378ef8f952'
change, = [c for c in manifest['changes'] if c['path'] == 'source/comfy/sd.py']
source_bytes = (CANDIDATE / change['path']).read_bytes()
assert hashlib.sha256(source_bytes).hexdigest() == change['after_sha256']
assert hashlib.sha256((CANDIDATE / change['patch']).read_bytes()).hexdigest() == change['patch_sha256']

# Execute only the candidate's assignment statements, with real nn.Module
# loading and tiny synthetic tensors. Everything else in Comfy is unimported.
tree = ast.parse(source_bytes)
loader, = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'load_diffusion_model_state_dict']
start = next(i for i, n in enumerate(loader.body) if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'native_assign' for t in n.targets))
end = next(i for i in range(start, len(loader.body)) if isinstance(loader.body[i], ast.Expr)
           and isinstance(loader.body[i].value, ast.Call)
           and isinstance(loader.body[i].value.func, ast.Attribute)
           and loader.body[i].value.func.attr == 'load_model_weights')
fragment = ast.Module(body=loader.body[start:end + 1], type_ignores=[])
fragment = ast.fix_missing_locations(fragment)
fragment_text = ast.unparse(fragment)
(OUTPUT / 'extracted-candidate.py').write_text(fragment_text + '\n')

import torch

initial = {'torch': torch.__version__, 'default_dtype': str(torch.get_default_dtype()),
           'default_device': str(torch.get_default_device()),
           'num_threads': torch.get_num_threads(), 'num_interop_threads': torch.get_num_interop_threads(),
           'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
           'deterministic_warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
           'xpu_initialized': torch.xpu.is_initialized(),
           'OMP_NUM_THREADS': os.environ['OMP_NUM_THREADS'], 'MKL_NUM_THREADS': os.environ['MKL_NUM_THREADS']}
assert not initial['xpu_initialized'] and initial['default_device'] == 'cpu'
torch.set_num_threads(1)

# Values straddle round-to-nearest-even BF16 boundaries, including signs,
# exact halfway values, odd/even mantissas, signed zeros and tiny subnormals.
bits = [0, 0x80000000, 0x3f807fff, 0x3f808000, 0x3f808001,
        0x3f817fff, 0x3f818000, 0x3f818001, 0xbf808000,
        0xbf818000, 0x00008000, 0x00008001, 0x80008000, 0x80008001]
n = len(bits)
source_table = torch.tensor(bits, dtype=torch.int64).to(torch.int32).view(torch.float32)
source_weight = (torch.arange(n*n, dtype=torch.float32).reshape(n, n) / 32).to(torch.bfloat16)
state = {'weight': source_weight, 'table': source_table}
original = {k: v.clone() for k, v in state.items()}


class TinyNative(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.empty((n, n), dtype=torch.bfloat16), requires_grad=False)
        self.register_buffer('table', torch.empty(n, dtype=torch.bfloat16))

    def forward(self, x):
        return torch.nn.functional.linear(x, self.weight) + self.table


class ModelWrapper:
    def __init__(self):
        self.diffusion_model = TinyNative()

    def load_model_weights(self, sd, prefix, assign=False):
        assert prefix == ''
        result = self.diffusion_model.load_state_dict(sd, strict=False, assign=assign)
        assert not result.missing_keys and not result.unexpected_keys


def candidate(sd, enabled=True):
    model = ModelWrapper()
    patcher = SimpleNamespace(is_dynamic=lambda: False)
    values = {'torch': torch, 'comfy': SimpleNamespace(memory_management=SimpleNamespace(aimdo_enabled=False)),
              'model': model, 'model_patcher': patcher, 'new_sd': dict(sd),
              'model_options': {'ltx_native_bf16_assign': enabled},
              'custom_operations': None,
              'model_config': SimpleNamespace(quant_config=None, unet_config={'image_model': 'ltxav'}),
              'unet_dtype': torch.bfloat16, 'offload_device': torch.device('cpu')}
    exec(compile(fragment, str(CANDIDATE / change['path']), 'exec'), values)
    return model.diffusion_model, patcher


def same_bytes(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and torch.equal(a.view(torch.uint8), b.view(torch.uint8))


try:
    baseline = TinyNative()
    baseline.load_state_dict(state, strict=True, assign=False)
    assigned, patcher = candidate(state)
    control, _ = candidate(state, enabled=False)
    equal = {k: same_bytes(baseline.state_dict()[k], assigned.state_dict()[k]) for k in state}
    assert all(equal.values())
    assert all(same_bytes(baseline.state_dict()[k], control.state_dict()[k]) for k in state)
    assert all(same_bytes(state[k], original[k]) for k in state), 'source state changed'
    assert assigned.weight.data_ptr() == source_weight.data_ptr(), 'matching dtype should retain source storage'
    assert assigned.table.data_ptr() != source_table.data_ptr(), 'dtype conversion needs distinct storage'
    x = torch.ones((1, n), dtype=torch.bfloat16)
    forward_equal = same_bytes(baseline(x), assigned(x))
    assert forward_equal
    rejections = {}
    bad_states = {'missing_key': {'weight': source_weight},
                  'unexpected_key': {**state, 'unexpected': torch.ones(1)},
                  'noncontiguous_stride': {**state, 'weight': source_weight.t()},
                  'wrong_shape': {**state, 'weight': source_weight[:1]}}
    for name, bad in bad_states.items():
        try:
            candidate(bad)
        except RuntimeError as error:
            rejections[name] = str(error)
        else:
            raise AssertionError('candidate accepted ' + name)
    post_xpu = torch.xpu.is_initialized()
    assert not post_xpu
    assert all(t.device.type == 'cpu' for t in list(assigned.parameters()) + list(assigned.buffers()))
    report = {'status': 'passed-small-cpu-semantics-only', 'initial_defaults': initial,
              'effective_num_threads': torch.get_num_threads(), 'post_xpu_initialized': post_xpu,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'candidate_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
              'candidate_source_sha256': change['after_sha256'], 'candidate_patch_sha256': change['patch_sha256'],
              'extracted_ast_sha256': hashlib.sha256(fragment_text.encode()).hexdigest(),
              'synthetic_source_table_f32_bits': [hex(b) for b in bits],
              'exact_parameter_buffer_bytes': equal, 'exact_cpu_forward_bytes': forward_equal,
              'matching_dtype_source_alias_preserved': True, 'conversion_uses_distinct_storage': True,
              'source_unchanged': True, 'candidate_disabled_matches_baseline': True,
              'rejections': rejections, 'assignment_report': patcher._ltx_native_assign_report,
              'limitations': ['No Comfy imports or native checkpoint loaded',
                  'No GPU operations, enumeration, compilation, or device/host setting changes',
                  'Native checkpoint parity, tied/overlapping alias constraints, memory saving and driver stability unqualified']}
except BaseException as error:
    report = {'status': 'failed', 'initial_defaults': initial, 'error': repr(error),
              'post_xpu_initialized': torch.xpu.is_initialized()}
    (OUTPUT / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    raise
(OUTPUT / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
