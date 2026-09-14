#!/usr/bin/env python3
"""CPU-only tiny real Gemma4 state/lifecycle tests; never edits the runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest

SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
LANE = Path(__file__).resolve().parents[1]
PIN = '19e1058f4c445ef74047e77a23f9ca7684c1e4b6'
sys.path.insert(0, str(SOURCE))
sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-pinned-memory', '--disable-async-offload']
import comfy.options
comfy.options.enable_args_parsing()
import torch
from torch import nn
import comfy.model_patcher as mp
import comfy.ops
from comfy.text_encoders.gemma4 import Gemma4Config, TransformerBlockGemma4
from comfy.text_encoders.llama import RMSNorm

CPU = torch.device('cpu')
spec = importlib.util.spec_from_file_location('helpers', LANE / 'scripts/test-encoder-candidates.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
name = 'comfy/model_patcher.py'
original = subprocess.check_output(['git', '-C', str(SOURCE), 'show', f'{PIN}:{name}'], text=True)
if (SOURCE / name).read_text() != original:
    raise RuntimeError('Runtime source differs from pinned source')
patch = LANE / 'patches/encoder-small-state-residency.patch'
candidate = helpers.apply_patch_in_memory({name: original}, patch.read_text())[name]
class Candidate(mp.ModelPatcher):
    pass
for method in ('_ltx_small_state', 'load', 'partially_unload', 'unpatch_model'):
    setattr(Candidate, method, helpers.extract(candidate, 'ModelPatcher', dict(vars(mp)), method))

class TinyGemma(nn.Module):
    def __init__(self):
        super().__init__()
        config = Gemma4Config(hidden_size=8, intermediate_size=16, num_hidden_layers=2,
                              num_attention_heads=2, num_key_value_heads=1,
                              hidden_size_per_layer_input=0, num_kv_shared_layers=0)
        config.head_dim = 4
        config.global_head_dim = 4
        config.sliding_attention = None
        self.layers = nn.ModuleList([TransformerBlockGemma4(config, i, device=CPU,
                                    dtype=torch.bfloat16, ops=comfy.ops.manual_cast) for i in range(2)])
        self.norm = RMSNorm(8, device=CPU, dtype=torch.bfloat16)
        with torch.no_grad():
            for i, parameter in enumerate(self.parameters()):
                parameter.fill_((i + 1) / 128)
            for layer in self.layers:
                layer.layer_scalar.fill_(0.5)
    def get_dtype(self):
        return torch.bfloat16
    def forward(self, x):
        # Real block arithmetic, including attention and original scalar cast.
        freqs = torch.eye(2, dtype=x.dtype).expand(1, 1, x.shape[1], 2, 2, 2).contiguous()
        for layer in self.layers:
            x, _, _ = layer(x.clone(), freqs_cis=(freqs, freqs))
        return self.norm(x)

def make(enabled=True, cls=Candidate):
    p = cls(TinyGemma(), CPU, CPU)
    p.model_options['ltx_small_state_residency'] = enabled
    return p

def hashes(p):
    return {k: hashlib.sha256(v.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
            for k, v in p.model.state_dict().items()}

def output(p):
    with torch.inference_mode():
        return p.model(torch.arange(24, dtype=torch.bfloat16).reshape(1, 3, 8) / 32).clone()

def accounted(p):
    weights = sum(row[1] for row in p._load_list() if getattr(row[3], 'comfy_patched_weights', False))
    buffers = sum(m._buffers[k].nbytes for m, k in p._ltx_small_state()[1]) if getattr(p.model, '_ltx_small_buffers_loaded', False) else 0
    return weights + buffers

class Tests(unittest.TestCase):
    budget = 1600
    def test_pinned_load_list_omits_direct_scalar_buffers(self):
        p = make()
        listed = sum(row[1] for row in p._load_list())
        self.assertEqual(p.model_size() - listed, 4)
        self.assertEqual(len(p._ltx_small_state()[0]), 13)
        self.assertEqual(len(p._ltx_small_state()[1]), 2)
    def test_partial_load_prioritizes_norms_and_accounts_buffers(self):
        p = make()
        before, expected = hashes(p), output(p)
        p.load(CPU, lowvram_model_memory=self.budget)
        for row in p._load_list():
            if row[2] in p._ltx_small_state()[0]:
                self.assertTrue(getattr(row[3], 'comfy_patched_weights', False))
        self.assertTrue(p.model._ltx_small_buffers_loaded)
        self.assertEqual(p.loaded_size(), accounted(p))
        self.assertLess(p.loaded_size(), p.model_size())
        self.assertEqual(hashes(p), before)
        self.assertTrue(torch.equal(output(p), expected))
    def test_partial_reload_repeats_preserve_accounting_and_values(self):
        p = make()
        before, expected = hashes(p), output(p)
        p.load(CPU, lowvram_model_memory=self.budget)
        initial = p.loaded_size()
        for _ in range(4):
            p.partially_load(CPU, extra_memory=0.1)
            self.assertEqual(p.loaded_size(), accounted(p))
            self.assertEqual(p.loaded_size(), initial)
            self.assertEqual(hashes(p), before)
            self.assertTrue(torch.equal(output(p), expected))
    def test_partial_unload_prefers_large_weights_before_norms(self):
        p = make()
        p.load(CPU, lowvram_model_memory=self.budget)
        p.partially_unload(CPU, memory_to_free=1)
        self.assertEqual(p.loaded_size(), accounted(p))
        for row in p._load_list():
            if row[2] in p._ltx_small_state()[0]:
                self.assertTrue(getattr(row[3], 'comfy_patched_weights', False))
        self.assertTrue(p.model._ltx_small_buffers_loaded)
    def test_complete_partial_unload_then_reload_preserves_registered_state(self):
        p = make()
        before, expected = hashes(p), output(p)
        p.load(CPU, full_load=True)
        self.assertEqual(p.loaded_size(), p.model_size())
        total = p.loaded_size()
        self.assertEqual(p.partially_unload(CPU, memory_to_free=1e9), total)
        self.assertEqual(p.loaded_size(), 0)
        self.assertFalse(p.model._ltx_small_buffers_loaded)
        p.partially_load(CPU, extra_memory=self.budget)
        self.assertEqual(p.loaded_size(), accounted(p))
        self.assertEqual(hashes(p), before)
        self.assertTrue(torch.equal(output(p), expected))
    def test_detach_shared_clone_and_reload(self):
        p = make()
        before = hashes(p)
        p.load(CPU, lowvram_model_memory=self.budget)
        clone = p.clone()
        self.assertIsInstance(clone, Candidate)
        self.assertIs(clone.model, p.model)
        self.assertTrue(clone.model_options['ltx_small_state_residency'])
        clone.detach()
        self.assertEqual(p.loaded_size(), 0)
        self.assertFalse(p.model._ltx_small_buffers_loaded)
        p.partially_load(CPU, extra_memory=self.budget)
        self.assertEqual(p.loaded_size(), accounted(p))
        self.assertEqual(hashes(p), before)
    def test_rejects_inadequate_budget_before_setting_loaded_state(self):
        p = make()
        with self.assertRaisesRegex(RuntimeError, 'budget'):
            p.load(CPU, lowvram_model_memory=1)
        self.assertFalse(getattr(p.model, '_ltx_small_buffers_loaded', False))
    def test_disabled_candidate_keeps_original_first_load_placement(self):
        p, control = make(False), make(False, mp.ModelPatcher)
        for model in (p, control):
            model.load(CPU, lowvram_model_memory=self.budget)
        self.assertEqual(p.loaded_size(), control.loaded_size())
        self.assertEqual([row[2] for row in p._load_list() if getattr(row[3], 'comfy_patched_weights', False)],
                         [row[2] for row in control._load_list() if getattr(row[3], 'comfy_patched_weights', False)])
    def test_rejects_budget_that_covers_state_but_not_cast_reserve(self):
        p = make()
        norms, buffers = p._ltx_small_state()
        small = sum(row[1] for row in p._load_list() if row[2] in norms) + sum(m._buffers[k].nbytes for m, k in buffers)
        with self.assertRaisesRegex(RuntimeError, 'cast reserve'):
            p.load(CPU, lowvram_model_memory=small + 1)
    def test_rejects_dynamic_hooks_and_object_patches(self):
        for field in ('hook_patches', 'object_patches'):
            p = make()
            setattr(p, field, {'unsupported': object()})
            with self.assertRaisesRegex(RuntimeError, 'patches/hooks'):
                p._ltx_small_state()
        p = make()
        p.is_dynamic = lambda: True
        with self.assertRaisesRegex(RuntimeError, 'static'):
            p._ltx_small_state()
    def test_option_cannot_be_disabled_while_buffers_are_loaded(self):
        p = make()
        p.load(CPU, lowvram_model_memory=self.budget)
        p.model_options['ltx_small_state_residency'] = False
        with self.assertRaisesRegex(RuntimeError, 'Detach'):
            p.load(CPU, lowvram_model_memory=self.budget)
        p.detach()
        self.assertEqual(p._ltx_small_state(), (set(), []))
    def test_rejects_weight_patches(self):
        p = make()
        p.add_patches({'norm.weight': (torch.zeros(8, dtype=torch.bfloat16),)})
        with self.assertRaisesRegex(RuntimeError, 'patches/hooks'):
            p.load(CPU, lowvram_model_memory=self.budget)

if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'passed': result.wasSuccessful(), 'tests_run': result.testsRun,
                      'source_commit': PIN, 'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
                      'scope': 'Real tiny BF16 Gemma4 blocks and ModelPatcher on CPU; not XPU residency/performance/parity evidence'}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
