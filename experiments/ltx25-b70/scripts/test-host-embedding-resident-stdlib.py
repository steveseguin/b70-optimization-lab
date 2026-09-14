#!/usr/bin/env python3
"""Source-only component assembly tests. All runtime imports are isolated stubs."""
import ast
import contextlib
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
TARGET = HERE / 'host_embedding_resident_node.py'
PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-10/source/scripts/resident_node.py')
PARENT_SHA = '57b60dcba6be6b3127bd5c532603905cdcb1e541889ecb5f9b37ff2084ee1c25'

class Device:
    def __init__(self, name): self.name = name; self.type = name.split(':')[0]
    def __str__(self): return self.name

class Assembly:
    def __init__(self, root):
        self.root = Path(root)
        self.events = []
        self.failure = None
        self.identity = {'model_verification_sha256': '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f', 'server_identity_sha256': 'server-A'}
        self.clips = []
        self.receipts = []
    def event(self, name, *args):
        self.events.append((name, *args))
        if self.failure == name: raise RuntimeError('injected ' + name)
    def unet(self, filename, dtype):
        self.event('unet', filename, dtype)
        return (types.SimpleNamespace(load_device=Device('xpu:0')),)
    def clip(self, **kwargs):
        self.event('clip', kwargs)
        group = types.SimpleNamespace(mode=kwargs['mode'], retired=False)
        def guard():
            if group.retired: raise RuntimeError('retired')
        def retire(clip):
            guard(); self.event('retire', group.mode); group.retired = True
            return {'original_ownership_restored': True, 'all_shared_clones_retired': True}
        group.guard = guard
        group.detach_restore = retire
        group.inventory = lambda clip: {'mode': group.mode, 'metadata_only': True}
        clip = types.SimpleNamespace(_host_embedding=group,
            patcher=types.SimpleNamespace(loaded_size=lambda: 0, load_device=Device('xpu:2')),
            cond_stage_model=types.SimpleNamespace(parameters=lambda: [types.SimpleNamespace(device=Device('cpu'))]))
        self.clips.append(clip)
        return clip
    def weights(self, path, return_metadata):
        self.event('weights', path, return_metadata)
        return {'weight': path}, {'source': path}
    def vae(self, **kwargs):
        self.event('vae', kwargs)
        return types.SimpleNamespace(device=kwargs['device'], throw_exception_if_invalid=lambda: self.event('validate_vae'))
    def upscale(self, filename):
        self.event('upscale', filename); return (object(),)
    def shard(self, model, **kwargs):
        self.event('shard', kwargs)
        model.ltx_layer_shard_report = {'secondary_device': kwargs['secondary_device']}
        return model
    def exclusive(self, path, value, root):
        with path.open('x') as stream: json.dump(value, stream)
        self.receipts.append(path)
    @contextlib.contextmanager
    def loaded(self):
        names = ['torch', 'comfy', 'comfy.model_management', 'comfy.sd', 'comfy.utils',
                 'folder_paths', 'nodes', 'comfy_extras', 'comfy_extras.nodes_hunyuan',
                 'ltx_layer_shard', 'encoder_diagnostics', 'host_embedding_clip', 'host_embedding_placement_node']
        if any(name in sys.modules for name in names): raise RuntimeError('Refuse preexisting native/runtime modules')
        modules = {name: types.ModuleType(name) for name in names}
        modules['torch'].device = Device
        for name in ('comfy', 'comfy_extras'): modules[name].__path__ = []
        for leaf in ('model_management', 'sd', 'utils'): setattr(modules['comfy'], leaf, modules['comfy.' + leaf])
        modules['comfy.model_management'].unload_all_models = lambda: self.event('unload_all')
        modules['comfy.model_management'].cleanup_models_gc = lambda: self.event('cleanup')
        modules['comfy.sd'].VAE = self.vae
        modules['comfy.utils'].load_torch_file = self.weights
        modules['folder_paths'].get_full_path_or_raise = lambda kind, name: kind + '/' + name
        modules['folder_paths'].get_folder_paths = lambda kind: [kind]
        modules['nodes'].UNETLoader = lambda: types.SimpleNamespace(load_unet=self.unet)
        modules['comfy_extras.nodes_hunyuan'].LatentUpscaleModelLoader = types.SimpleNamespace(execute=self.upscale)
        modules['ltx_layer_shard'].apply_layer_shard = self.shard
        modules['encoder_diagnostics'].ROOT = self.root
        modules['encoder_diagnostics']._context = lambda root: (self.root, dict(self.identity))
        modules['encoder_diagnostics']._exclusive_json = self.exclusive
        modules['host_embedding_clip'].load_clip = self.clip
        modules['host_embedding_clip'].MODES = ('control', 'host-table')
        def require(ok, message):
            if not ok: raise RuntimeError(message)
        modules['host_embedding_clip'].require = require
        modules['host_embedding_placement_node'].NODE_CLASS_MAPPINGS = {'placement-stub': object()}
        sys.modules.update(modules)
        try:
            module = types.ModuleType('resident_assembly_under_test')
            exec(compile(TARGET.read_bytes(), str(TARGET), 'exec'), module.__dict__)
            yield module, module.LTXHostEmbeddingComponents()
        finally:
            for name, value in modules.items():
                if sys.modules.get(name) is not value: raise RuntimeError('Stub module unexpectedly replaced: ' + name)
                del sys.modules[name]

