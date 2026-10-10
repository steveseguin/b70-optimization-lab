"""Packet112 candidate safety contract for per-block graph replay. CPU-importable.

The sealed native contract (native_safety / native_adapter) requires zero
sampler routes; graph execution is never relabelled as native. This module
subclasses both and changes exactly one thing: instead of "no routes" it
accepts only the pinned 48-route LTXGraphCaptureGate inventory (all48,
chain 1) bound to the prompt-executor thread and the launched placement's owners
(two-way 23/25 by default, or the named two-way20-28),
with at most eight signatures per route and, after the qualification freeze,
exactly the frozen signature set. Residency, ownership, 8/8/2/9 GiB pre-floors,
2 GiB post-floors, VAE OOM refusal and failure latches are inherited unchanged.
"""
import copy
import hashlib
import inspect
import math
from pathlib import Path
import time

import native_adapter
from native_adapter import NativeAdapter, fingerprint, protect_residence, require
from native_safety import (CARDS, GIB, PRE_BYTES, ROLES, NativeReferenceSafety, SafetyRefusal)

PLACEMENTS = {'two-way': 23, 'two-way20-28': 20}
BLOCKS = 48
MAX_SIGNATURES = 8


def route_devices(placement):
    require(placement in PLACEMENTS, 'Unknown sampler placement: %r' % (placement,))
    return {i: ('xpu:0' if i < PLACEMENTS[placement] else 'xpu:1') for i in range(BLOCKS)}


ROUTE_DEVICES = route_devices('two-way')
CANDIDATE_PHASES = ('stream_setup', 'stream_qualification', 'stream')
SAMPLER_WORKERS = 1


# -- pure route-inventory contract (unit tested on CPU) ------------------------
def check_route_inventory(snapshot, expected):
    """Return a verdict dict; raise SafetyRefusal on any deviation.

    expected = {'state': 'absent'|'installing'|'pinned', 'owner_thread': int|None,
                'frozen': bool, 'frozen_signatures': {index: digest}|None, 'placement': str}
    """
    state = expected['state']
    devices = route_devices(expected.get('placement', 'two-way'))
    require(state in ('absent', 'installing', 'pinned'), 'Unknown expected route state')
    if state == 'installing':
        try:
            return check_route_inventory(snapshot, dict(expected, state='absent'))
        except SafetyRefusal:
            return check_route_inventory(snapshot, dict(expected, state='pinned'))
    require(type(snapshot) is dict and snapshot.get('gate_failed') is False,
            'Graph-capture gate latched a failure')
    require(snapshot.get('captures_frozen') is bool(expected['frozen']),
            'Capture freeze differs from the expected phase')
    registry = snapshot.get('registry')
    require(type(registry) is list and len(registry) == BLOCKS and
            [r.get('index') for r in registry] == list(range(BLOCKS)), 'Route registry must cover 48 blocks')
    if state == 'absent':
        require(snapshot.get('installed') is False and snapshot.get('route_objects') == 0 and
                snapshot.get('groups') == [] and snapshot.get('pool_owners') == [],
                'Graph routes, groups or pools exist before the graph chain')
        for row in registry:
            require(row.get('type') == '_BlockRoute' and row.get('device') == devices[row['index']]
                    and row.get('primary') == 'xpu:0' and row.get('last') is (row['index'] == BLOCKS - 1),
                    'Native route %d differs' % row['index'])
        return {'passed': True, 'state': 'absent', 'routes': 0}
    owner = expected['owner_thread']
    require(type(owner) is int, 'Pinned routes need a bound owner thread')
    record = snapshot.get('install_record')
    require(snapshot.get('installed') is True and type(record) is dict and
            record == {'model_is_primary': True, 'originals': list(range(BLOCKS)),
                       'selection': 'all48', 'chain': 1}, 'Installed graph selection differs from all48/chain1')
    require(snapshot.get('route_objects') == BLOCKS and snapshot.get('route_list_is_registry') is True,
            'Graph route inventory is not exactly the 48 registered routes')
    counts = set()
    signatures = {}
    for row in registry:
        i = row['index']
        require(row.get('type') == 'GraphBlockRoute' and row.get('head_index') == i and
                row.get('native_block') is True and row.get('original_is_pinned') is True and
                row.get('device') == devices[i] and row.get('primary') == 'xpu:0' and
                row.get('last') is (i == BLOCKS - 1), 'Graph route %d differs from its pinned owner' % i)
        threads = row.get('threads')
        require(type(threads) is dict and set(threads) <= {str(owner)},
                'Route %d holds graphs for a thread other than the prompt executor' % i)
        n = threads.get(str(owner), 0)
        require(type(n) is int and 0 <= n <= MAX_SIGNATURES, 'Route %d exceeds eight signatures' % i)
        counts.add(n)
        signatures[i] = row.get('signature_digest')
    require(len(counts) == 1, 'Signature coverage differs between routes')
    allowed = {(d, owner) for d in ('xpu:0', 'xpu:1')}
    for key in ('groups', 'pool_owners'):
        rows = snapshot.get(key)
        require(type(rows) is list and all(type(r) is list and len(r) == 2 for r in rows) and
                {tuple(r) for r in rows} <= allowed, 'Foreign %s for graph replay' % key)
    if expected['frozen']:
        require(expected['frozen_signatures'] is not None and
                signatures == expected['frozen_signatures'], 'Signature set changed after the freeze')
    return {'passed': True, 'state': 'pinned', 'routes': BLOCKS, 'signatures_per_route': counts.pop(),
            'owner_thread': owner}


