#!/usr/bin/env python3
"""Inactive encoder patches tested in memory; CPU tiny models, no source edits."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

LANE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('policy', LANE / 'scripts/test-encoder-small-state-policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
b = policy.base
import torch
import comfy.sd as sd
import comfy.sd1_clip as clip_impl
import comfy.text_encoders.lt as lt

PATCHES = ['encoder-small-state-residency.patch', 'encoder-small-state-policy-guard.patch',
           'encoder-crop-before-cpu-opt-in.patch', 'encoder-clip-options.patch', 'resident-node-encoder-options.patch']
NAMES = ['comfy/model_patcher.py', 'comfy/sd1_clip.py', 'comfy/text_encoders/lt.py', 'comfy/sd.py']
original = {n: (b.SOURCE / n).read_text() for n in NAMES}
original['scripts/resident_node.py'] = (LANE / 'scripts/resident_node.py').read_text()
candidate = original.copy()
for p in PATCHES:
    candidate = b.helpers.apply_patch_in_memory(candidate, (LANE / 'patches' / p).read_text())
class TokenEncoder(b.helpers.extract(candidate['comfy/sd1_clip.py'], 'ClipTokenWeightEncoder', dict(vars(clip_impl))), torch.nn.Module):
    def __init__(self, device=None, dtype=None, **kwargs):
        torch.nn.Module.__init__(self)
        self.transformer = torch.nn.Module()
        self.transformer.model = b.TinyGemma()
        self.transformer.model.config = types.SimpleNamespace(hidden_size=8, num_hidden_layers=2)
        self.operations = b.comfy.ops.manual_cast
        self.special_tokens = {}
        self.crop_calls = []
    def encode(self, tokens):
        mask = torch.tensor([[int(x != 0) for x in section] for section in tokens], dtype=torch.long)
        x = torch.arange(len(tokens) * len(tokens[0]) * 8, dtype=torch.bfloat16).reshape(len(tokens), len(tokens[0]), 8) / 32
        with torch.inference_mode():
            out = self.transformer.model(x)
        return torch.stack((out, out * 0.5, out * 0.25), dim=1), None, {'attention_mask': mask}
    def encode_token_weights(self, values, **kwargs):
        self.crop_calls.append(kwargs.copy())
        return super().encode_token_weights(values, **kwargs)

PatchedLTX = b.helpers.extract(candidate['comfy/text_encoders/lt.py'], 'LTXAVTEModel', dict(vars(lt)))
class PatchedCLIP(sd.CLIP):
    __init__ = b.helpers.extract(candidate['comfy/sd.py'], 'CLIP', dict(vars(sd)), '__init__')

TARGET = types.SimpleNamespace(clip=PatchedLTX, tokenizer=lambda **kwargs: object(), params={
    'dtype_llama': torch.bfloat16, 'text_encoder_model': TokenEncoder,
    'text_projection_type': 'dual_linear', 'video_projection_dim': 8, 'audio_projection_dim': 4})
FLAGS = {'control': (False, False), 'crop': (True, False), 'small_state': (False, True), 'combined': (True, True)}

def make_clip(options, cls=PatchedCLIP):
    opts = {'load_device': b.CPU, 'offload_device': b.CPU, 'initial_device': b.CPU, 'dtype': torch.bfloat16, **options}
    with patch.object(b.mp, 'CoreModelPatcher', policy.GuardedCandidate), patch.object(b.mp, 'ModelPatcher', policy.GuardedCandidate):
        clip = cls(target=TARGET, model_options=opts)
    with torch.no_grad():
        for i, tensor in enumerate(clip.cond_stage_model.parameters()):
            tensor.fill_((i + 1) / 128)
    clip.cond_stage_model.execution_device = b.CPU
    return clip

def native_load(models, **kwargs):
    for p in models:
        p.patch_model(b.CPU)

class Tests(unittest.TestCase):
    def test_constructor_flags_precede_first_possible_load_and_clone(self):
        for variant, (crop, small) in FLAGS.items():
            observations = []
            def inspect(models, **kwargs):
                p = models[0]
                observations.append((p.model.ltx_crop_before_cpu, p.model_options.get('ltx_small_state_residency', False)))
                native_load(models, **kwargs)
            with patch.object(sd.model_management, 'load_models_gpu', side_effect=inspect):
                clip = make_clip({'ltx_crop_before_cpu': crop, 'ltx_small_state_residency': small})
            self.assertEqual(observations, [(crop, small)], variant)
            clone = clip.clone()
            self.assertEqual(clone.patcher.model_options.get('ltx_small_state_residency', False), small)
            self.assertIs(clone.cond_stage_model, clip.cond_stage_model)
    def test_four_variants_keep_tiny_encoder_and_projection_math_exact(self):
        results = []
        for variant, (crop, small) in FLAGS.items():
            with patch.object(sd.model_management, 'load_models_gpu', side_effect=native_load):
                clip = make_clip({'ltx_crop_before_cpu': crop, 'ltx_small_state_residency': small})
            rows = []
            for valid in (1, 3, 8):
                tokens = {'gemma3_12b': [[(int(i >= 8-valid), 1.0) for i in range(8)]]}
                with torch.inference_mode():
                    rows.append(clip.cond_stage_model.encode_token_weights(tokens)[0])
            calls = clip.cond_stage_model.gemma3_12b.crop_calls
            self.assertEqual(calls, [{'crop_to_attention_mask': True}] * 3 if crop else [{}] * 3)
            results.append(rows)
        for rows in results[1:]:
            for actual, expected in zip(rows, results[0]):
                self.assertTrue(torch.equal(actual, expected))
    def test_control_matches_original_ltx_projection_forward(self):
        with patch.object(sd.model_management, 'load_models_gpu', side_effect=native_load):
            clip = make_clip({})
        tokens = {'gemma3_12b': [[(int(i >= 5), 1.0) for i in range(8)]]}
        with torch.inference_mode():
            expected = lt.LTXAVTEModel.encode_token_weights(clip.cond_stage_model, tokens)[0]
            actual = clip.cond_stage_model.encode_token_weights(tokens)[0]
        self.assertTrue(torch.equal(actual, expected))
        self.assertNotIn('ltx_small_state_residency', clip.patcher.model_options)
    def test_resident_variants_unload_before_replacement_and_write_new_receipts(self):
        mod = types.ModuleType('inactive_encoder_resident')
        # Import dependencies resolves the frozen shard helper, but no calls use GPUs.
        import sys
        sys.path.insert(0, str(LANE / 'scripts'))
        exec(compile(candidate['scripts/resident_node.py'], 'inactive:resident_node.py', 'exec'), mod.__dict__)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / 'encoder-server-cpu-test'
            run.mkdir()
            (root/'model-verification.json').write_text('{"status":"passed"}')
            events, owned = [], []
            def load_clip(**kwargs):
                events.append('load')
                clip = make_clip(kwargs['model_options'])
                owned.append(clip)
                return clip
            def unload():
                events.append('unload')
                for clip in owned:
                    clip.patcher.detach()
                owned.clear()
            with patch.object(mod, 'ROOT', root), patch.dict(os.environ, {'LTX_ENCODER_RUN_DIR': str(run)}), \
                 patch.object(mod.nodes.UNETLoader, 'load_unet', return_value=(types.SimpleNamespace(load_device=b.CPU),)), \
                 patch.object(mod.comfy.sd, 'load_clip', side_effect=load_clip), \
                 patch.object(mod.comfy.model_management, 'load_models_gpu', side_effect=native_load), \
                 patch.object(mod.comfy.model_management, 'unload_all_models', side_effect=unload), \
                 patch.object(mod.comfy.model_management, 'cleanup_models_gc'), \
                 patch.object(mod.nodes.VAELoader, 'load_vae', side_effect=lambda *a: (types.SimpleNamespace(device=b.CPU),)), \
                 patch.object(mod.folder_paths, 'get_full_path_or_raise', return_value='/verified/tiny'), \
                 patch.object(mod.folder_paths, 'get_folder_paths', return_value=[]), \
                 patch.object(mod.LatentUpscaleModelLoader, 'execute', return_value=(object(),)):
                node = mod.LTXResidentComponents()
                for variant, flags in FLAGS.items():
                    components = node.load('single', variant)
                    self.assertIs(components, node.load('single', variant))
                    self.assertEqual(len(owned), 1)
                    self.assertEqual(components[1].cond_stage_model.ltx_crop_before_cpu, flags[0])
                self.assertEqual(events, ['load', 'unload', 'load', 'unload', 'load', 'unload', 'load'])
                receipts = list(run.glob('components-*.json'))
                self.assertEqual(len(receipts), 4)
                self.assertEqual({json.loads(p.read_text())['encoder_variant'] for p in receipts}, set(FLAGS))
                # An occupied receipt path is never overwritten.
                collision = run / 'components-05-single-control.json'
                collision.write_text('protected')
                old_events, old_components = events.copy(), mod._components
                with self.assertRaises(FileExistsError):
                    node.load('single', 'control')
                self.assertEqual(events, old_events)
                self.assertIs(mod._components, old_components)
                self.assertEqual(collision.read_text(), 'protected')
                with patch.dict(os.environ, {'LTX_ENCODER_RUN_DIR': str(root/'speed-server')}):
                    with self.assertRaisesRegex(AssertionError, 'dedicated'):
                        node.load('single', 'control')

if __name__ == '__main__':
    before = json.loads((LANE/'data/encoder-integration-loaded-source-before.json').read_text())
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    after = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before}
    unchanged = before == after
    print(json.dumps({'passed': result.wasSuccessful() and unchanged, 'tests_run': result.testsRun,
                      'loaded_source_unchanged': unchanged, 'loaded_source_sha256': after,
                      'patch_sha256': {p: hashlib.sha256((LANE/'patches'/p).read_bytes()).hexdigest() for p in PATCHES},
                      'scope': 'In-memory CPU tiny Gemma4 + CLIP/LTX projection and mocked nonencoder loaders; no runtime/GPU validation'}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() and unchanged else 1)
