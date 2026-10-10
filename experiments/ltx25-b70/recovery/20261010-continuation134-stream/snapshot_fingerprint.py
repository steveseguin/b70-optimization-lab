"""Packet119: the four-card safety snapshot with residence fingerprints (LTX_SNAPSHOT_MODE=walk|fingerprint).

Stdlib only; Torch and the live objects come in through the runtime's adapter. Nothing here touches a device
except through the adapter's own calls (`_state`, `_free`, the allocator counters), exactly as the walk does.

What the walk costs. Every four-card snapshot (`CandidateSafety._snapshot`, sealed, unchanged) calls the
adapter's `_inspect`, which (1) re-runs the phase/identity/route/text checks (`_state`), (2) walks every tensor of
the two sampler owners again (`verify_placement`), (3) builds one dict per parameter and buffer of all seven roles
(about 6,800 rows) and serialises them to canonical JSON for a SHA-256 per role (the residence/ownership
fingerprint the controller compares with the admitted one), and (4) synchronises the four cards and reads the
memory counters. On the CPU of this host (3) and (2) are about 60 % of the Python time of a snapshot.

What the fingerprint mode changes, and why it is the same check. A row of the walk is a pure function of
(kind, name, id(tensor), untyped_storage().data_ptr(), shape, dtype, device) plus static facts (the integer-buffer
flag follows from the dtype; the FP32 constructor exception follows from (role, kind, name) and is re-checked,
with its source pin, on every snapshot). At the placement event (right after the full-residency preparation, when
the controller's admitted fingerprints are computed) `ResidenceLedger.capture()` walks once more, requires the
SHA-256 of the walk's rows to equal the admitted fingerprint, and binds that SHA-256 to the tuple of those facts
(checked row by row against the walk's rows). A later snapshot re-enumerates the same tensors the same way
(`named_parameters()`, `named_buffers()`, same order, same de-duplication) and re-reads the same facts; if the
tuple is equal, the walk's rows would be equal byte for byte, so its SHA-256 is the bound one; if anything
differs, the fingerprint mode does not decide: it runs the walk itself (`_rows` + fingerprint) and returns the
walk's result, so the controller refuses exactly as in walk mode. The sampler placement check uses the same
fact tuples (every tensor of both sampler owners on its load device, the shard registration, no patches), and
falls back to the sealed `verify_placement()` on any deviation. Phase, identity, routes, text, VAE binding,
encoder cache, fault flags, the four synchronisations and every memory floor are the unchanged code.

What a pure event fingerprint cannot see, and therefore what is NOT fingerprinted (partial fingerprinting): a
tensor's storage pointer, shape, dtype and device can change without any Python-visible placement event (the
C-level `Tensor.data` setter, `set_`, `resize_`, `torch.utils.swap_tensors`, a direct `_parameters` /
`_buffers` write). So every snapshot still reads those facts of every tensor (the walk's reads); what is dropped
is only the per-row dict building, the JSON serialisation and hashing, and the second sampler walk. Nothing that
the walk checks is checked less often.

Runtime proof (`SnapshotInspector`): during setup and qualification every snapshot runs both modes (the walk is
the snapshot the controller admits) and compares them verdict for verdict; during streaming the walk runs beside
the fingerprint on every DUAL_EVERY-th chunk and on every chunk that reports a memory reading within
NEAR_FLOOR_BYTES of a pre-request floor (from that snapshot on). A disagreement writes LATCH_NAME in the results
root (the launcher then refuses LTX_SNAPSHOT_MODE=fingerprint) and raises, which latches the server.
The decode thread's xpu:3 snapshot (precompute_guard.Xpu3Snapshot, P7) uses the same ledger and policy.
"""
import threading
import time