def _signature_digest(keys):
    return hashlib.sha256('\n'.join(sorted(repr(k) for k in keys)).encode()).hexdigest()


def snapshot_routes(capture, gate, primary_model, signature_digest=None):
    """Read live objects into the plain snapshot `check_route_inventory` consumes."""
    signature_digest = signature_digest or _signature_digest
    options = primary_model.model_options.get('transformer_options', {})
    routes = options.get('patches_replace', {}).get('dit', {})
    blocks = tuple(primary_model.model.diffusion_model.transformer_blocks)
    installed = gate['_installed']
    originals = installed[1] if installed is not None else {}
    registry = []
    heads = []
    for i in range(BLOCKS):
        route = routes.get(('double_block', i))
        kind = type(route).__name__
        row = {'index': i, 'type': kind}
        if kind == 'GraphBlockRoute':
            heads.append(route)
            original = route.original_route
            row.update(head_index=route.index, native_block=(len(route.blocks) == 1 and route.blocks[0] is blocks[i]),
                       original_is_pinned=original is originals.get(i),
                       threads={str(t): len(e) for t, e in route.entries.items()},
                       signature_digest=signature_digest(
                           [k for e in route.entries.values() for k in e]))
        else:
            original = route
        row.update(device=str(getattr(original, 'device', None)), primary=str(getattr(original, 'primary', None)),
                   last=getattr(original, 'last', None))
        registry.append(row)
    record = None
    if installed is not None:
        record = {'model_is_primary': installed[0] is primary_model, 'originals': sorted(originals),
                  'selection': installed[3][0], 'chain': installed[3][1]}
    groups = []
    if heads:
        groups = sorted([str(d), t] for d, t in heads[0].registry.groups)
    with capture._POOL_LOCK:
        pool_owners = sorted([str(d), t] for d, t in capture._POOL_OWNERS)
    return {'installed': installed is not None, 'install_record': record, 'gate_failed': bool(gate['_failed']),
            'route_objects': len(capture._ROUTES),
            'route_list_is_registry': len(capture._ROUTES) == len(heads) and
                                      all(a is b for a, b in zip(capture._ROUTES, heads)),
            'registry': registry, 'groups': groups, 'pool_owners': pool_owners,
            'captures_frozen': bool(capture.CAPTURES_FROZEN[0]),
            'captured_graphs': sum(r['threads'].get(t, 0) for r in registry if 'threads' in r for t in r['threads'])}


