"""Explicit reference-only bridge to the identity-checked live Comfy objects.

Import is CPU-only. prepare()/request methods intentionally use injected live
device APIs and must only be called by the coordinator's preflighted runtime.
"""
from contextlib import contextmanager
import hashlib
import inspect
import json
import math
from pathlib import Path
import time

from native_safety import NativeReferenceSafety, SafetyRefusal, ROLES, CARDS, PRE_BYTES, GIB, digest


def require(condition, reason):
    if not condition:
        raise SafetyRefusal(reason)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


@contextmanager
def protect_residence(mm, xpu):
    """Keep existing LoadedModel owners; refuse pressure before any eviction.

    Scoped around one preload or one native request. It preserves the caller's
    requested memory/keep_loaded list and adds no explicit cache-flush call;
    original Comfy allocator bookkeeping remains unchanged.
    """
    require(mm.DISABLE_SMART_MEMORY is False, 'No-eviction reference requires smart-memory checks')
    original = mm.free_memory

    def guarded(memory_required, device, keep_loaded=(), for_dynamic=False,
                pins_required=0, ram_required=0):
        require(not for_dynamic, 'Dynamic model eviction is outside native reference')
        card = str(device)
        require(card in CARDS, 'Unexpected/global free_memory target')
        require(type(memory_required) in (int, float) and math.isfinite(memory_required)
                and memory_required >= 0, 'Invalid native load memory request')
        xpu.synchronize(device)
        free, _ = xpu.mem_get_info(device)
        require(type(free) is int and free >= memory_required,
                'Native load would need eviction; refused before free_memory')
        protected = list(mm.current_loaded_models)
        keep = list(keep_loaded)
        for owner in protected:
            if not any(owner is item for item in keep):
                keep.append(owner)
        result = original(memory_required, device, keep_loaded=keep,
                          for_dynamic=for_dynamic, pins_required=pins_required,
                          ram_required=ram_required)
        require(not result, 'Native free_memory unexpectedly evicted a model')
        require(all(any(p is q for q in mm.current_loaded_models) for p in protected),
                'Native load changed protected loaded-model registry')
        return result

    mm.free_memory = guarded
    try:
        yield
    finally:
        require(mm.free_memory is guarded, 'Native memory guard ownership changed')
        mm.free_memory = original


# These are constructor-owned state, not a general FP32 weight allowance.
# Paths/hashes are from the immutable upstream-99b source inherited by 101.
FP32_SOURCES = {
    'sd1_clip.py': '4b7f08bea2028e73c8f68dc9a26f5cc2981ddf27f12c303a467bd8aa9939dcfa',
    'text_encoders/gemma4.py': '6fc1b06e42e33bed5e69c208808551af839265ad319f4eb9a0aa40ecc62d179a',
    'model_sampling.py': '8afdc665272589a567792bb652389df7d4a83f69574c2b7e5b3d533d55592990',
}
FP32_STATE = {
    ('text_primary', 'parameter', 'gemma3_12b.logit_scale'):
        ((), 'sd1_clip.py', 'SDClipModel constructor scalar'),
    ('text_primary', 'buffer', 'gemma3_12b.transformer.model._global_inv_freq'):
        ((256,), 'text_encoders/gemma4.py', 'Gemma4 12B global FP32 RoPE frequencies'),
    ('text_primary', 'buffer', 'gemma3_12b.transformer.model._sliding_inv_freq'):
        ((128,), 'text_encoders/gemma4.py', 'Gemma4 12B sliding FP32 RoPE frequencies'),
    ('sampler_primary', 'buffer', 'model_sampling.sigmas'):
        ((10000,), 'model_sampling.py', 'LTXAV ModelSamplingFlux scheduler table'),
}


SAMPLER_SEGMENTS = (('xpu:0', 0, 20), ('xpu:1', 20, 48))


