#!/usr/bin/env python3
"""Synthetic CPU integration and real-source free_memory control-flow tests."""
import ast
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_adapter as A
import native_safety as S

SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source')


class FakeTensor:
    def __init__(self, device, dtype='torch.bfloat16'):
        self.device, self.dtype, self.shape = device, dtype, (4,)
    def untyped_storage(self): return NS(data_ptr=lambda: id(self))
    def numel(self): return 4
    def element_size(self): return 2


class Patcher:
    def __init__(self, card, resident=False):
        self.load_device, self.resident = card, resident
        self.tensor = FakeTensor(card if resident else 'cpu')
        self.buffers = []
        self.model = NS(named_parameters=lambda: [('weight', self.tensor)],
                        named_buffers=lambda: self.buffers)
        self.additional = {}
    def is_dynamic(self): return False
    def is_clone(self, other): return self.model is other.model
    def model_size(self): return 8 + sum(t.numel() * t.element_size() for _, t in self.buffers)
    def loaded_size(self): return self.model_size() if self.resident else 0
    def get_additional_models_with_key(self, key): return self.additional[key]
    def verify_placement(self):
        A.require(str(self.tensor.device) == self.load_device, 'fake sampler misplaced')


class Fixture:
    def __init__(self, root):
        self.root, self.hashes, self.events = root, {}, []
        self.free = {c: 40 * S.GIB for c in S.CARDS}
        self.xpu = NS(synchronize=lambda c: self.events.append(('sync', str(c))),
                      mem_get_info=lambda c: (self.free[str(c)], 48 * S.GIB),
                      memory_allocated=lambda c: 100, memory_reserved=lambda c: 200,
                      max_memory_allocated=lambda c: 100)
        self.torch = self.module('torch', xpu=self.xpu)
        self.patchers = {r: Patcher(c, r.startswith('text_')) for r, c in S.ROLES.items()}
        self.primary = self.patchers['sampler_primary']
        self.primary.additional['ltx_layer_shard'] = [self.patchers['sampler_secondary']]
        self.primary.model.diffusion_model = NS(_ltx_layer_shard_identity={
            'split_index': 23, 'block_count': 48, 'primary': 'xpu:0', 'secondary': 'xpu:1'})
        self.patchers['text_primary'].additional['ltx_text_layer_shard'] = [self.patchers['text_secondary']]
        self.stack = NS(_ltx_text_shard_identity={
            'split_index': 24, 'layer_count': 48, 'primary': 'xpu:2', 'secondary': 'xpu:3'})
        self.clip = NS(patcher=self.patchers['text_primary'], _host_embedding=NS(
            owner=None, guard=lambda: None, inventory=lambda *a, **kw: {'mode': 'control'}))
        self.video = NS(patcher=self.patchers['video_vae'])
        self.audio = NS(patcher=self.patchers['audio_vae'])
        self.components = (self.primary, self.clip, self.video, self.audio, self.patchers['upsampler'])
        registry = [NS(model=p) for r, p in self.patchers.items() if r.startswith('text_')]
        self.mm = self.module('mm', DISABLE_SMART_MEMORY=False, MAX_PINNED_MEMORY=0, current_loaded_models=registry,
                              minimum_inference_memory=lambda: S.GIB, extra_reserved_memory=lambda: 2 * S.GIB)
        self.mm.loaded_models = lambda: [o.model for o in self.mm.current_loaded_models]
        def free_memory(amount, card, **kw):
            self.events.append(('free_memory', amount, str(card), kw))
            for owner in self.mm.current_loaded_models:
                A.require(any(owner is p for p in kw['keep_loaded']), 'existing owner unprotected')
            return []
        self.original_free = self.mm.free_memory = free_memory
        def load(patchers, force_full_load):
            self.events.append(('load', force_full_load))
            for card in S.CARDS: self.mm.free_memory(2 * S.GIB, card)
            for p in patchers:
                p.tensor.device, p.resident = p.load_device, True
                for _, t in p.buffers: t.device = p.load_device
                if not any(o.model is p for o in self.mm.current_loaded_models):
                    self.mm.current_loaded_models.append(NS(model=p))
        self.mm.load_models_gpu = load
        self.adapter = self.module('text_adapter', stack_of=lambda clip: (self.stack, []))
        self.shard = self.module('text_shard', verify_placement=lambda clip, stack: True)
        self.window = self.module('window', qualified=lambda: True, state=lambda: {'qualified': True})
        self.pipeline = self.module('pipeline', running=lambda: 0)
        self.host = self.namespace('host', _failure=None, _pending=[], _components=self.components,
                                   _shared=(self.primary, self.video, self.audio, self.patchers['upsampler']),
                                   _identity={'runtime': 'pinned'}, _generation=1, _mode='control',
                                   SAMPLER_PLACEMENT='two-way', torch=self.torch,
                                   comfy=NS(model_management=self.mm), shared_identity=lambda shared: [id(o) for o in shared])
        self.text = self.namespace('text', torch=self.torch, adapter=self.adapter, ltx_text_shard=self.shard,
                                  _failed=False, _installed=(self.clip, {}, NS(summary=lambda: {
                                      'layers_captured': list(range(48)), 'captured_graphs': 96})))
        self.capture = self.module('capture', _ROUTES=[], CAPTURES_FROZEN=[False], LOADS_FROZEN=[False])
        self.lean = self.module('lean', _MEMO_INSTALLED={}, _SENTRY_INSTALLED={})
        self.sampler = self.namespace('sampler', _installed=None, _failed=False, adapter=self.capture)
        self.samplerpipe = self.namespace('samplerpipe', _failed=False, SAMPLER_WORKERS=1, SAMPLER_BATCH=1, lean=self.lean)
        self.decode = self.namespace('decode', _REPLICAS={}, _REPLICA_SETS={'replica': {}}, _failed=False)
        self.textpipe = self.namespace('textpipe', window=self.window, pipeline=self.pipeline, _failed=False)
        def node(name, method, namespace):
            exec('def ' + method + '(self): pass', namespace)
            return type(name, (), {method: namespace[method]})
        self.nodes = NS(NODE_CLASS_MAPPINGS={
            'LTXHostEmbeddingComponents': node('Host', 'load', self.host),
            'LTXTextEncoderGraphGate': node('Text', '_apply', self.text),
            'LTXGraphCaptureGate': node('Sampler', '_apply', self.sampler),
            'LTXPipelineDecode': node('Decode', '_apply', self.decode),
            'LTXPipelineSampler': node('SamplerPipe', '_apply', self.samplerpipe),
            'LTXPipelineTextEncode': node('TextPipe', '_apply', self.textpipe)})
        for classname, cls in self.nodes.NODE_CLASS_MAPPINGS.items():
            method = 'load' if classname == 'LTXHostEmbeddingComponents' else '_apply'
            getattr(cls, method).__globals__.setdefault('NODE_CLASS_MAPPINGS', {})[classname] = cls
        self.session = NS(lock=threading.RLock(), active={'name': 'prepare-native'},
                          requests={'prepare-native': {'phase': 'native-setup'}},
                          phase='native_reference', healthy=lambda: None)
        def metadata(role, name):
            return {'phase': self.session.phase, 'qualification_id': 'qid',
                    'plan_sha256': 'a' * 64, 'runtime_manifest_sha256': 'b' * 64}
        def phase(*args):
            self.events.append(('phase', args))
            A.require(self.session.active is not None and self.session.active['name'] == args[2],
                      'wrong active graph request')
            return metadata(args[0], args[2])
        self.session.require_phase, self.session._metadata = phase, metadata

    def namespace(self, name, **attrs):
        p = self.root / (name + '.py')
        p.write_text('# synthetic pinned ' + name + '\n')
        self.hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return {'__file__': str(p), **attrs}

    def module(self, name, **attrs): return NS(**self.namespace(name, **attrs))

    def make(self):
        return A.NativeAdapter(torch=self.torch, nodes=self.nodes, model_management=self.mm,
                               session=self.session, qualification_id='qid', run_name='native-run',
                               plan_sha256='a' * 64, runtime_sha256='b' * 64,
                               source_hashes=self.hashes, fault_check=lambda: False)

    def prepare(self, adapter):
        result = adapter.prepare()
        self.session.active = None
        return result

    def begin(self, name='native-1'):
        self.session.active = {'name': name}


class AdapterControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = Fixture(Path(self.tmp.name))
    def tearDown(self): self.tmp.cleanup()

    def test_prepare_then_fresh_request_and_close(self):
        a = self.f.make()
        prepared = self.f.prepare(a)
        self.assertTrue(prepared['window_qualified'])
        self.assertEqual(sum(e[0] == 'load' for e in self.f.events), 1)
        self.assertIs(self.f.mm.free_memory, self.f.original_free)
        self.f.begin(); a.before_request('native-1')
        self.assertIsNot(self.f.mm.free_memory, self.f.original_free)
        self.f.mm.free_memory(S.GIB, 'xpu:0')
        a.after_request('native-1')
        self.f.session.active = None
        self.assertIs(self.f.mm.free_memory, self.f.original_free)
        a.close()
        with self.assertRaises(S.SafetyRefusal): a.prepare()

    def test_preload_insufficient_space_never_loads_or_retries(self):
        self.f.free['xpu:0'] = 6 * S.GIB
        a = self.f.make()
        with self.assertRaises(S.SafetyRefusal): a.prepare()
        self.assertFalse(any(e[0] == 'load' for e in self.f.events))
        self.f.free['xpu:0'] = 40 * S.GIB
        with self.assertRaises(S.SafetyRefusal): a.prepare()

    def test_registered_owner_module_used_not_alias(self):
        # Only registered globals change; a hypothetical imported alias would
        # still look healthy. Discovery must see the actual registered failure.
        self.f.host['_failure'] = {'error': 'real owner failed'}
        with self.assertRaises(S.SafetyRefusal): self.f.make().prepare()
        self.assertFalse(any(e[0] == 'load' for e in self.f.events))

    def test_source_drift_refused_before_any_device_call(self):
        Path(self.f.host['__file__']).write_text('# modified')
        with self.assertRaises(S.SafetyRefusal): self.f.make().prepare()
        self.assertFalse(any(e[0] in ('sync', 'load') for e in self.f.events))

    def test_actual_registered_sampler_and_replica_state_refuses(self):
        self.f.sampler['_installed'] = object()
        with self.assertRaises(S.SafetyRefusal): self.f.make().prepare()
        self.f.sampler['_installed'] = None
        self.f.decode['_REPLICA_SETS']['replica']['video'] = object()
        with self.assertRaisesRegex(S.SafetyRefusal, 'Decoder replica'): self.f.make().prepare()

    def test_orphan_route_and_lean_state_refuse_even_when_gate_uninstalled(self):
        self.f.capture._ROUTES.append(object())
        with self.assertRaises(S.SafetyRefusal): self.f.make().prepare()
        self.f.capture._ROUTES.clear()
        self.f.lean._MEMO_INSTALLED['model'] = object()
        with self.assertRaises(S.SafetyRefusal): self.f.make().prepare()

    def test_observation_only_between_requests_and_actual_name_binding(self):
        a = self.f.make(); self.f.prepare(a)
        snap = a.native_state()
        self.assertTrue(snap['observation_only'])
        self.f.begin('native-1')
        a.before_request('native-1'); a.after_request('native-1')
        names = [e[1][2] for e in self.f.events if e[0] == 'phase']
        self.assertIn('prepare-native', names)
        self.assertIn('native-1', names)
        self.assertNotIn('native-run', names)
        with self.assertRaises(S.SafetyRefusal): a.native_state()

    def test_float32_parameter_refused_integer_buffer_recorded(self):
        self.f.patchers['upsampler'].tensor.dtype = 'torch.float32'
        with self.assertRaises(S.SafetyRefusal): self.f.make().prepare()
        self.f.patchers['upsampler'].tensor.dtype = 'torch.bfloat16'
        self.f.patchers['upsampler'].buffers.append(('indices', FakeTensor('cpu', 'torch.int64')))
        a = self.f.make(); self.f.prepare(a)
        rows = a._rows('upsampler', require_loaded=True)
        self.assertTrue(rows[1]['integer_buffer_exception'])

    def test_post_load_text_mutation_refuses(self):
        load = self.f.mm.load_models_gpu
        def corrupt(*a, **kw):
            load(*a, **kw)
            self.f.patchers['text_secondary'].tensor.device = 'cpu'
        self.f.mm.load_models_gpu = corrupt
        with self.assertRaises(S.SafetyRefusal): self.f.make().prepare()
        self.assertIs(self.f.mm.free_memory, self.f.original_free)

    def test_same_globals_method_or_code_replacement_refuses(self):
        a = self.f.make(); self.f.prepare(a)
        cls = self.f.nodes.NODE_CLASS_MAPPINGS['LTXPipelineDecode']
        original = cls._apply
        exec('def replacement(self): return 123', self.f.decode)
        cls._apply = self.f.decode['replacement']
        with self.assertRaisesRegex(S.SafetyRefusal, 'Registered native node ownership'): a.native_state()
        cls._apply = original

    def test_load_exception_restores_and_latches(self):
        def fail(*a, **kw): raise RuntimeError('load failed')
        self.f.mm.load_models_gpu = fail
        a = self.f.make()
        with self.assertRaises(S.SafetyRefusal): a.prepare()
        self.assertIs(self.f.mm.free_memory, self.f.original_free)
        with self.assertRaises(S.SafetyRefusal): a.before_request('native-1')

    def test_request_pressure_refuses_before_original_and_abort_restores(self):
        a = self.f.make(); self.f.prepare(a); self.f.begin(); a.before_request('native-1')
        count = sum(e[0] == 'free_memory' for e in self.f.events)
        with self.assertRaises(S.SafetyRefusal): self.f.mm.free_memory(41 * S.GIB, 'xpu:0')
        self.assertEqual(sum(e[0] == 'free_memory' for e in self.f.events), count)
        with self.assertRaises(S.SafetyRefusal): a.abort_request('pressure refusal')
        self.assertIs(self.f.mm.free_memory, self.f.original_free)
        with self.assertRaises(S.SafetyRefusal): a.before_request('native-2')

    def test_changed_residence_or_post_floor_refuses_and_restores(self):
        a = self.f.make(); self.f.prepare(a); self.f.begin(); a.before_request('native-1')
        self.f.free['xpu:0'] = 2 * S.GIB - 1
        with self.assertRaises(S.SafetyRefusal): a.after_request('native-1')
        self.assertIs(self.f.mm.free_memory, self.f.original_free)
        with self.assertRaises(S.SafetyRefusal): a.native_state()

    def test_bindings_exist_in_actual_source_ast(self):
        for filename, classname, method in (
                ('host_embedding_resident_node.py', 'LTXHostEmbeddingComponents', 'load'),
                ('graph_text_encoder_node.py', 'LTXTextEncoderGraphGate', '_apply'),
                ('graph_capture_node.py', 'LTXGraphCaptureGate', '_apply'),
                ('pipeline_decode_node.py', 'LTXPipelineDecode', '_apply'),
                ('pipeline_sampler_node.py', 'LTXPipelineSampler', '_apply'),
                ('pipeline_node.py', 'LTXPipelineTextEncode', '_apply')):
            tree = ast.parse((SOURCE / 'scripts' / filename).read_bytes())
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == classname)
            self.assertTrue(any(isinstance(n, ast.FunctionDef) and n.name == method for n in cls.body))