def candidate_layout(model, placement):
    """The launched placement, read without moves; graph routes delegate to the original routes."""
    devices = route_devices(placement)
    split = PLACEMENTS[placement]
    shards = model.get_additional_models_with_key('ltx_layer_shard')
    require(isinstance(shards, (list, tuple)) and len(shards) == 1, placement + ' requires one secondary owner')
    secondary = shards[0]
    require(model is not secondary and model.model is not secondary.model and
            str(model.load_device) == 'xpu:0' and str(secondary.load_device) == 'xpu:1',
            placement + ' owners are aliased or misplaced')
    diffusion = model.model.diffusion_model
    identity = diffusion._ltx_layer_shard_identity
    if placement == 'two-way':
        ok = (identity.get('split_index') == split and identity.get('segments') is None and
              identity.get('secondary') == 'xpu:1')
    else:
        ok = ('split_index' in identity and identity['split_index'] is None and 'secondary' not in identity and
              identity.get('segments') == [['xpu:0', 0, split], ['xpu:1', split, BLOCKS]] and
              identity.get('devices') == ['xpu:0', 'xpu:1'])
    require(ok and identity.get('block_count') == BLOCKS and identity.get('primary') == 'xpu:0',
            'Actual sampler placement is not ' + placement)
    blocks = tuple(diffusion.transformer_blocks)
    primary_blocks, secondary_blocks = tuple(diffusion._ltx_primary_blocks), tuple(secondary.model.blocks)
    require(len(blocks) == len({id(b) for b in blocks}) == BLOCKS and
            len(primary_blocks) == split and len(secondary_blocks) == BLOCKS - split and
            all(a is b for a, b in zip(primary_blocks, blocks[:split])) and
            all(a is b for a, b in zip(secondary_blocks, blocks[split:])),
            placement + ' block ownership differs')
    routes = model.model_options.get('transformer_options', {}).get('patches_replace', {}).get('dit', {})
    require(set(routes) == {('double_block', i) for i in range(BLOCKS)}, 'Route coverage differs')
    for i in range(BLOCKS):
        route = routes[('double_block', i)]
        base = route.original_route if type(route).__name__ == 'GraphBlockRoute' else route
        require(type(base).__name__ == '_BlockRoute' and str(base.device) == devices[i] and
                str(base.primary) == 'xpu:0' and base.last is (i == BLOCKS - 1),
                '%s block route %d differs' % (placement, i))
    return secondary


# -- safety controller -------------------------------------------------------
class CandidateSafety(NativeReferenceSafety):
    """NativeReferenceSafety with the candidate route contract in place of zero routes."""

    def _snapshot(self, event, required):
        self.require_phase()
        for card in CARDS:
            self.synchronize(card)
        snap = self.inspect(dict(self.objects))
        if not isinstance(snap, dict):
            self._fail('Missing candidate safety snapshot')
        receipt = {'event': event, 'request_id': self.active,
                   'required_physical_free_bytes': dict(required),
                   'snapshot': copy.deepcopy(snap), 'admitted': False,
                   'allowances_are_not_peak_bounds': True}
        self.receipts.append(receipt)
        if (snap.get('plan_sha256') != self.plan_sha256 or snap.get('runtime_sha256') != self.runtime_sha256 or
                snap.get('phase') != 'candidate-stream'):
            self._fail('Candidate plan/runtime/phase identity changed')
        inventory = snap.get('route_inventory')
        if (snap.get('fault') is not False or snap.get('text_graphs_captured') is not True or
                snap.get('window_qualified') is not True or
                type(snap.get('decoder_replicas')) is not int or snap['decoder_replicas'] != 0 or
                type(inventory) is not dict or inventory.get('passed') is not True or
                snap.get('sampler_routes') != inventory.get('routes')):
            self._fail('Fault or route inventory outside the candidate contract')
        residence = snap.get('residence')
        if not isinstance(residence, dict) or set(residence) != set(ROLES):
            self._fail('Missing or unexpected resident objects')
        for role, device in ROLES.items():
            row = residence[role]
            if not isinstance(row, dict) or row != {
                    'object_id': id(self.objects[role]), 'device': device, 'dtype': 'torch.bfloat16',
                    'fully_resident': True, 'ownership_sha256': self.expected_residence[role]}:
                self._fail('Residence/ownership changed: ' + role)
        for role in ('video_vae', 'audio_vae'):
            if getattr(self.objects[role], '_ltx_native_reference_safety', None) is not self:
                self._fail('VAE safety binding was removed or replaced')
        free, peaks = snap.get('physical_free_bytes'), snap.get('peaks')
        if not isinstance(free, dict) or set(free) != set(CARDS):
            self._fail('Incomplete physical free-memory readings')
        if not isinstance(peaks, dict) or set(peaks) != set(CARDS):
            self._fail('Incomplete allocation/peak readings')
        for card in CARDS:
            if not self._bytes(free[card]) or free[card] < required[card]:
                self._fail('Physical free-memory admission refused: %s has %s, needs %s'
                           % (card, free[card], required[card]))
            row = peaks[card]
            if (not isinstance(row, dict) or set(row) != {'allocated', 'reserved', 'peak'} or
                    not all(self._bytes(v) for v in row.values()) or
                    row['reserved'] < row['allocated'] or row['peak'] < row['allocated']):
                self._fail('Invalid allocation/peak readings: ' + card)
        receipt['admitted'] = True
        return receipt

    def drain(self):
        """Hand this request's receipts to the runtime; keeps process memory bounded."""
        rows, self.receipts = self.receipts, []
        return rows