SCHEMA = 'ltx.stream118.snapshot-fingerprint.v1'
LATCH_NAME = 'snapshot-118-refused.json'
MODES = ('walk', 'fingerprint')
DUAL_EVERY = 20                    # streaming: the walk runs beside the fingerprint on every 20th chunk ...
NEAR_FLOOR_BYTES = 2 ** 29         # ... and once a snapshot reads a card within 0.5 GiB of its pre-request floor
SHARD_KEY = 'ltx_layer_shard'      # ltx_layer_shard.KEY (sealed)
VERDICT_KEYS = ('plan_sha256', 'runtime_sha256', 'phase', 'fault', 'text_graphs_captured', 'window_qualified',
                'sampler_routes', 'route_inventory', 'decoder_replicas', 'residence')


class SnapshotDisagreement(RuntimeError):
    """The fingerprint and the walk reached different verdicts (latched; never retried)."""


class LedgerRefusal(RuntimeError):
    pass


def require(ok, why):
    if not ok:
        raise LedgerRefusal(why)


def enumerate_facts(patcher):
    """The walk's enumeration of one role (NativeAdapter._rows order) without building rows: per tensor
    (kind, name, id, storage data_ptr, shape, dtype, device); and the tensors, aligned."""
    facts, tensors = [], []
    for kind, values in (('parameter', patcher.model.named_parameters()), ('buffer', patcher.model.named_buffers())):
        for name, tensor in values:
            facts.append((kind, name, id(tensor), tensor.untyped_storage().data_ptr(), tuple(tensor.shape),
                          tensor.dtype, tensor.device))
            tensors.append(tensor)
    return tuple(facts), tensors


def fact_matches_row(fact, row):
    """One fact tuple against one row of the walk (the binding proof of capture())."""
    kind, name, ident, storage, shape, dtype, device = fact
    return (row['kind'] == kind and row['name'] == name and row['id'] == ident and row['storage'] == storage and
            row['shape'] == list(shape) and row['dtype'] == str(dtype) and row['device'] == str(device))