class RealFreeMemoryControls(unittest.TestCase):
    def test_original_function_preserves_existing_keep_and_all_registry_owners(self):
        tree = ast.parse((SOURCE / 'comfy/model_management.py').read_bytes())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'free_memory')
        calls = []
        owner = NS(device='xpu:0', is_dead=lambda: False)
        caller_owner = object()
        env = dict(cleanup_models_gc=lambda: None, detail=lambda *a: None,
                   current_loaded_models=[owner], DISABLE_SMART_MEMORY=False,
                   vram_state='high', VRAMState=NS(HIGH_VRAM='high'),
                   ensure_pin_budget=lambda n: calls.append(('pins', n)),
                   ensure_pin_registerable=lambda n: calls.append(('register', n)))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<actual-free-memory>', 'exec'), env)
        original = env['free_memory']
        def recording(*args, **kwargs):
            calls.append(('original', args, kwargs))
            return original(*args, **kwargs)
        mm = NS(free_memory=recording, current_loaded_models=env['current_loaded_models'], DISABLE_SMART_MEMORY=False)
        xpu = NS(synchronize=lambda d: None, mem_get_info=lambda d: (100, 200))
        with A.protect_residence(mm, xpu):
            self.assertEqual(mm.free_memory(90, 'xpu:0', keep_loaded=[caller_owner], pins_required=7), [])
            event = next(e for e in calls if e[0] == 'original')
            self.assertIs(event[2]['keep_loaded'][0], caller_owner)
            self.assertIs(event[2]['keep_loaded'][1], owner)
            count = len(calls)
            with self.assertRaises(S.SafetyRefusal): mm.free_memory(101, 'xpu:0')
            self.assertEqual(len(calls), count)
        self.assertIs(mm.free_memory, recording)


if __name__ == '__main__': unittest.main()
