"""Inactive actual tiny CLIP integration fixture, imported by guarded driver only."""
import gc
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-10/source')
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(LANE / 'scripts'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


# This unchanged fixture sets --cpu before importing the actual Comfy modules.
base = load('qualified_host_embedding_fixture', LANE / 'scripts/test-host-embedding-candidate-cpu-fixture-v2.py')
import torch
from torch import nn
import comfy.sd
import comfy.model_management as mm
load('encoder_diagnostics', SOURCE / 'scripts/encoder_diagnostics.py')
adapter = load('host_embedding_clip', LANE / 'scripts/host_embedding_clip_v2.py')
placement = load('host_embedding_placement_node', LANE / 'scripts/host_embedding_placement_node_v2.py')
CPU = torch.device('cpu')
TOKENS = [[(0, 1.0), (0, 1.0), (2, 1.0), (5, 1.0), (31, 1.0)]]


class TinyTokenizer:
    def __init__(self, **kwargs):
        pass

    def state_dict(self):
        return {}


class TinyTE(nn.Module):
    def __init__(self, dtype, device, model_options):
        super().__init__()
        if torch.device(device) != CPU or dtype != torch.bfloat16:
            raise RuntimeError('Tiny fixture allocates only BF16 CPU parameters')
        self.dtype = dtype
        self.dtypes = {dtype}
        self.gemma3_12b = nn.Module()
        self.gemma3_12b.transformer = nn.Module()
        self.gemma3_12b.transformer.model = base.Tiny()
        self.estimate_calls = []
        self.execution_device = None
        self.requires_grad_(False).eval()

    def get_dtype(self):
        return self.dtype

    def reset_clip_options(self):
        self.execution_device = None

    def set_clip_options(self, options):
        self.execution_device = options.get('execution_device', self.execution_device)

    def memory_estimation_function(self, tokens, device=None):
        value = 12345 + 17 * len(tokens)
        self.estimate_calls.append((id(tokens), device, value))
        return value

    def encode_token_weights(self, tokens):
        core = self.gemma3_12b.transformer.model
        ids = [[token for token, weight in section] for section in tokens]
        embeds, mask, counts, info = base.TokenFixture(core).process_tokens(ids, self.execution_device)
        return core.linear(embeds), None, {'attention_mask': mask}

    def load_sd(self, state):
        return self.load_state_dict(state, strict=False)


def construct(load_device=CPU):
    return comfy.sd.CLIP(target=SimpleNamespace(params={}, clip=TinyTE, tokenizer=TinyTokenizer),
        parameters=328, disable_dynamic=True,
        model_options={'load_device': load_device, 'offload_device': CPU,
                       'initial_device': CPU, 'dtype': torch.bfloat16})


def adapted(mode):
    # Physical CPU target naturally takes the constructor full-load branch.
    # Explicitly detach before testing the adapter's required unloaded boundary.
    original = construct()
    original.patcher.detach()
    group = adapter.ClipOwnership(original, mode)
    return adapter.HostEmbeddingCLIP.adopt(original, group)


def state_bytes(clip):
    return {name: (base.raw(value), str(value.dtype), tuple(value.shape), tuple(value.stride()))
            for name, value in clip.get_sd().items()}


def consume(clip):
    clip._host_embedding.consume_observations()


class Tests(unittest.TestCase):
    def test_factory_actual_constructor_no_preload(self):
        observed = []
        def tiny_loader(**kwargs):
            observed.append(kwargs)
            # Same real CLIP constructor and options, tiny CPU-created target.
            return comfy.sd.CLIP(target=SimpleNamespace(params={}, clip=TinyTE, tokenizer=TinyTokenizer),
                parameters=328, disable_dynamic=True, model_options=kwargs['model_options'])
        with patch.object(comfy.sd, 'load_clip', tiny_loader):
            clip = adapter.load_clip(ckpt_paths=['tiny-no-file'], embedding_directory=[], mode='host-table',
                model_options={'load_device': torch.device('xpu:2'), 'offload_device': CPU,
                               'dtype': torch.bfloat16})
        self.assertEqual(observed[0]['model_options']['initial_device'], CPU)
        self.assertEqual(clip.patcher.loaded_size(), 0)
        self.assertEqual(clip.patcher.load_device, torch.device('xpu:2'))
        self.assertTrue(all(p.device == CPU for p in clip.cond_stage_model.parameters()))
        self.assertEqual(clip._host_embedding.owner.host.model.embedding.weight.device.type, 'cpu')
        clip._host_embedding.detach_restore(clip)

    def test_actual_loader_estimator_both_owners_and_accounting(self):
        for mode in adapter.MODES:
            clip = adapted(mode)
            group = clip._host_embedding
            records = []
            original_load = mm.load_models_gpu
            def observe_load(models, **kwargs):
                records.append((list(models), dict(kwargs)))
                return original_load(models, **kwargs)
            # Force the private loader accounting path to recompute model size.
            clip.patcher.size = 0
            if group.owner is not None:
                group.owner.host.size = 0
            with patch.object(mm, 'load_models_gpu', observe_load):
                result = clip.load_model(TOKENS)
            self.assertIs(result, clip.patcher)
            self.assertEqual(records[0][1], {'memory_required': 12362})
            expected = [clip.patcher] + ([group.owner.host] if group.owner else [])
            self.assertEqual(records[0][0], expected)
            self.assertEqual(clip.cond_stage_model.estimate_calls[-1], (id(TOKENS), CPU, 12362))
            self.assertTrue(all(any(loaded.model is p for loaded in mm.current_loaded_models) for p in expected))
            report = group.inventory(clip, require_loaded=True)
            if group.owner:
                self.assertEqual(group.owner.host.loaded_size(), group.owner.host_bytes)
                self.assertEqual(clip.patcher.loaded_size() + group.owner.host.loaded_size(), group.original_bytes)
                self.assertEqual(report['host']['parameters']['count'], 1)
            group.detach_restore(clip)
            mm.unload_all_models()

    def test_clone_original_gc_state_refusals_and_complete_restore(self):
        original = construct()
        expected = state_bytes(original)
        original.patcher.detach()
        group = adapter.ClipOwnership(original, 'host-table')
        first = adapter.HostEmbeddingCLIP.adopt(original, group)
        del original
        first.load_model(TOKENS)
        second = first.clone()
        first_ref = weakref.ref(first)
        del first
        gc.collect()
        self.assertIsNone(first_ref())
        third = second.clone()
        second.load_model(TOKENS)
        refusals = [second.get_sd, second.state_dict_for_saving,
                    lambda: second.load_sd({}, full_model=True),
                    second.cond_stage_model.state_dict,
                    lambda: second.cond_stage_model.load_state_dict({}, strict=False),
                    lambda: second.cond_stage_model.gemma3_12b.transformer.model.linear.load_state_dict({}, strict=False),
                    group.owner.host.model.state_dict,
                    lambda: group.owner.host.model.embedding.load_state_dict({}, strict=False),
                    second.patcher.model_state_dict_for_saving]
        for call in refusals:
            with self.assertRaises(RuntimeError):
                call()
        with group.loader_state_access():
            self.assertEqual(mm.module_size(second.cond_stage_model) + mm.module_size(group.owner.host.model), group.original_bytes)
        report = group.detach_restore(second)
        self.assertTrue(report['original_ownership_restored'])
        self.assertEqual(report['after_host_registered_bytes'], 0)
        self.assertEqual(state_bytes(second), expected)
        self.assertEqual(state_bytes(third), expected)
        second.load_sd(second.get_sd(), full_model=True)
        self.assertEqual(state_bytes(second), expected)
        for clip in (second, third):
            with self.assertRaises(RuntimeError):
                clip.load_model(TOKENS)
        mm.unload_all_models()

    def test_exact_encoding_observations_and_conditioning_identity(self):
        reference = construct()
        expected = reference.encode_from_tokens(TOKENS, return_dict=True)
        for mode in adapter.MODES:
            clip = adapted(mode)
            conditioning = clip.encode_from_tokens_scheduled(TOKENS)
            actual = conditioning[0][0]
            self.assertEqual(base.raw(actual), base.raw(expected['cond']))
            self.assertEqual(actual.dtype, expected['cond'].dtype)
            self.assertEqual(actual.stride(), expected['cond'].stride())
            group = clip._host_embedding
            observed = json.loads(json.dumps(group.embedding_observations))
            self.assertEqual(len(observed), 1)
            self.assertEqual(observed[0]['input_ids'], {'shape': [1, 5], 'dtype': 'torch.int64', 'device': 'cpu'})
            self.assertEqual(observed[0]['scaled_embedding'], {'shape': [1, 5, 8], 'dtype': 'torch.float32', 'device': 'cpu'})
            with tempfile.TemporaryDirectory(prefix='host-placement-cpu-') as temp:
                root = Path(temp)
                run = root / 'encoder-server-fixture'
                run.mkdir()
                (root / 'model-verification.json').write_text('{"status":"passed"}')
                (run / 'server-identity.json').write_text('{"fixture":"CPU"}')
                with patch.object(placement, 'ROOT', root), patch.dict(os.environ, {'LTX_ENCODER_RUN_DIR': str(run)}):
                    result = placement.LTXHostEmbeddingPlacementCheck().check(clip, conditioning, 'cpu-r01-' + mode, mode)
                    self.assertIs(result[0], conditioning)
                    receipt = json.loads((run / ('host-embedding-placement-cpu-r01-' + mode + '.json')).read_text())
                    self.assertEqual(receipt['embedding_observations'], observed)
                    self.assertEqual(group.embedding_observations, [])
                    with self.assertRaises(RuntimeError):
                        placement.LTXHostEmbeddingPlacementCheck().check(clip, conditioning, 'cpu-r02-' + mode, mode)
            group.detach_restore(clip)
            mm.unload_all_models()

    def test_observation_bounds_and_no_tensor_retention(self):
        clip = adapted('host-table')
        group = clip._host_embedding
        clip.encode_from_tokens(TOKENS)
        frozen = json.loads(json.dumps(group.embedding_observations))
        self.assertEqual(frozen, group.embedding_observations)
        with self.assertRaises(RuntimeError):
            clip.encode_from_tokens(TOKENS)  # A placement receipt must consume first.
        consume(clip)
        group.observation_active = True
        ids = torch.tensor([[2]], dtype=torch.long)
        output = torch.empty((1, 1, 8), dtype=torch.float32)
        for _ in range(group.observation_limit):
            group.observe_embedding(None, (ids,), {'out_dtype': torch.float32}, output)
        with self.assertRaises(RuntimeError):
            group.observe_embedding(None, (ids,), {'out_dtype': torch.float32}, output)
        group.observation_active = False
        group.embedding_observations.clear()
        group.detach_restore(clip)
        mm.unload_all_models()

    def test_inference_mode_real_clip_adapter(self):
        with torch.inference_mode():
            clip = adapted('host-table')
            group = clip._host_embedding
            table = group.owner.weight
            clip.encode_from_tokens(TOKENS)
            self.assertFalse(group.owner.metadata()['weight_version_tracked'])
            consume(clip)
            group.detach_restore(clip)
            self.assertIs(clip.cond_stage_model.gemma3_12b.transformer.model.embed_tokens.weight, table)
            mm.unload_all_models()


TEST_NAMES = sorted(name for name in dir(Tests) if name.startswith('test_'))