def require_sampler_layout(model, placement):
    """Inspect the qualified100b named two-segment representation, without moves."""
    require(placement == 'two-way20-28', 'Native reference requires named20/28')
    shards = model.get_additional_models_with_key('ltx_layer_shard')
    require(isinstance(shards, (list, tuple)) and len(shards) == 1,
            'Named20/28 requires exactly one secondary owner')
    secondary = shards[0]
    require(model is not secondary and model.model is not secondary.model and
            str(model.load_device) == 'xpu:0' and str(secondary.load_device) == 'xpu:1',
            'Named20/28 owners are aliased or misplaced')
    diffusion = model.model.diffusion_model
    identity = diffusion._ltx_layer_shard_identity
    segments = identity.get('segments')
    require(isinstance(segments, list) and len(segments) == 2 and
            all(isinstance(s, list) and len(s) == 3 and type(s[1]) is int and type(s[2]) is int
                for s in segments), 'Named20/28 segment structure differs')
    require('split_index' in identity and identity['split_index'] is None and
            segments == [list(s) for s in SAMPLER_SEGMENTS] and
            type(identity.get('block_count')) is int and identity['block_count'] == 48 and
            identity.get('primary') == 'xpu:0' and identity.get('devices') == ['xpu:0', 'xpu:1'] and
            'secondary' not in identity,
            'Actual native sampler placement is not exact named20/28')
    blocks = tuple(diffusion.transformer_blocks)
    primary_blocks, secondary_blocks = tuple(diffusion._ltx_primary_blocks), tuple(secondary.model.blocks)
    require(len(blocks) == len({id(b) for b in blocks}) == 48 and
            len(primary_blocks) == 20 and len(secondary_blocks) == 28 and
            all(a is b for a, b in zip(primary_blocks, blocks[:20])) and
            all(a is b for a, b in zip(secondary_blocks, blocks[20:])),
            'Named20/28 actual block ownership differs')
    routes = model.model_options.get('transformer_options', {}).get('patches_replace', {}).get('dit', {})
    require(set(routes) == {('double_block', i) for i in range(48)},
            'Named20/28 native route coverage differs')
    for i in range(48):
        route = routes[('double_block', i)]
        require(str(route.device) == ('xpu:0' if i < 20 else 'xpu:1') and
                str(route.primary) == 'xpu:0' and type(route.last) is bool and route.last == (i == 47),
                'Named20/28 native block route differs')
    return secondary


