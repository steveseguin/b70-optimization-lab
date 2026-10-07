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
    def __init__(self, device, dtype='torch.bfloat16', shape=(4,)):
        self.device, self.dtype, self.shape = device, dtype, shape
    def untyped_storage(self): return NS(data_ptr=lambda: id(self))
    def numel(self): return A.math.prod(self.shape)
    def element_size(self): return 4 if self.dtype == 'torch.float32' else 2


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
        self.samplerpipe = self.namespace('samplerpipe', _failed=False, SAMPLER_WORKERS=2, SAMPLER_BATCH=1, lean=self.lean)
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

    def test_w1_or_w3_source_configuration_refuses_before_any_preload(self):
        for workers in (1,3):
            with self.subTest(workers=workers):
                self.f.samplerpipe['SAMPLER_WORKERS']=workers
                a=self.f.make()
                with self.assertRaisesRegex(S.SafetyRefusal,'healthy W2 B1'):a.prepare()
                self.assertFalse(any(e[0]=='load' for e in self.f.events))
                self.assertIsNotNone(a.failed)

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


class ConstructorDtypeControls(unittest.TestCase):
    def adapter(self, role, kind, name, tensor):
        a = object.__new__(A.NativeAdapter)
        p = Patcher(S.ROLES[role], resident=True)
        p.model.named_parameters = lambda: [(name, tensor)] if kind == 'parameter' else [('weight', p.tensor)]
        p.model.named_buffers = lambda: [(name, tensor)] if kind == 'buffer' else []
        a.patchers = {role: p}
        a.mm = NS(__file__=str(SOURCE / 'comfy/model_management.py'), loaded_models=lambda: [p])
        a.source_hashes = {str((SOURCE / 'comfy' / name).resolve()): sha
                           for name, sha in A.FP32_SOURCES.items()}
        a.bound_sources = {}
        return a

    def test_exact_constructor_state_admitted_without_cast_or_cpu_exemption(self):
        for (role, kind, name), (shape, source, _) in A.FP32_STATE.items():
            with self.subTest(name=name):
                t = FakeTensor(S.ROLES[role], 'torch.float32', shape)
                a = self.adapter(role, kind, name, t)
                row = next(r for r in a._rows(role, require_loaded=True) if r['name'] == name)
                self.assertEqual(row['id'], id(t))
                self.assertEqual(row['dtype'], 'torch.float32')
                self.assertEqual(row['bytes'], A.math.prod(shape) * 4)
                self.assertEqual(row['fp32_constructor_exception']['source_sha256'], A.FP32_SOURCES[source])
                # FakeTensor has no casting/moving API; acceptance cannot cast.
                t.device = 'cpu'
                with self.assertRaisesRegex(S.SafetyRefusal, 'offloaded/misplaced'):
                    a._rows(role, require_loaded=True)
                a._rows(role, require_loaded=False)

    def test_inspection_reports_actual_fp32_inventory(self):
        a = self.adapter('text_primary', 'parameter', 'gemma3_12b.logit_scale',
                         FakeTensor('xpu:2', 'torch.float32', ()))
        for role in S.ROLES:
            if role not in a.patchers: a.patchers[role] = Patcher(S.ROLES[role], resident=True)
        for (role, kind, name), (shape, _, _) in A.FP32_STATE.items():
            if kind == 'buffer':
                a.patchers[role].buffers.append((name, FakeTensor(S.ROLES[role], 'torch.float32', shape)))
        a.patchers['text_primary'].model.named_buffers = lambda: a.patchers['text_primary'].buffers
        a.objects = a.patchers
        a.mm.loaded_models = lambda: list(a.patchers.values())
        a._state = lambda observation=False: {'synthetic': True}
        a._free = lambda: {c: 40 * S.GIB for c in S.CARDS}
        a.torch = NS(xpu=NS(memory_allocated=lambda c: 0, memory_reserved=lambda c: 0,
                            max_memory_allocated=lambda c: 0))
        a.controller = None
        a.plan_sha256, a.runtime_sha256 = 'a' * 64, 'b' * 64
        snap = a._inspect(a.objects)
        self.assertEqual(len(snap['constructor_fp32_state']), 4)
        self.assertEqual(sum(row['bytes'] for row in snap['constructor_fp32_state']), 41540)
        self.assertIn('checkpoint weights', snap['residence_dtype_semantics'])
        for row in snap['constructor_fp32_state']:
            self.assertEqual(row['dtype'], 'torch.float32')
            self.assertEqual(row['device'], S.ROLES[row['role']])
            self.assertEqual(hashlib.sha256(Path(row['source_path']).read_bytes()).hexdigest(), row['source_sha256'])
        self.assertTrue(all(row['dtype'] == 'torch.bfloat16' for row in snap['residence'].values()))

    def test_changed_kind_role_name_shape_precision_and_width_refused(self):
        for key, (shape, _, _) in A.FP32_STATE.items():
            role, kind, name = key
            for change in ('role', 'kind', 'name', 'shape', 'dtype', 'width'):
                with self.subTest(name=name, change=change):
                    rr = 'video_vae' if change == 'role' else role
                    kk = ('buffer' if kind == 'parameter' else 'parameter') if change == 'kind' else kind
                    nn = name + '.unexpected' if change == 'name' else name
                    t = FakeTensor(S.ROLES[rr], 'torch.float64' if change == 'dtype' else 'torch.float32',
                                   (2,) if change == 'shape' else shape)
                    if change == 'width': t.element_size = lambda: 8
                    a = self.adapter(rr, kk, nn, t)
                    with self.assertRaises(S.SafetyRefusal): a._rows(rr, require_loaded=True)

    def test_missing_modified_or_changed_source_identity_refused(self):
        key = ('text_primary', 'parameter', 'gemma3_12b.logit_scale')
        t = FakeTensor('xpu:2', 'torch.float32', ())
        a = self.adapter(*key, t)
        a.source_hashes.clear()
        with self.assertRaisesRegex(S.SafetyRefusal, 'constructor absent/different'):
            a._rows(key[0], require_loaded=True)
        with tempfile.TemporaryDirectory() as tmp:
            a = self.adapter(*key, t)
            a.mm.__file__ = str(Path(tmp) / 'model_management.py')
            source = Path(tmp) / 'sd1_clip.py'
            source.write_text('# changed constructor')
            a.source_hashes[str(source)] = A.FP32_SOURCES['sd1_clip.py']
            with self.assertRaisesRegex(S.SafetyRefusal, 'Loaded source changed'):
                a._rows(key[0], require_loaded=True)

    def test_bf16_checkpoint_rule_and_precision_preservation(self):
        for role in S.ROLES:
            for kind in ('parameter', 'buffer'):
                t = FakeTensor(S.ROLES[role])
                a = self.adapter(role, kind, 'checkpoint.weight', t)
                a._rows(role, require_loaded=True)
                t.dtype = 'torch.float32'
                with self.assertRaisesRegex(S.SafetyRefusal, 'Unexpected reference tensor dtype'):
                    a._rows(role, require_loaded=True)
        # An unintended downcast of a known FP32 constructor is refused too.
        t = FakeTensor('xpu:2', shape=())
        a = self.adapter('text_primary', 'parameter', 'gemma3_12b.logit_scale', t)
        with self.assertRaisesRegex(S.SafetyRefusal, 'Constructor-owned FP32 state changed'):
            a._rows('text_primary', require_loaded=True)

    def test_pinned_constructor_and_loader_source_rationale(self):
        sources = {}
        for name, sha in A.FP32_SOURCES.items():
            raw = (SOURCE / 'comfy' / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), sha)
            sources[name] = ast.parse(raw)
        def cls(tree, name): return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
        clip = ast.unparse(cls(sources['sd1_clip.py'], 'SDClipModel'))
        self.assertIn('self.logit_scale = torch.nn.Parameter(torch.tensor(4.6055))', clip)
        gemma = cls(sources['text_encoders/gemma4.py'], 'Gemma4Config')
        defaults = {n.targets[0].id: ast.literal_eval(n.value) for n in gemma.body
                    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                    and n.targets[0].id in ('head_dim', 'global_head_dim')}
        self.assertEqual(defaults, {'head_dim': 256, 'global_head_dim': 512})
        g12 = ast.unparse(cls(sources['text_encoders/gemma4.py'], 'Gemma4_12B_Config'))
        self.assertNotIn('head_dim =', g12)
        transformer = ast.unparse(cls(sources['text_encoders/gemma4.py'], 'Gemma4Transformer'))
        self.assertIn("self.register_buffer('_global_inv_freq', global_inv, persistent=False)", transformer)
        self.assertIn("self.register_buffer('_sliding_inv_freq', sliding_inv, persistent=False)", transformer)
        self.assertIn('torch.arange(0, config.head_dim, 2).float()', transformer)
        flux = cls(sources['model_sampling.py'], 'ModelSamplingFlux')
        method = next(n for n in flux.body if isinstance(n, ast.FunctionDef) and n.name == 'set_parameters')
        self.assertEqual(ast.literal_eval(method.args.defaults[-1]), 10000)
        self.assertIn("self.register_buffer('sigmas', ts)", ast.unparse(method))
        base = ast.parse((SOURCE / 'comfy/model_base.py').read_bytes())
        ltx_init = next(n for n in cls(base, 'LTXAV').body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
        self.assertEqual(ast.unparse(ltx_init.args.defaults[0]), 'ModelType.FLUX')
        shard = (SOURCE / 'scripts/ltx_text_shard.py').read_text()
        self.assertIn('t.device != p.load_device', shard)
        loader = (SOURCE / 'comfy/model_patcher.py').read_text()
        self.assertIn('self.model.to(device_to)', loader)


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
