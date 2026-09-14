#!/usr/bin/env python3
"""Prepared CPU proof; run only after the parent schedules native CPU work.

Imports actual frozen ops/ScaledEmbedding/ModelPatcher with --cpu, then tests
actual SDClipModel.process_tokens extracted from the pinned source. Never
launches an endpoint or queries an accelerator. CPU equality is not XPU proof.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import logging
import numbers
from pathlib import Path
import sys
import unittest

SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-10/source')
LANE = Path(__file__).resolve().parents[1]
PINS = {
    'comfy/text_encoders/llama.py': '7a1c57dd6e94ff1731f4cc6d98db2baaf8fed03e2fe996f79e49e06d9199717f',
    'comfy/sd1_clip.py': 'fc2c7e8442e00d525740699c936a00e93a87f58d7c63a1c23a87cd96226962f8',
    'comfy/ops.py': '6058f688d936b083c49fa49a57964837476db6d95750ea70198ad60e884ffed0',
    'comfy/model_patcher.py': '768d9b6f24b632dffba9e4c3c2d2962b3c309bf33182cf599d8c9abda2125d99',
}
for name, expected in PINS.items():
    if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != expected:
        raise RuntimeError('CPU fixture source identity changed: ' + name)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE))
sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-pinned-memory', '--disable-async-offload']
import comfy.options
comfy.options.enable_args_parsing()
import torch
from torch import nn
import comfy.ops
from comfy.model_patcher import ModelPatcher
from comfy.text_encoders.llama import _make_scaled_embedding

spec = importlib.util.spec_from_file_location('host_embedding_candidate', LANE / 'scripts/ltx_host_embedding_candidate.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
tree = ast.parse((SOURCE / 'comfy/sd1_clip.py').read_text())
clazz = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'SDClipModel')
method = next(node for node in clazz.body if isinstance(node, ast.FunctionDef) and node.name == 'process_tokens')
namespace = {'torch': torch, 'numbers': numbers, 'logging': logging}
exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-process-tokens>', 'exec'), namespace)


class Tiny(nn.Module):
    def __init__(self):
        super().__init__()
        self.embed_tokens = _make_scaled_embedding(comfy.ops.manual_cast, 32, 8, 8 ** .5, 'cpu', torch.bfloat16)
        self.linear = comfy.ops.manual_cast.Linear(8, 8, dtype=torch.bfloat16, device='cpu')
        with torch.no_grad():
            self.embed_tokens.weight.copy_(torch.arange(256).reshape(32, 8).to(torch.bfloat16) / 16 - 8)
            self.embed_tokens.weight[0, 0] = -0.0
            self.linear.weight.fill_(.125)
            self.linear.bias.zero_()
        self.requires_grad_(False).eval()

    def get_input_embeddings(self):
        return self.embed_tokens


class TokenFixture:
    process_tokens = namespace['process_tokens']
    special_tokens = {'start': 2, 'pad': 0}

    def __init__(self, model):
        self.transformer = model


def make():
    model = Tiny()
    patcher = ModelPatcher(model, torch.device('cpu'), torch.device('cpu'))
    return model, patcher


def raw(tensor):
    return tensor.detach().contiguous().view(torch.uint8).numpy().tobytes()


class Tests(unittest.TestCase):
    def test_actual_token_processing_and_rows(self):
        self.assertNotEqual(raw(torch.tensor([0.0])), raw(torch.tensor([-0.0])))
        for tokens in ([[0, 0, 2, 5, 5, 31]], [[2, 1, 7], [0, 2, 31]], [[0] * 1023 + [2]]):
            model, patcher = make()
            fixture = TokenFixture(model)
            reference = fixture.process_tokens(tokens, torch.device('cpu'))
            owner = candidate.HostEmbeddingOwner(patcher, model)
            patcher.patch_model(torch.device('cpu'))
            actual = fixture.process_tokens(tokens, torch.device('cpu'))
            for index in (0, 1):
                self.assertTrue(torch.equal(reference[index], actual[index]))
                self.assertEqual(raw(reference[index]), raw(actual[index]))
                self.assertEqual(reference[index].dtype, actual[index].dtype)
                self.assertEqual(reference[index].stride(), actual[index].stride())
            self.assertEqual(reference[2:], actual[2:])
            patcher.detach()
            owner.restore()

    def test_ownership_full_load_clone_detach_restore(self):
        model, patcher = make()
        original = {key: value.clone() for key, value in model.state_dict().items()}
        owner = candidate.HostEmbeddingOwner(patcher, model)
        clone = patcher.clone()
        self.assertEqual(owner.metadata()['clone_count'], 2)
        self.assertNotIn('embed_tokens.weight', model.state_dict())
        self.assertIn('embedding.weight', owner.host.model.state_dict())
        owner.host.patch_model(torch.device('cpu'))
        self.assertEqual(owner.host.loaded_size(), owner.host_bytes)
        patcher.patch_model(torch.device('cpu'))
        owner.guard(require_resident=True)
        self.assertEqual(patcher.loaded_size() + owner.host_bytes, owner.original_size)
        clone.partially_load(torch.device('cpu'), .1)
        with self.assertRaises(RuntimeError):
            owner.restore()
        clone.detach()
        owner.restore()
        self.assertEqual(patcher.model_size(), owner.original_size)
        self.assertEqual(clone.model_size(), owner.original_size)
        for key, value in model.state_dict().items():
            self.assertTrue(torch.equal(original[key], value))
            self.assertEqual(raw(original[key]), raw(value))
        with self.assertRaises(RuntimeError):
            owner.delegate(torch.tensor([[2]]), out_dtype=torch.float32)

    def test_inference_construction_preserves_original_table(self):
        with torch.inference_mode():
            model, patcher = make()
            table = model.embed_tokens.weight
            owner = candidate.HostEmbeddingOwner(patcher, model)
            self.assertIs(owner.host.model.embedding.weight, table)
            self.assertTrue(owner.metadata()['inference_tensor'])
            self.assertFalse(owner.metadata()['weight_version_tracked'])
            owner.host.patch_model(torch.device('cpu'))
            patcher.patch_model(torch.device('cpu'))
            owner.delegate(torch.tensor([[0, 2, 31]]), out_dtype=torch.float32)
            patcher.detach()
            owner.restore()
            self.assertIs(model.embed_tokens.weight, table)
            self.assertEqual(owner.host.loaded_size(), 0)

    def test_install_failure_restores_original_registration(self):
        model, patcher = make()
        original = model.embed_tokens
        size = patcher.model_size()
        def reject(*args):
            raise RuntimeError('fixture registration failure')
        patcher.add_callback_with_key = reject
        with self.assertRaises(RuntimeError):
            candidate.HostEmbeddingOwner(patcher, model)
        self.assertIs(model.embed_tokens, original)
        self.assertEqual(patcher.model_size(), size)

    def test_invalidations(self):
        mutations = [lambda owner: owner.weight.add_(1),
                     lambda owner: setattr(owner.host.model.embedding, 'padding_idx', 0),
                     lambda owner: setattr(owner.host.model.embedding, 'weight', nn.Parameter(owner.weight.clone(), requires_grad=False)),
                     lambda owner: setattr(owner.host.model.embedding, 'training', True)]
        for mutation in mutations:
            model, patcher = make()
            owner = candidate.HostEmbeddingOwner(patcher, model)
            with torch.no_grad():
                mutation(owner)
            with self.assertRaises(RuntimeError):
                owner.guard()

    def test_reject_preload_hooks_and_nonresident_accounting(self):
        model, patcher = make()
        patcher.patch_model(torch.device('cpu'))
        with self.assertRaises(RuntimeError):
            candidate.HostEmbeddingOwner(patcher, model)
        patcher.detach()
        owner = candidate.HostEmbeddingOwner(patcher, model)
        with self.assertRaises(RuntimeError):
            owner.delegate(torch.tensor([[2]]), out_dtype=torch.float32)
        patcher.patch_model(torch.device('cpu'))
        clone = patcher.clone()
        clone.object_patches['unexpected'] = True
        with self.assertRaises(RuntimeError):
            owner.guard()


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status': 'passed' if result.wasSuccessful() else 'failed',
        'tests': result.testsRun, 'scope': 'Actual CPU embedding/token/patcher code; not accelerator residency or performance proof',
        'source_sha256s': PINS, 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'candidate_sha256': hashlib.sha256((LANE / 'scripts/ltx_host_embedding_candidate.py').read_bytes()).hexdigest(),
        'native_gpu_requests': 0}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