class Tests(unittest.TestCase):
    def test_same_mode_reuses_five_components(self):
        with tempfile.TemporaryDirectory() as root:
            a = Assembly(root)
            with a.loaded() as (m, node):
                first = node.load('split', 'control'); before = list(a.events)
                self.assertIs(first, node.load('split', 'control'))
                self.assertEqual(a.events, before)
                self.assertEqual(len(first), 5)
                self.assertEqual(m._generation, 1)
                self.assertEqual(node.RETURN_TYPES, ('MODEL','CLIP','VAE','VAE','LATENT_UPSCALE_MODEL'))
                self.assertEqual(node.RETURN_NAMES, ('model','clip','video_vae','audio_vae','upscaler'))
                self.assertEqual(len(a.receipts), 2)
                options = next(row[1]['model_options'] for row in a.events if row[0] == 'clip')
                self.assertEqual({k: str(v) for k,v in options.items()}, {'load_device':'xpu:2','offload_device':'cpu'})
                self.assertEqual([row[1:] for row in a.events if row[0] == 'unet'],
                    [('ltx-2.5-22b-distilled-transformer-bf16.safetensors','default')])
                self.assertEqual([row[1] for row in a.events if row[0] == 'weights'],
                    ['vae/ltx-2.5-video-vae-bf16.safetensors','vae/ltx-2.5-audio-vae-bf16.safetensors'])
                self.assertEqual([str(row[1]['device']) for row in a.events if row[0] == 'vae'], ['xpu:3','xpu:3'])
                self.assertEqual([row[1] for row in a.events if row[0] == 'upscale'],
                    ['ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors'])
                self.assertEqual([row[1] for row in a.events if row[0] == 'shard'], [{'secondary_device':'xpu:1'}])
    def test_control_host_control_retires_before_unload(self):
        with tempfile.TemporaryDirectory() as root:
            a = Assembly(root)
            with a.loaded() as (m, node):
                outputs = [node.load('split', mode) for mode in ('control','host-table','control')]
                self.assertEqual(m._generation, 3)
                self.assertTrue(a.clips[0]._host_embedding.retired and a.clips[1]._host_embedding.retired)
                self.assertFalse(a.clips[2]._host_embedding.retired)
                lifecycle = [row[0] for row in a.events if row[0] in ('retire','unload_all','cleanup')]
                self.assertEqual(lifecycle, ['retire','unload_all','cleanup'] * 2)
                for generation, mode in enumerate(('control','host-table','control'), 1):
                    record = json.loads((Path(root) / f'host-components-{generation:02d}-{mode}-result.json').read_text())
                    self.assertEqual(record['generation'], generation)
                    self.assertEqual(record['status'], 'completed')
                    self.assertFalse(record['generated_output_cache'] or record['prompt_encoding_cache'])
                self.assertEqual(len(a.receipts), 8)
    def test_existing_started_receipt_refuses_before_work(self):
        with tempfile.TemporaryDirectory() as root:
            a = Assembly(root)
            path = Path(root) / 'host-components-01-control-started.json'; path.write_text('preserved')
            with a.loaded() as (m, node):
                with self.assertRaises(FileExistsError): node.load('split','control')
                self.assertEqual(a.events, [])
                self.assertEqual(path.read_text(), 'preserved')
    def test_existing_result_receipt_refuses_before_work(self):
        with tempfile.TemporaryDirectory() as root:
            a = Assembly(root)
            path = Path(root) / 'host-components-01-control-result.json'; path.write_text('preserved')
            with a.loaded() as (m, node):
                with self.assertRaises(RuntimeError): node.load('split','control')
                self.assertEqual(a.events, [])
                self.assertEqual(path.read_text(), 'preserved')
    def test_identity_change_refuses_reuse_or_transition(self):
        with tempfile.TemporaryDirectory() as root:
            a = Assembly(root)
            with a.loaded() as (m, node):
                node.load('split','control'); before=list(a.events)
                a.identity['server_identity_sha256'] = 'server-B'
                for mode in ('control','host-table'):
                    with self.assertRaises(RuntimeError): node.load('split',mode)
                self.assertEqual(a.events,before)
    def test_failure_is_sticky_and_retains_partial_owners(self):
        with tempfile.TemporaryDirectory() as root:
            a = Assembly(root); a.failure='vae'
            with a.loaded() as (m, node):
                with self.assertRaisesRegex(RuntimeError,'injected vae'): node.load('split','host-table')
                self.assertEqual(len(m._pending),2)
                self.assertEqual(m._generation,0)
                self.assertEqual(m._failure['phase'],'load-VAEs')
                record=json.loads((Path(root)/'host-components-01-host-table-result.json').read_text())
                self.assertEqual(record['status'],'failed'); self.assertEqual(record['retained_partial_owners'],2)
                before=list(a.events); a.failure=None
                for mode in ('host-table','control'):
                    with self.assertRaisesRegex(RuntimeError,'transition failed'): node.load('split',mode)
                self.assertEqual(a.events,before)
                self.assertNotIn('unload_all',[row[0] for row in a.events])
    def test_failed_retirement_does_not_unload_or_retry(self):
        with tempfile.TemporaryDirectory() as root:
            a=Assembly(root)
            with a.loaded() as (m,node):
                first=node.load('split','control'); a.failure='retire'
                with self.assertRaisesRegex(RuntimeError,'injected retire'): node.load('split','host-table')
                self.assertIs(m._components,first)
                self.assertNotIn('unload_all',[row[0] for row in a.events])
                before=list(a.events)
                with self.assertRaisesRegex(RuntimeError,'transition failed'): node.load('split','control')
                self.assertEqual(a.events,before)
    def test_original_numerical_loading_calls_unchanged(self):
        self.assertEqual(hashlib.sha256(PARENT.read_bytes()).hexdigest(),PARENT_SHA)
        names=('nodes.UNETLoader().load_unet','comfy.utils.load_torch_file','comfy.sd.VAE',
               'LatentUpscaleModelLoader.execute','apply_layer_shard')
        def calls(path):
            rows={name:[] for name in names}
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,ast.Call) and ast.unparse(node.func) in rows:
                    rows[ast.unparse(node.func)].append(ast.dump(node))
            return rows
        baseline=calls(PARENT); current=calls(TARGET)
        self.assertEqual(baseline,current)
        self.assertTrue(all(len(rows)==1 for rows in current.values()))
    def test_stubs_are_removed(self):
        with tempfile.TemporaryDirectory() as root:
            with Assembly(root).loaded(): self.assertIn('torch',sys.modules)
        self.assertNotIn('torch',sys.modules)
        self.assertNotIn('comfy',sys.modules)

if __name__ == '__main__':
    unittest.main()