class NativeAdapter:
    def __init__(self, *, torch, nodes, model_management, session, qualification_id,
                 run_name, plan_sha256, runtime_sha256, source_hashes, fault_check):
        self.torch, self.nodes, self.mm = torch, nodes, model_management
        self.session, self.qualification_id, self.run_name = session, qualification_id, run_name
        self.authority = getattr(session, '_authority', session)
        self.current_name = None
        self.plan_sha256, self.runtime_sha256 = digest(plan_sha256), digest(runtime_sha256)
        require(callable(fault_check), 'Explicit fault observer required')
        self.fault_check = fault_check
        self.source_hashes = {str(Path(p).resolve()): digest(h) for p, h in source_hashes.items()}
        require(self.source_hashes, 'Runtime source inventory required')
        self.started = False
        self.ready = False
        self.failed = None
        self.controller = None
        self.guard = None
        self.receipts = []
        self.bound_sources = {}
        self.node_bindings = []

    def _fail(self, exc):
        if self.failed is None:
            self.failed = str(exc)
            self.receipts.append({'event': 'adapter-failure', 'reason': self.failed,
                                  'plan_sha256': self.plan_sha256,
                                  'runtime_sha256': self.runtime_sha256})
        raise SafetyRefusal(self.failed)

    def _phase(self):
        require(self.failed is None, 'Native adapter is latched: ' + str(self.failed))
        require(self.controller is None or self.controller.failed is None,
                'Native reference controller has a latched failure')
        require(self.current_name is not None, 'No actual native request name is bound')
        auth = self.session.require_phase('native', self.qualification_id, self.current_name)
        self._check_authority_metadata(auth)
        require(self.fault_check() is False, 'Native fault observer refused execution')

    def _check_authority_metadata(self, auth):
        require(isinstance(auth, dict) and auth.get('phase') == 'native_reference' and
                auth.get('qualification_id') == self.qualification_id and
                auth.get('plan_sha256') == self.plan_sha256 and
                auth.get('runtime_manifest_sha256') == self.runtime_sha256,
                'Native authority identity differs')

    def _observation_phase(self):
        require(self.failed is None and self.controller is not None and self.controller.failed is None,
                'Native observation after failure/unprepared state')
        require(self.current_name is None and self.guard is None,
                'Between-request observation attempted during native execution')
        with self.authority.lock:
            self.authority.healthy()
            require(self.authority.active is None, 'Native observation requires no active request')
            self._check_authority_metadata(self.authority._metadata('observation', None))
        require(self.fault_check() is False, 'Fault during native observation')

    def _pin(self, namespace):
        path = str(Path(namespace['__file__']).resolve())
        expected = self.source_hashes.get(path)
        require(expected is not None, 'Loaded module absent from runtime inventory: ' + path)
        actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        require(actual == expected, 'Loaded source changed: ' + path)
        self.bound_sources[path] = actual

    def _globals(self, node_name, method):
        cls = self.nodes.NODE_CLASS_MAPPINGS[node_name]
        function = getattr(cls, method)
        unwrapped = inspect.unwrap(function)
        ns = unwrapped.__globals__
        self._pin(ns)
        require(ns.get('NODE_CLASS_MAPPINGS', {}).get(node_name) is cls,
                'Registered node does not own its defining globals: ' + node_name)
        self.node_bindings.append((node_name, method, cls, ns, function, unwrapped, unwrapped.__code__))
        return ns

    def _discover(self):
        self.host = self._globals('LTXHostEmbeddingComponents', 'load')
        self.text = self._globals('LTXTextEncoderGraphGate', '_apply')
        self.sampler = self._globals('LTXGraphCaptureGate', '_apply')
        self.decode = self._globals('LTXPipelineDecode', '_apply')
        self.text_pipeline = self._globals('LTXPipelineTextEncode', '_apply')
        self.sampler_pipeline = self._globals('LTXPipelineSampler', '_apply')
        # The actual method name is source-bound; no alternate imported node
        # module is permitted to stand in for the registry's live globals.
        self.window = self.text_pipeline['window']
        self.pipeline = self.text_pipeline['pipeline']
        self.text_adapter = self.text['adapter']
        self.text_shard = self.text['ltx_text_shard']
        self.capture = self.sampler['adapter']
        self.lean = self.sampler_pipeline['lean']
        for module in (self.window, self.pipeline, self.text_adapter, self.text_shard,
                       self.capture, self.lean, self.mm, self.torch):
            self._pin(vars(module))
        require(self.host['torch'] is self.torch and self.text['torch'] is self.torch,
                'Runtime Torch module differs from registered node owner')
        require(self.host['comfy'].model_management is self.mm,
                'Runtime model manager differs from registered node owner')
        require(self.host['_failure'] is None and not self.host['_pending']
                and self.host['_components'] is not None, 'Host loader is incomplete/failed')
        self.components = self.host['_components']
        model, self.clip, video, audio, upscaler = self.components
        secondary = require_sampler_layout(model, self.host['SAMPLER_PLACEMENT'])
        text_secondary, = self.clip.patcher.get_additional_models_with_key('ltx_text_layer_shard')
        self.objects = dict(zip(ROLES, (model, secondary, upscaler, self.clip.patcher,
                                       text_secondary, video, audio)))
        self.patchers = {r: o.patcher if r.endswith('_vae') else o for r, o in self.objects.items()}
        self.host_identity = fingerprint(self.host['_identity'])
        self.shared_identity = fingerprint(self.host['shared_identity'](self.host['_shared']))
        self.generation = self.host['_generation']
        self.mode = self.host['_mode']
        require(self.generation > 0 and self.mode == 'control', 'Unexpected accepted host-loader mode')
        require(self.clip._host_embedding.owner is None, 'Unexpected separate CPU embedding owner')
        self.stack, _ = self.text_adapter.stack_of(self.clip)
        text_identity = self.stack._ltx_text_shard_identity
        require(all(text_identity.get(k) == v for k, v in {
            'split_index': 24, 'layer_count': 48, 'primary': 'xpu:2', 'secondary': 'xpu:3'}.items()),
            'Actual accepted text placement is not24/24')

    def _state(self, observation=False):
        if observation:
            self._observation_phase()
        else:
            self._phase()
        for name, method, cls, ns, function, unwrapped, code in self.node_bindings:
            require(self.nodes.NODE_CLASS_MAPPINGS.get(name) is cls and
                    getattr(cls, method) is function and inspect.unwrap(function) is unwrapped and
                    unwrapped.__code__ is code and unwrapped.__globals__ is ns and
                    ns.get('NODE_CLASS_MAPPINGS', {}).get(name) is cls,
                    'Registered native node ownership changed: ' + name)
        require(require_sampler_layout(self.components[0], self.host['SAMPLER_PLACEMENT']) is
                self.objects['sampler_secondary'], 'Native secondary owner changed')
        require(self.host['_components'] is self.components and self.host['_failure'] is None
                and not self.host['_pending'] and self.host['_generation'] == self.generation
                and self.host['_mode'] == self.mode, 'Host component ownership changed')
        require(fingerprint(self.host['_identity']) == self.host_identity and
                fingerprint(self.host['shared_identity'](self.host['_shared'])) == self.shared_identity,
                'Host/model identity changed')
        require(self.sampler['_installed'] is None and not self.sampler['_failed'],
                'Sampler graph routes/failure exist before native reference')
        require(not self.capture._ROUTES and not self.capture.CAPTURES_FROZEN[0]
                and not self.capture.LOADS_FROZEN[0], 'Actual sampler graph/freeze state is not native')
        require(not self.lean._MEMO_INSTALLED and not self.lean._SENTRY_INSTALLED,
                'Lean conditioning installed before native reference')
        require(not self.sampler_pipeline['_failed'] and self.sampler_pipeline['SAMPLER_WORKERS'] == 2
                and self.sampler_pipeline['SAMPLER_BATCH'] == 1, 'Native successor is not healthy W2 B1')
        require(not self.decode['_REPLICAS'] and
                all(not v for v in self.decode['_REPLICA_SETS'].values()) and not self.decode['_failed'],
                'Decoder replica exists before native reference')
        require(not self.text['_failed'] and not self.text_pipeline['_failed'], 'Encoder path failed')
        installed = self.text['_installed']
        require(installed is not None and installed[0] is self.clip, 'Accepted text graph owner missing')
        summary = installed[2].summary()
        require(summary['layers_captured'] == list(range(48)) and summary['captured_graphs'] >= 48,
                'Text layer capture coverage incomplete')
        require(self.window.qualified(), 'Text window is not qualified')
        self.clip._host_embedding.guard()
        self.clip._host_embedding.inventory(self.clip, require_loaded=True)
        self.text_shard.verify_placement(self.clip, self.stack)
        # Preserve truthful running/pending values for the coordinator's
        # quiescence checks; do not pretend the currently executing node is idle.
        return {'text_capture': summary, 'window': self.window.state(),
                'pipeline_running': self.pipeline.running()}

    def _dtype_exception(self, role, kind, name, tensor):
        spec = FP32_STATE.get((role, kind, name))
        if spec is None:
            return None
        shape, relative, rationale = spec
        require(str(tensor.dtype) == 'torch.float32' and tuple(tensor.shape) == shape
                and tensor.numel() == math.prod(shape) and tensor.element_size() == 4,
                'Constructor-owned FP32 state changed: ' + role + '/' + name)
        # Check both the packet inventory and the reviewed immutable constructor.
        path = (Path(self.mm.__file__).resolve().parent / relative).resolve()
        expected = FP32_SOURCES[relative]
        require(self.source_hashes.get(str(path)) == expected,
                'FP32 constructor absent/different in runtime inventory: ' + str(path))
        self._pin({'__file__': str(path)})
        return {'source_path': str(path), 'source_sha256': expected,
                'rationale': rationale}

    def _rows(self, role, *, require_loaded):
        patcher = self.patchers[role]
        require(str(patcher.load_device) == ROLES[role] and not patcher.is_dynamic(),
                'Reference patcher target/dynamic mode changed: ' + role)
        rows = []
        for kind, values in (('parameter', patcher.model.named_parameters()),
                             ('buffer', patcher.model.named_buffers())):
            for name, tensor in values:
                dtype = str(tensor.dtype)
                integral = dtype in {'torch.bool', 'torch.uint8', 'torch.int8', 'torch.int16',
                                     'torch.int32', 'torch.int64'}
                exception = self._dtype_exception(role, kind, name, tensor)
                require(dtype == 'torch.bfloat16' or (kind == 'buffer' and integral) or exception is not None,
                        'Unexpected reference tensor dtype: ' + role + '/' + name + '/' + dtype)
                device = str(tensor.device)
                require(device == ROLES[role] if require_loaded else device in ('cpu', ROLES[role]),
                        'Reference tensor is offloaded/misplaced: ' + role + '/' + name)
                rows.append({'kind': kind, 'name': name, 'id': id(tensor),
                             'storage': tensor.untyped_storage().data_ptr(),
                             'shape': list(tensor.shape), 'dtype': dtype, 'device': device,
                             'bytes': tensor.numel() * tensor.element_size(),
                             'integer_buffer_exception': integral, 'fp32_constructor_exception': exception})
        require(rows, 'Empty reference tensor inventory: ' + role)
        if require_loaded:
            require(any(patcher is p for p in self.mm.loaded_models()), 'Reference owner absent from loaded registry')
            require(patcher.loaded_size() == patcher.model_size() and patcher.loaded_size() > 0,
                    'Reference model is not fully loaded: ' + role)
        return rows

    def _free(self):
        for card in CARDS:
            self.torch.xpu.synchronize(card)
        result = {c: self.torch.xpu.mem_get_info(c)[0] for c in CARDS}
        require(all(type(v) is int and v >= 0 for v in result.values()), 'Invalid physical free-memory readings')
        return result

    def prepare(self):
        require(not self.started, 'Native preparation is one-shot')
        self.started = True
        try:
            with self.authority.lock:
                require(self.authority.active is not None, 'Native prepare requires its admitted setup request')
                self.current_name = self.authority.active['name']
                require(self.authority.requests[self.current_name]['phase'] == 'native-setup',
                        'Full residency may only be prepared by registered native setup')
            self._phase()
            self._discover()
            require(self.mm.MAX_PINNED_MEMORY <= 0, 'Reference requires existing disabled pinned-memory policy')
            state_before = self._state()
            text_before = {r: fingerprint(self._rows(r, require_loaded=True))
                           for r in ('text_primary', 'text_secondary')}
            missing = {c: 0 for c in CARDS}
            for role in ROLES:
                for row in self._rows(role, require_loaded=False):
                    if row['device'] != ROLES[role]:
                        missing[ROLES[role]] += row['bytes']
            extra = max(self.mm.minimum_inference_memory(), self.mm.extra_reserved_memory())
            require(type(extra) in (int, float) and math.isfinite(extra) and extra >= 0,
                    'Invalid loader inference reserve')
            required = {c: math.ceil(1.1 * missing[c]) + max(PRE_BYTES[c], math.ceil(extra)) for c in CARDS}
            free = self._free()
            self.receipts.append({'event': 'preload-admission', 'free': free, 'missing_tensor_bytes': missing,
                                  'required': required, 'state': state_before})
            require(all(free[c] >= required[c] for c in CARDS), 'Insufficient space before native full residency')
            # Registry clones would be detached by load_models_gpu outside its
            # free_memory helper. Refuse them before the one load call.
            for patcher in self.patchers.values():
                require(not any(p is not patcher and patcher.is_clone(p) for p in self.mm.loaded_models()),
                        'Clone owner would be detached during native preparation')
            with protect_residence(self.mm, self.torch.xpu):
                self.mm.load_models_gpu(list(self.patchers.values()), force_full_load=True)
            self._state()
            require(all(fingerprint(self._rows(r, require_loaded=True)) == h for r, h in text_before.items()),
                    'Preload changed accepted encoder ownership')
            self.objects['sampler_primary'].verify_placement()
            expected = {r: fingerprint(self._rows(r, require_loaded=True)) for r in ROLES}
            self.controller = NativeReferenceSafety(
                plan_sha256=self.plan_sha256, runtime_sha256=self.runtime_sha256,
                objects=self.objects, expected_residence=expected,
                synchronize=self.torch.xpu.synchronize, inspect=self._inspect, require_phase=self._phase)
            self.ready = True
            snapshot = self._inspect(self.objects)
            require(all(snapshot['physical_free_bytes'][c] >= PRE_BYTES[c] for c in CARDS),
                    'Post-preload native headroom refused')
            self.receipts.append({'event': 'prepared', 'snapshot': snapshot,
                                  'sources': dict(self.bound_sources)})
            return snapshot
        except BaseException as exc:
            self._fail(exc)
        finally:
            self.current_name = None

    def _inspect(self, objects, observation=False):
        require(all(objects[r] is self.objects[r] for r in ROLES), 'Reference objects changed')
        state = self._state(observation)
        self.objects['sampler_primary'].verify_placement()
        checked_rows = {r: self._rows(r, require_loaded=True) for r in ROLES}
        constructor_state = [
            {'role': role, **{key: row[key] for key in ('kind', 'name', 'dtype', 'shape', 'device', 'bytes')},
             **row['fp32_constructor_exception']}
            for role, rows in checked_rows.items() for row in rows
            if row['fp32_constructor_exception'] is not None]
        residence = {r: {'object_id': id(o), 'device': ROLES[r], 'dtype': 'torch.bfloat16',
                         'fully_resident': True,
                         'ownership_sha256': fingerprint(checked_rows[r])}
                     for r, o in self.objects.items()}
        if self.controller is not None:
            require(all(row['ownership_sha256'] == self.controller.expected_residence[r]
                        for r, row in residence.items()), 'Admitted native tensor ownership changed')
        return {'plan_sha256': self.plan_sha256, 'runtime_sha256': self.runtime_sha256,
                'phase': 'native-reference', 'fault': False,
                'text_graphs_captured': True, 'window_qualified': True,
                'sampler_routes': 0, 'decoder_replicas': 0, 'residence': residence,
                'residence_dtype_semantics': 'checkpoint weights; constructor exceptions listed separately',
                'constructor_fp32_state': constructor_state,
                'physical_free_bytes': self._free(),
                'peaks': {c: {'allocated': self.torch.xpu.memory_allocated(c),
                              'reserved': self.torch.xpu.memory_reserved(c),
                              'peak': self.torch.xpu.max_memory_allocated(c)} for c in CARDS},
                'observed_state': state, 'timestamp_ns': time.time_ns()}

    def native_state(self):
        require(self.ready, 'Native preparation has not completed')
        try:
            result = self._inspect(self.objects, observation=True)
            result['observation_only'] = True
            return result
        except BaseException as exc:
            self._fail(exc)

    def before_request(self, name):
        try:
            require(self.ready and self.guard is None, 'Native adapter unavailable or overlapping request')
            self.current_name = name
            self._phase()
            self.guard = protect_residence(self.mm, self.torch.xpu)
            self.guard.__enter__()
            return self.controller.before(name)
        except BaseException as exc:
            self._restore_guard()
            self.current_name = None
            self._fail(exc)

    def _restore_guard(self):
        if self.guard is not None:
            guard, self.guard = self.guard, None
            guard.__exit__(None, None, None)

    def after_request(self, name):
        try:
            require(self.controller is not None and self.controller.active == name and self.current_name == name,
                    'Native post-request identity mismatch')
            return self.controller.after()
        except BaseException as exc:
            self._fail(exc)
        finally:
            self._restore_guard()
            self.current_name = None

    def abort_request(self, exc):
        try:
            if self.controller is not None:
                self.controller._fail('Executor rejected native request: ' + str(exc))
        finally:
            self._restore_guard()
            self.current_name = None
            self._fail(exc)

    def close(self):
        try:
            require(self.guard is None and self.controller is not None, 'Cannot close active/unprepared native adapter')
            self.controller.close()
            self.ready = False
        except BaseException as exc:
            self._fail(exc)