class CandidateAdapter(NativeAdapter):
    """NativeAdapter bound to the candidate route contract, the launched placement and W1 B1."""

    def __init__(self, *, expected_routes, **kwargs):
        require(callable(expected_routes), 'Expected route state callback required')
        self.expected_routes = expected_routes
        self.last_inventory = None
        super().__init__(**kwargs)

    def _check_authority_metadata(self, auth):
        require(isinstance(auth, dict) and auth.get('phase') in CANDIDATE_PHASES and
                auth.get('qualification_id') == self.qualification_id and
                auth.get('plan_sha256') == self.plan_sha256 and
                auth.get('runtime_manifest_sha256') == self.runtime_sha256,
                'Candidate authority identity differs')

    def _phase(self):
        require(self.failed is None, 'Candidate adapter is latched: ' + str(self.failed))
        require(self.controller is None or self.controller.failed is None,
                'Candidate controller has a latched failure')
        require(self.current_name is not None, 'No actual request name is bound')
        auth = self.session.require_phase('candidate', self.qualification_id, self.current_name)
        self._check_authority_metadata(auth)
        require(self.fault_check() is False, 'Fault observer refused execution')

    def _discover(self):
        self.host = self._globals('LTXHostEmbeddingComponents', 'load')
        self.text = self._globals('LTXTextEncoderGraphGate', '_apply')
        self.sampler = self._globals('LTXGraphCaptureGate', '_apply')
        self.decode = self._globals('LTXPipelineDecode', '_apply')
        self.text_pipeline = self._globals('LTXPipelineTextEncode', '_apply')
        self.sampler_pipeline = self._globals('LTXPipelineSampler', '_apply')
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
        require(self.host['SAMPLER_PLACEMENT'] == self.expected_routes().get('placement'),
                'Loaded sampler placement differs from the launch parameter')
        secondary = candidate_layout(model, self.host['SAMPLER_PLACEMENT'])
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

    def enable_signature_digest_cache(self, enabled):
        from signature_cache127 import SignatureDigestCache
        require(type(enabled) is int and enabled in (0, 1), 'Invalid signature cache choice')
        require(not hasattr(self, '_signature_digest_cache'), 'Signature cache already configured')
        self._signature_digest_cache = SignatureDigestCache() if enabled else None

    def signature_cache_summary(self):
        cache = getattr(self, '_signature_digest_cache', None)
        return {'enabled': cache is not None, 'stats': None if cache is None else cache.summary()}

    def route_inventory(self):
        cache = getattr(self, '_signature_digest_cache', None)
        digest_keys = None if cache is None else lambda keys: cache.digest(keys, _signature_digest)
        snapshot = snapshot_routes(self.capture, self.sampler, self.components[0], digest_keys)
        verdict = check_route_inventory(snapshot, self.expected_routes())
        self.last_inventory = {'verdict': verdict, 'captured_graphs': snapshot['captured_graphs'],
                               'signature_digests': {r['index']: r.get('signature_digest')
                                                     for r in snapshot['registry']}}
        return verdict

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
                    'Registered node ownership changed: ' + name)
        require(candidate_layout(self.components[0], self.host['SAMPLER_PLACEMENT']) is
                self.objects['sampler_secondary'], 'Secondary owner changed')
        require(self.host['_components'] is self.components and self.host['_failure'] is None
                and not self.host['_pending'] and self.host['_generation'] == self.generation
                and self.host['_mode'] == self.mode, 'Host component ownership changed')
        require(fingerprint(self.host['_identity']) == self.host_identity and
                fingerprint(self.host['shared_identity'](self.host['_shared'])) == self.shared_identity,
                'Host/model identity changed')
        inventory = self.route_inventory()
        require(not self.capture.LOADS_FROZEN[0], 'Load freeze is outside the candidate contract')
        require(not self.lean._MEMO_INSTALLED and not self.lean._SENTRY_INSTALLED,
                'Lean conditioning is outside the candidate contract')
        require(not self.sampler_pipeline['_failed'] and self.sampler_pipeline['SAMPLER_WORKERS'] == SAMPLER_WORKERS
                and self.sampler_pipeline['SAMPLER_BATCH'] == 1, 'Candidate requires healthy W1 B1')
        require(not self.decode['_REPLICAS'] and
                all(not v for v in self.decode['_REPLICA_SETS'].values()) and not self.decode['_failed'],
                'Decoder replica is outside the candidate contract')
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
        return {'text_capture_layers': len(summary['layers_captured']),
                'text_captured_graphs': summary['captured_graphs'],
                'window': self.window.state(), 'pipeline_running': self.pipeline.running(),
                'route_inventory': inventory}

    def prepare(self):
        require(not self.started, 'Candidate preparation is one-shot')
        self.started = True
        try:
            with self.authority.lock:
                require(self.authority.active is not None, 'Prepare requires its admitted setup request')
                self.current_name = self.authority.active['name']
                require(self.authority.requests[self.current_name]['phase'] == 'native-setup',
                        'Full residency may only be prepared by registered setup')
            self._phase()
            self._discover()
            require(self.mm.MAX_PINNED_MEMORY <= 0, 'Requires the existing disabled pinned-memory policy')
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
            require(all(free[c] >= required[c] for c in CARDS), 'Insufficient space before full residency')
            for patcher in self.patchers.values():
                require(not any(p is not patcher and patcher.is_clone(p) for p in self.mm.loaded_models()),
                        'Clone owner would be detached during preparation')
            with protect_residence(self.mm, self.torch.xpu):
                self.mm.load_models_gpu(list(self.patchers.values()), force_full_load=True)
            self._state()
            require(all(fingerprint(self._rows(r, require_loaded=True)) == h for r, h in text_before.items()),
                    'Preload changed accepted encoder ownership')
            self.objects['sampler_primary'].verify_placement()
            expected = {r: fingerprint(self._rows(r, require_loaded=True)) for r in ROLES}
            self.controller = CandidateSafety(
                plan_sha256=self.plan_sha256, runtime_sha256=self.runtime_sha256,
                objects=self.objects, expected_residence=expected,
                synchronize=self.torch.xpu.synchronize, inspect=self._inspect, require_phase=self._phase)
            self.ready = True
            snapshot = self._inspect(self.objects)
            require(all(snapshot['physical_free_bytes'][c] >= PRE_BYTES[c] for c in CARDS),
                    'Post-preload headroom refused')
            self.receipts.append({'event': 'prepared', 'snapshot': snapshot, 'sources': dict(self.bound_sources)})
            return snapshot
        except BaseException as exc:
            self._fail(exc)
        finally:
            self.current_name = None

    def _inspect(self, objects, observation=False):
        require(all(objects[r] is self.objects[r] for r in ROLES), 'Objects changed')
        state = self._state(observation)
        self.objects['sampler_primary'].verify_placement()
        checked_rows = {r: self._rows(r, require_loaded=True) for r in ROLES}
        residence = {r: {'object_id': id(o), 'device': ROLES[r], 'dtype': 'torch.bfloat16',
                         'fully_resident': True, 'ownership_sha256': fingerprint(checked_rows[r])}
                     for r, o in self.objects.items()}
        if self.controller is not None:
            require(all(row['ownership_sha256'] == self.controller.expected_residence[r]
                        for r, row in residence.items()), 'Admitted tensor ownership changed')
        inventory = state['route_inventory']
        return {'plan_sha256': self.plan_sha256, 'runtime_sha256': self.runtime_sha256,
                'phase': 'candidate-stream', 'fault': False,
                'text_graphs_captured': True, 'window_qualified': True,
                'sampler_routes': inventory['routes'], 'route_inventory': inventory,
                'decoder_replicas': 0, 'residence': residence,
                'physical_free_bytes': self._free(),
                'peaks': {c: {'allocated': self.torch.xpu.memory_allocated(c),
                              'reserved': self.torch.xpu.memory_reserved(c),
                              'peak': self.torch.xpu.max_memory_allocated(c)} for c in CARDS},
                'observed_state': state, 'timestamp_ns': time.time_ns()}

    def drain_receipts(self):
        rows, self.receipts = self.receipts, []
        return rows