class ResidenceLedger:
    """Residence/ownership of the seven roles from fact tuples bound to the admitted fingerprints."""

    def __init__(self, *, adapter, roles, fingerprint, require_fn=None):
        self.adapter, self.roles, self.fingerprint = adapter, dict(roles), fingerprint
        self.require = require_fn or require          # native_adapter.require in the server (same messages)
        self.expected = None                          # role -> fact tuple bound to the admitted SHA-256
        self.bound = {}                               # role -> admitted SHA-256
        self.exceptions = {}                          # role -> [(index, kind, name, exception dict)]
        self.load_devices = {}                        # role -> patcher.load_device at capture
        self.lock = threading.Lock()
        self.stats = {'fingerprint': 0, 'fallback_walks': 0, 'placement_fallbacks': 0, 'dual_walks': 0,
                      'agreements': 0, 'disagreements': 0, 'xpu3_fingerprint': 0, 'xpu3_dual': 0}

    def bump(self, key, n=1):
        with self.lock:
            self.stats[key] += n

    # -- the placement event ------------------------------------------------------------------------
    def capture(self, controller):
        """Bind each role's fact tuple to its admitted fingerprint (one walk; refuses on any difference)."""
        a = self.adapter
        expected, exceptions = {}, {}
        for role in self.roles:
            rows = a._rows(role, require_loaded=True)
            sha = self.fingerprint(rows)
            require(sha == controller.expected_residence[role],
                    'Ledger capture: the walk does not reproduce the admitted fingerprint of ' + role)
            facts, tensors = enumerate_facts(a.patchers[role])
            require(len(facts) == len(rows) and all(fact_matches_row(f, r) for f, r in zip(facts, rows)),
                    'Ledger capture: the fact tuple does not bind to the walk of ' + role)
            patcher = a.patchers[role]
            ids = [id(t) for t in patcher.model.parameters()] + [id(t) for t in patcher.model.buffers()]
            require(ids == [f[2] for f in facts], 'Ledger capture: parameters()/buffers() differ from the walk of '
                    + role)
            exceptions[role] = [(i, r['kind'], r['name'], r['fp32_constructor_exception'])
                                for i, r in enumerate(rows) if r['fp32_constructor_exception'] is not None]
            expected[role] = facts
            self.bound[role] = sha
            self.load_devices[role] = patcher.load_device
        self.expected, self.exceptions = expected, exceptions
        return self.receipt()

    @property
    def ready(self):
        return self.expected is not None

    # -- per snapshot -------------------------------------------------------------------------------
    def facts(self, role):
        return enumerate_facts(self.adapter.patchers[role])

    def walk_ownership(self, role):
        return self.fingerprint(self.adapter._rows(role, require_loaded=True))

    def ownership(self, role, enumerated=None):
        """The walk's residence/ownership SHA-256 of `role`: the bound one when the facts are unchanged (with the
        walk's non-row checks re-run), otherwise the walk's own result."""
        a = self.adapter
        patcher = a.patchers[role]
        device = self.roles[role]
        if str(patcher.load_device) != device or patcher.is_dynamic():
            self.bump('fallback_walks')
            return self.walk_ownership(role)          # raises exactly as the walk does
        facts, tensors = enumerated if enumerated is not None else self.facts(role)
        if facts != self.expected[role]:
            self.bump('fallback_walks')
            return self.walk_ownership(role)
        for index, kind, name, bound in self.exceptions[role]:
            if a._dtype_exception(role, kind, name, tensors[index]) != bound:     # re-pins the constructor source
                self.bump('fallback_walks')
                return self.walk_ownership(role)
        self.require(any(patcher is p for p in a.mm.loaded_models()), 'Reference owner absent from loaded registry')
        self.require(patcher.loaded_size() == patcher.model_size() and patcher.loaded_size() > 0,
                     'Reference model is not fully loaded: ' + role)
        self.bump('fingerprint')
        return self.bound[role]

    def placement(self, enumerated):
        """CandidateAdapter._inspect's `objects['sampler_primary'].verify_placement()` from the fact tuples;
        the sealed call itself on any deviation."""
        a = self.adapter
        primary = a.objects['sampler_primary']
        owners = {id(a.patchers['sampler_primary']): 'sampler_primary',
                  id(a.patchers['sampler_secondary']): 'sampler_secondary'}
        shards = primary.get_additional_models_with_key(SHARD_KEY)
        ok = bool(shards) and not (primary.patches or primary.hook_patches or primary.forced_hooks)
        for patcher in (primary, *(shards or ())):
            role = owners.get(id(patcher))
            ok = ok and role is not None and enumerated[role][0] == self.expected[role] and \
                patcher.load_device == self.load_devices[role] and str(patcher.load_device) == self.roles[role]
        if not ok:
            self.bump('placement_fallbacks')
            primary.verify_placement()
        return True

    def receipt(self):
        with self.lock:
            stats = dict(self.stats)
        return {'schema': SCHEMA, 'ready': self.ready, 'roles': sorted(self.roles),
                'bound_fingerprints': dict(self.bound),
                'tensors': {r: len(f) for r, f in (self.expected or {}).items()},
                'constructor_exceptions': {r: [(k, n) for _, k, n, _ in rows] for r, rows in self.exceptions.items()},
                'stats': stats}


class SnapshotInspector:
    """The controller's `inspect` callable: the walk (CandidateAdapter._inspect) or the fingerprint, with the
    dual-mode proof, per-snapshot timing records and the disagreement latch."""

    def __init__(self, *, mode, adapter, walk_inspect, ledger, roles, cards, pre_floors, phase, latch,
                 clock=time.time_ns, require_fn=None, schedule='full'):
        require(mode in MODES, 'Snapshot mode must be walk or fingerprint')
        require(mode == 'walk' or ledger is not None, 'The fingerprint mode needs a residence ledger')
        self.require = require_fn or require          # native_adapter.require in the server (same messages)
        self.mode, self.adapter, self.walk_inspect, self.ledger = mode, adapter, walk_inspect, ledger
        self.roles, self.cards, self.pre_floors = dict(roles), tuple(cards), dict(pre_floors)
        self.phase, self.latch, self.clock = phase, latch, clock
        self.labels = []                 # labels expected for the next snapshots of the active request
        self.records = []                # records of the active request (drained into its receipt)
        self.chunk_dual = True           # this request: dual by policy (setup/qualification, every 20th chunk)
        self.near_floor = False          # this request: a snapshot read a card within NEAR_FLOOR_BYTES of its floor
        self.disagreement = None
        require(schedule in ('full', 'a-xpu3-sync'), 'Unknown snapshot schedule')
        require(schedule == 'full' or mode == 'fingerprint', 'Reduced barriers require fingerprint mode')
        self.schedule = schedule

    # -- request context (prompt thread) -----------------------------------------------------------------
    def begin_request(self, stream_seq, phase):
        self.labels, self.records = [], []
        self.chunk_dual = phase != 'stream' or (type(stream_seq) is int and stream_seq % DUAL_EVERY == 0)
        self.near_floor = False

    def expect(self, *labels):
        self.labels.extend(labels)

    def reduced_barriers(self, label):
        return (self.schedule == 'a-xpu3-sync' and self.mode == 'fingerprint' and
                self.ledger is not None and self.ledger.ready and not self.chunk_dual and
                not self.near_floor and label in ('A-before', 'A-after'))

    def bind_synchronize(self, controller):
        """Filter the controller's injected barrier too; its inspect and admission stay unchanged.

        Setup has already completed. Default full mode preserves the original callable.
        This callback is prompt-thread only; the decode guard retains its own barriers.
        """
        if self.schedule == 'full':
            return
        require(self.mode == 'fingerprint', 'Reduced barriers require fingerprint mode')
        original = controller.synchronize
        def synchronize(card):
            label = self.labels[0] if self.labels else None
            if not self.reduced_barriers(label) or card == 'xpu:3':
                original(card)
        controller.synchronize = synchronize

    def drain(self):
        rows, self.records = self.records, []
        self.labels = []
        return rows

    # -- the inspect callable -------------------------------------------------------------------------
    def __call__(self, objects, observation=False):
        label = self.labels.pop(0) if self.labels else None
        start = self.clock()
        sync_cards = self.cards
        if self.mode == 'walk' or observation or not self.ledger.ready:
            snap, parts = self._timed_walk(objects, observation)
            dual = agree = False
        elif self.chunk_dual or self.near_floor:
            snap, parts = self._dual(objects, observation, None, label)
            dual = agree = True
        else:
            if self.reduced_barriers(label):
                sync_cards = ('xpu:3',)
            snap, parts = self._fingerprint(objects, observation, sync_cards=sync_cards)
            dual = agree = False
            if self._near(snap):
                self.near_floor = True
                snap, walk_parts = self._dual(objects, observation, snap, label)
                parts.update(walk_parts)
                dual = agree = True
                sync_cards = self.cards
        end = self.clock()
        if label is not None and not observation:
            self.records.append({'label': label, 'mode': self.mode, 'dual': dual, 'agree': True if agree else None,
                                 'start_ns': start, 'end_ns': end, 'seconds': round((end - start) / 1e9, 6),
                                 'parts_s': {k: round(v, 6) for k, v in parts.items()},
                                 'synchronized': list(sync_cards),
                                 'memory_cards': list(self.cards),
                                 'min_margin_bytes': self._margin(snap)})
        return snap

    def _margin(self, snap):
        free = snap.get('physical_free_bytes') if type(snap) is dict else None
        if type(free) is not dict:
            return None
        values = [free[c] - self.pre_floors[c] for c in self.cards if type(free.get(c)) is int]
        return min(values) if values else None

    def _near(self, snap):
        margin = self._margin(snap)
        return margin is not None and margin <= NEAR_FLOOR_BYTES

    def _timed_walk(self, objects, observation):
        t0 = time.perf_counter()
        snap = self.walk_inspect(objects, observation)
        return snap, {'walk': time.perf_counter() - t0}

    def _fingerprint(self, objects, observation, sync_cards=None):
        """CandidateAdapter._inspect with the residence and the sampler placement from the ledger."""
        a, ledger = self.adapter, self.ledger
        parts = {}
        t0 = time.perf_counter()
        self.require(all(objects[r] is a.objects[r] for r in self.roles), 'Objects changed')
        state = a._state(observation)
        t1 = time.perf_counter()
        enumerated = {r: ledger.facts(r) for r in self.roles}
        t2 = time.perf_counter()
        ledger.placement(enumerated)
        residence = {r: {'object_id': id(o), 'device': self.roles[r], 'dtype': 'torch.bfloat16',
                         'fully_resident': True, 'ownership_sha256': ledger.ownership(r, enumerated[r])}
                     for r, o in a.objects.items()}
        if a.controller is not None:
            self.require(all(row['ownership_sha256'] == a.controller.expected_residence[r]
                          for r, row in residence.items()), 'Admitted tensor ownership changed')
        t3 = time.perf_counter()
        inventory = state['route_inventory']
        if sync_cards is None or tuple(sync_cards) == self.cards:
            free = a._free()
        else:
            # Safety trade: all readings remain fresh, but 0/1/2 are not drained.
            # No stale/fabricated readings are handed to the unchanged controller.
            for card in sync_cards:
                a.torch.xpu.synchronize(card)
            free = {c: a.torch.xpu.mem_get_info(c)[0] for c in self.cards}
            self.require(all(type(v) is int and v >= 0 for v in free.values()),
                         'Invalid physical free-memory readings')
        peaks = {c: {'allocated': a.torch.xpu.memory_allocated(c), 'reserved': a.torch.xpu.memory_reserved(c),
                     'peak': a.torch.xpu.max_memory_allocated(c)} for c in self.cards}
        t4 = time.perf_counter()
        parts.update(state=t1 - t0, facts=t2 - t1, residence=t3 - t2, memory=t4 - t3)
        return ({'plan_sha256': a.plan_sha256, 'runtime_sha256': a.runtime_sha256,
                 'phase': 'candidate-stream', 'fault': False,
                 'text_graphs_captured': True, 'window_qualified': True,
                 'sampler_routes': inventory['routes'], 'route_inventory': inventory,
                 'decoder_replicas': 0, 'residence': residence,
                 'physical_free_bytes': free, 'peaks': peaks,
                 'observed_state': state, 'timestamp_ns': time.time_ns(), 'residence_mode': 'fingerprint'}, parts)

    def _dual(self, objects, observation, fingerprint_snap, label=None):
        """Walk and fingerprint on the same objects; the walk's snapshot is the one the controller admits."""
        ledger = self.ledger
        ledger.bump('dual_walks')
        t0 = time.perf_counter()
        walk = walk_error = fp_error = None
        try:
            walk = self.walk_inspect(objects, observation)
        except Exception as error:      # noqa: BLE001 - compared below, then re-raised
            walk_error = error
        t1 = time.perf_counter()
        fp = fingerprint_snap
        if fp is None:
            try:
                fp, _ = self._fingerprint(objects, observation)
            except Exception as error:  # noqa: BLE001
                fp_error = error
        t2 = time.perf_counter()
        if walk_error is not None and (fp_error is not None or fp is None):
            ledger.bump('agreements')
            raise walk_error             # both refused: same verdict (the walk's refusal is the one reported)
        if walk_error is not None or fp_error is not None:
            self._disagree('one mode refused and the other admitted', walk_error or fp_error)
        differ = sorted(k for k in VERDICT_KEYS if walk.get(k) != fp.get(k))
        if differ:
            self._disagree('verdict fields differ: %s' % differ, None)
        # Compare admission verdicts, not changing allocator byte counts. The six labeled
        # sites use PRE_BYTES before and 2 GiB after, as the sealed controller does.
        required = ({c: 2 ** 31 for c in self.cards} if label and label.endswith('-after')
                    else self.pre_floors)
        if self._memory_admitted(walk, required) != self._memory_admitted(fp, required):
            self._disagree('memory admission verdicts differ', None)
        if self._near(walk) or self._near(fp):
            self.near_floor = True
        ledger.bump('agreements')
        walk = dict(walk, residence_mode='walk+fingerprint')
        return walk, {'dual_walk': t1 - t0, 'dual_fingerprint': t2 - t1}

    def _memory_admitted(self, snap, required):
        # CandidateSafety._snapshot's free/allocator checks, without mutating the controller.
        valid_bytes = lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0
        free, peaks = snap.get('physical_free_bytes'), snap.get('peaks')
        if not isinstance(free, dict) or set(free) != set(self.cards):
            return False
        if not isinstance(peaks, dict) or set(peaks) != set(self.cards):
            return False
        for card in self.cards:
            if not valid_bytes(free[card]) or free[card] < required[card]:
                return False
            row = peaks[card]
            if (not isinstance(row, dict) or set(row) != {'allocated', 'reserved', 'peak'} or
                    not all(valid_bytes(v) for v in row.values()) or
                    row['reserved'] < row['allocated'] or row['peak'] < row['allocated']):
                return False
        return True

    def observe_xpu3_free(self, free, floor):
        # Use the actual P5 reading, including on the post-encode snapshot.
        if type(free) is int and free <= floor + NEAR_FLOOR_BYTES:
            self.near_floor = True

    def _disagree(self, why, error):
        self.ledger.bump('disagreements')
        reason = 'Snapshot fingerprint disagrees with the walk: %s (%r)' % (why, error)
        self.disagreement = reason
        try:
            self.latch(reason)
        finally:
            raise SnapshotDisagreement(reason)

    # -- the decode thread's xpu:3 snapshot (P7) -----------------------------------------------------
    def xpu3_callbacks(self, xpu3_free, xpu3_floor, *, always_dual=False):
        """(rows, fingerprint) callables for precompute_guard.Xpu3Snapshot: rows(role) -> role; fingerprint(role)
        -> the role's residence SHA-256 (fingerprint, or dual with the walk under the same policy)."""
        ledger = self.ledger
        require(self.mode == 'fingerprint', 'Walk mode keeps the packet-117 P7 callables (rows + fingerprint)')

        def fingerprint(role):
            if not ledger.ready:
                return ledger.walk_ownership(role)
            # Runtime always dual-checks P7: decode jobs overlap successor requests,
            # so their policy cannot safely use the prompt thread's mutable chunk number.
            if not always_dual:
                self.observe_xpu3_free(xpu3_free(), xpu3_floor)
            dual = always_dual or self.phase() != 'stream' or self.chunk_dual or self.near_floor
            value = None
            error = None
            try:
                value = ledger.ownership(role)
            except Exception as exc:     # noqa: BLE001
                error = exc
            ledger.bump('xpu3_fingerprint')
            if not dual:
                if error is not None:
                    raise error
                return value
            ledger.bump('xpu3_dual')
            try:
                walked, walk_error = ledger.walk_ownership(role), None
            except Exception as exc:     # noqa: BLE001
                walked, walk_error = None, exc
            if walk_error is not None and error is not None:
                raise walk_error
            if walk_error is not None or error is not None or walked != value:
                self._disagree('xpu:3 residence of %s (walk %r, fingerprint %r)' % (role, walked, value),
                               walk_error or error)
            return walked
        return (lambda role: role), fingerprint

    def summary(self):
        return {'schema': SCHEMA, 'mode': self.mode, 'schedule': self.schedule, 'dual_every': DUAL_EVERY,
                'near_floor_bytes': NEAR_FLOOR_BYTES, 'disagreement': self.disagreement,
                'ledger': self.ledger.receipt() if self.ledger is not None else None}
