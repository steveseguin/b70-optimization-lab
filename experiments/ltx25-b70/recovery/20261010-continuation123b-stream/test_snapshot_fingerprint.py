"""CPU tests (packet123): the four-card safety snapshot from residence fingerprints (snapshot_fingerprint.py).

The world is a set of fake tensors behind seven fake patchers (str(device) is the role's card, as on the server);
the walk is the REAL sealed code: NativeAdapter._rows / _dtype_exception and native_adapter.fingerprint (packet
111), CandidateAdapter._inspect and CandidateSafety (candidate_safety.py, pinned by conditioning_guard), with one
real FP32 constructor exception (model_sampling.sigmas, its source pinned to the sealed packet file).

What CPU shows:
1. The ledger binds each role's fact tuple to the admitted fingerprint (one walk), and refuses a binding that does
   not reproduce it.
2. Verdict equivalence: under every single mutation the walk can see (storage moved, shape, dtype, device, a tensor
   replaced, added, removed or renamed, a buffer changed, the load device, dynamic mode, the loaded registry, the
   loaded size, the FP32 exception's source pin) and under 300 random mutation sequences, the fingerprint returns
   the walk's SHA-256 or raises the walk's exception (type and message), role by role; mutations the walk cannot
   see (values) leave both unchanged. The sampler placement check equals the sealed verify_placement likewise.
3. Through the REAL CandidateSafety, a request's six snapshots in walk and in fingerprint mode give the same
   controller receipts (events, floors, residence, admission) and synchronise the same cards; a mutation makes both
   refuse with the same reason.
4. The proof policy: setup/qualification run every snapshot dual, streaming every 20th chunk and every snapshot from
   a near-floor reading on (per chunk); a disagreement writes the latch and raises; a refusal of both modes is the
   walk's refusal (no latch); walk mode never uses a ledger; the decode thread's xpu:3 P7 callbacks follow the same
   policy.
What CPU cannot show: the cost on the live server (the receipts' `snapshots[].seconds` and `parts_s` measure it) and
that no XPU-side mechanism moves a parameter without changing the facts read here (the dual walks are the check).
"""
import copy
import random
import types
import unittest
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SEALED111 = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-native-111/source/scripts')
PACKET117 = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-117')
sys.path.insert(0, str(HERE))
sys.path.append(str(SEALED111))     # sealed native_safety / native_adapter only; -B keeps it untouched
import candidate_safety as cs  # noqa: E402
import native_adapter  # noqa: E402
import snapshot_fingerprint as sf  # noqa: E402
from native_safety import CARDS, GIB, PRE_BYTES, ROLES, SafetyRefusal  # noqa: E402

MM_FILE = PACKET117 / 'source/comfy/model_management.py'
SIGMAS_SOURCE = PACKET117 / 'source/comfy/model_sampling.py'


class FakeDevice:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'FakeDevice(%r)' % self.name

    def __eq__(self, other):
        return str(other) == self.name

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.name)


class FakeStorage:
    def __init__(self, ptr):
        self.ptr = ptr

    def data_ptr(self):
        return self.ptr


class FakeTensor:
    counter = [0x100000]

    def __init__(self, shape, device, dtype='torch.bfloat16', size=2):
        self.shape, self.device, self.dtype, self.size = tuple(shape), FakeDevice(device), dtype, size
        FakeTensor.counter[0] += 0x1000
        self.ptr = FakeTensor.counter[0]
        self.values = 0.0

    def untyped_storage(self):
        return FakeStorage(self.ptr)

    def numel(self):
        n = 1
        for s in self.shape:
            n *= s
        return n

    def element_size(self):
        return self.size


class FakeModel:
    def __init__(self, role, device, count):
        self.params = [['%s.w%d' % (role, i), FakeTensor([4, i + 1], device)] for i in range(count)]
        self.buffers_ = [['%s.b0' % role, FakeTensor([2], device, 'torch.int64', 8)]]
        if role == 'sampler_primary':
            self.buffers_.append(['model_sampling.sigmas', FakeTensor([10000], device, 'torch.float32', 4)])

    def named_parameters(self):
        return iter([tuple(x) for x in self.params])

    def named_buffers(self):
        return iter([tuple(x) for x in self.buffers_])

    def parameters(self):
        return iter([t for _, t in self.params])

    def buffers(self):
        return iter([t for _, t in self.buffers_])


class FakePatcher:
    def __init__(self, role, device, count):
        self.role, self.load_device, self.model = role, FakeDevice(device), FakeModel(role, device, count)
        self.patches, self.hook_patches, self.forced_hooks = {}, {}, []
        self.shards, self.dynamic, self.loaded = [], False, 100

    def is_dynamic(self):
        return self.dynamic

    def loaded_size(self):
        return self.loaded

    def model_size(self):
        return 100

    def get_additional_models_with_key(self, key):
        assert key == 'ltx_layer_shard'
        return list(self.shards)

    def verify_placement(self):       # ltx_layer_shard.LTXLayerShardedPatcher.verify_placement (sealed), verbatim logic
        shards = self.get_additional_models_with_key('ltx_layer_shard')
        if not shards:
            raise RuntimeError("LTX shard registration is missing")
        for patcher in (self, *shards):
            misplaced = [str(t.device) for t in tuple(patcher.model.parameters()) + tuple(patcher.model.buffers())
                         if t.device != patcher.load_device]
            if misplaced:
                raise RuntimeError(f"LTX shard is not fully resident on {patcher.load_device}: {set(misplaced)}")
        if self.patches or self.hook_patches or self.forced_hooks:
            raise RuntimeError("Native LTX shard acquired unsupported weight/hooks patches")


class World:
    """Seven roles, the REAL walk bound to a fake adapter, and (optionally) the REAL CandidateSafety."""
    _rows = native_adapter.NativeAdapter._rows
    _dtype_exception = native_adapter.NativeAdapter._dtype_exception
    _pin = native_adapter.NativeAdapter._pin
    _inspect_walk = cs.CandidateAdapter._inspect

    def __init__(self, count=5):
        self.patchers = {role: FakePatcher(role, device, count) for role, device in ROLES.items()}
        self.patchers['sampler_primary'].shards = [self.patchers['sampler_secondary']]
        self.objects = {}
        for role in ROLES:
            if role.endswith('_vae'):
                self.objects[role] = types.SimpleNamespace(patcher=self.patchers[role], role=role)
            else:
                self.objects[role] = self.patchers[role]
        self.registry = list(self.patchers.values())
        self.mm = types.SimpleNamespace(loaded_models=lambda: list(self.registry), __file__=str(MM_FILE))
        self.source_hashes = {str(SIGMAS_SOURCE.resolve()): native_adapter.FP32_SOURCES['model_sampling.py']}
        self.bound_sources = {}
        self.plan_sha256, self.runtime_sha256 = 'a' * 64, 'b' * 64
        self.free = {'xpu:0': 10 * GIB, 'xpu:1': 10 * GIB, 'xpu:2': 10 * GIB, 'xpu:3': 13 * GIB}
        self.torch = types.SimpleNamespace(xpu=types.SimpleNamespace(
            memory_allocated=lambda c: 1, memory_reserved=lambda c: 2, max_memory_allocated=lambda c: 3))
        self.controller = None
        self.state_calls = 0

    def _state(self, observation=False):
        self.state_calls += 1
        return {'route_inventory': {'passed': True, 'routes': 48, 'state': 'pinned'}}

    def _free(self):
        return dict(self.free)

    def _inspect(self, objects, observation=False):
        return World._inspect_walk(self, objects, observation)

    def walk_sha(self, role):
        return native_adapter.fingerprint(self._rows(role, require_loaded=True))

    def admitted(self):
        return {role: self.walk_sha(role) for role in ROLES}


def outcome(fn):
    try:
        return ('ok', fn())
    except Exception as error:      # noqa: BLE001
        return ('raise', type(error).__name__, str(error))


# -- mutations (each returns nothing; the walk sees all but 'values') ------------------------------------------------
def param(w, role, i):
    params = w.patchers[role].model.params
    return params[min(i, len(params) - 1)] if params else None


def m_storage(w, role):
    if param(w, role, 1):
        param(w, role, 1)[1].ptr += 0x40                                # .data = <other storage>


def m_shape(w, role):
    if param(w, role, 2):
        param(w, role, 2)[1].shape = (4, 99)                            # resize_ / .data = view


def m_dtype(w, role):
    if param(w, role, 0):
        param(w, role, 0)[1].dtype = 'torch.float16'                    # .data = t.half()


def m_device(w, role):
    if param(w, role, 0):
        param(w, role, 0)[1].device = FakeDevice('cpu')                 # offloaded


def m_device_other_card(w, role):
    other = {'xpu:0': 'xpu:1'}.get(ROLES[role], 'xpu:0')
    if param(w, role, 3):
        param(w, role, 3)[1].device = FakeDevice(other)


def m_replace(w, role):
    row = param(w, role, 1)
    if row:
        old = row[1]
        new = FakeTensor(old.shape, str(old.device), old.dtype)
        new.ptr = old.ptr                                                  # same storage, new tensor object
        row[1] = new


def m_add(w, role):
    w.patchers[role].model.params.append(['%s.extra' % role, FakeTensor([4, 4], ROLES[role])])


def m_remove(w, role):
    if w.patchers[role].model.params:
        w.patchers[role].model.params.pop(min(2, len(w.patchers[role].model.params) - 1))


def m_rename(w, role):
    if param(w, role, 0):
        param(w, role, 0)[0] += '_renamed'


def m_reorder(w, role):
    p = w.patchers[role].model.params
    if len(p) > 1:
        p[0], p[1] = p[1], p[0]


def m_buffer(w, role):
    w.patchers[role].model.buffers_[0][1].ptr += 0x80


def m_load_device(w, role):
    w.patchers[role].load_device = FakeDevice('xpu:2' if ROLES[role] != 'xpu:2' else 'xpu:3')


def m_dynamic(w, role):
    w.patchers[role].dynamic = True


def m_unregistered(w, role):
    if w.patchers[role] in w.registry:
        w.registry.remove(w.patchers[role])


def m_partially_loaded(w, role):
    w.patchers[role].loaded = 50


def m_sigmas_dtype(w, role):
    if role == 'sampler_primary':
        w.patchers[role].model.buffers_[1][1].dtype = 'torch.bfloat16'


def m_sigmas_pin(w, role):
    w.source_hashes = {k: '0' * 64 for k in w.source_hashes}            # the constructor source pin changed


def m_values(w, role):
    if param(w, role, 0):
        param(w, role, 0)[1].values += 1.0                              # in-place value change (invisible to both)


MUTATIONS = [m_storage, m_shape, m_dtype, m_device, m_device_other_card, m_replace, m_add, m_remove, m_rename,
             m_reorder, m_buffer, m_load_device, m_dynamic, m_unregistered, m_partially_loaded, m_sigmas_dtype,
             m_sigmas_pin, m_values]


def ledger_for(w):
    w.controller = types.SimpleNamespace(expected_residence=w.admitted())
    ledger = sf.ResidenceLedger(adapter=w, roles=ROLES, fingerprint=native_adapter.fingerprint,
                                require_fn=native_adapter.require)
    ledger.capture(w.controller)
    return ledger


class Ledger(unittest.TestCase):
    def test_capture_binds_the_admitted_fingerprints(self):
        w = World()
        ledger = ledger_for(w)
        receipt = ledger.receipt()
        self.assertTrue(receipt['ready'])
        self.assertEqual(receipt['bound_fingerprints'], w.controller.expected_residence)
        self.assertEqual(receipt['tensors']['sampler_primary'], 7)            # 5 parameters, 2 buffers
        self.assertEqual(receipt['constructor_exceptions']['sampler_primary'], [('buffer', 'model_sampling.sigmas')])
        for role in ROLES:
            self.assertEqual(ledger.ownership(role), w.walk_sha(role))
        self.assertEqual(ledger.stats['fallback_walks'], 0)

    def test_capture_refuses_a_binding_that_does_not_reproduce_the_admitted_one(self):
        w = World()
        w.controller = types.SimpleNamespace(expected_residence=dict(w.admitted(), video_vae='0' * 64))
        ledger = sf.ResidenceLedger(adapter=w, roles=ROLES, fingerprint=native_adapter.fingerprint)
        with self.assertRaises(sf.LedgerRefusal):
            ledger.capture(w.controller)
        self.assertFalse(ledger.ready)

    def test_every_single_mutation_gives_the_walks_verdict(self):
        for mutate in MUTATIONS:
            for role in ROLES:
                w = World()
                ledger = ledger_for(w)
                mutate(w, role)
                for r in ROLES:
                    want = outcome(lambda: w.walk_sha(r))
                    got = outcome(lambda: ledger.ownership(r))
                    self.assertEqual(got, want, (mutate.__name__, role, r))

    def test_value_changes_are_invisible_to_both(self):
        w = World()
        ledger = ledger_for(w)
        m_values(w, 'video_vae')
        self.assertEqual(ledger.ownership('video_vae'), w.controller.expected_residence['video_vae'])
        self.assertEqual(ledger.stats['fallback_walks'], 0)

    def test_random_mutation_sequences(self):
        rng = random.Random(118)
        for trial in range(300):
            w = World(count=rng.randint(3, 8))
            ledger = ledger_for(w)
            for _ in range(rng.randint(0, 3)):
                rng.choice(MUTATIONS)(w, rng.choice(list(ROLES)))
            for r in ROLES:
                self.assertEqual(outcome(lambda: ledger.ownership(r)), outcome(lambda: w.walk_sha(r)), (trial, r))

    def test_placement_equals_the_sealed_verify_placement(self):
        def m_no_shards(w):
            w.patchers['sampler_primary'].shards = []

        def m_patches(w):
            w.patchers['sampler_primary'].patches = {'x': 1}

        def m_foreign_shard(w):
            w.patchers['sampler_primary'].shards = [w.patchers['upsampler']]

        def m_secondary_device(w):
            m_device_other_card(w, 'sampler_secondary')

        def m_primary_load_device(w):
            w.patchers['sampler_primary'].load_device = FakeDevice('xpu:1')

        cases = [lambda w: None, m_no_shards, m_patches, m_foreign_shard, m_secondary_device, m_primary_load_device,
                 lambda w: m_storage(w, 'sampler_secondary'), lambda w: m_values(w, 'sampler_primary')]
        for mutate in cases:
            w = World()
            ledger = ledger_for(w)
            mutate(w)
            enumerated = {r: ledger.facts(r) for r in ROLES}
            want = outcome(lambda: w.objects['sampler_primary'].verify_placement())
            got = outcome(lambda: ledger.placement(enumerated))
            self.assertEqual(got[0], want[0], mutate)
            if want[0] == 'raise':
                self.assertEqual(got, want)


class ThroughCandidateSafety(unittest.TestCase):
    """The REAL CandidateSafety with inspect = the SnapshotInspector in walk and in fingerprint mode."""

    def build(self, mode, phase='stream', latch=None, world=None):
        w = world or World()
        for role in ('video_vae', 'audio_vae'):                  # a fresh controller on the same objects
            if hasattr(w.objects[role], '_ltx_native_reference_safety'):
                delattr(w.objects[role], '_ltx_native_reference_safety')
        expected = w.admitted()
        ledger = None
        if mode == 'fingerprint':
            ledger = sf.ResidenceLedger(adapter=w, roles=ROLES, fingerprint=native_adapter.fingerprint,
                                        require_fn=native_adapter.require)
        latches = []
        inspector = sf.SnapshotInspector(mode=mode, adapter=w, walk_inspect=w._inspect, ledger=ledger, roles=ROLES,
                                         cards=CARDS, pre_floors=PRE_BYTES, phase=lambda: phase,
                                         latch=latch or latches.append, require_fn=native_adapter.require)
        synced = []
        ctl = cs.CandidateSafety(plan_sha256=w.plan_sha256, runtime_sha256=w.runtime_sha256, objects=w.objects,
                                 expected_residence=expected, synchronize=synced.append,
                                 inspect=lambda objects, observation=False: inspector(objects, observation),
                                 require_phase=lambda: None)
        w.controller = ctl
        if ledger is not None:
            ledger.capture(ctl)
        return w, ctl, inspector, synced, latches

    def request(self, ctl, inspector, name, seq):
        inspector.begin_request(seq, 'stream')
        inspector.expect('request-before')
        ctl.before(name)
        for stage in ('A', 'B'):
            inspector.expect(stage + '-before', stage + '-after')
            ctl._snapshot('conditioning-%s-before' % stage, PRE_BYTES)
            ctl._snapshot('conditioning-%s-after' % stage, {c: 2 * GIB for c in CARDS})
        inspector.expect('request-after')
        ctl.after()
        return inspector.drain()

    @staticmethod
    def comparable(receipts):
        out = []
        for r in receipts:
            snap = {k: v for k, v in r['snapshot'].items()
                    if k not in ('timestamp_ns', 'observed_state', 'residence_mode')}
            out.append((r['event'], r['required_physical_free_bytes'], r['admitted'], snap))
        return out

    def test_walk_and_fingerprint_take_identical_snapshots(self):
        runs = {}
        world = World()
        for mode in sf.MODES:
            w, ctl, inspector, synced, latches = self.build(mode, world=world)
            records = self.request(ctl, inspector, 'stream123b-s00000001', 1)
            runs[mode] = (self.comparable(ctl.drain()), synced, [r['label'] for r in records], latches)
            self.assertEqual([r['mode'] for r in records], [mode] * 6)
            self.assertEqual([r['dual'] for r in records], [False] * 6)
        self.assertEqual(runs['walk'][0], runs['fingerprint'][0])
        self.assertEqual(runs['walk'][1], runs['fingerprint'][1])
        self.assertEqual(runs['walk'][1], list(CARDS) * 6)
        self.assertEqual(runs['walk'][2], ['request-before', 'A-before', 'A-after', 'B-before', 'B-after',
                                           'request-after'])
        self.assertEqual(runs['fingerprint'][3], [])

    def test_a_mutation_is_refused_alike(self):
        reasons = {}
        for mode in sf.MODES:
            w, ctl, inspector, _, latches = self.build(mode)
            m_storage(w, 'text_secondary')
            inspector.begin_request(1, 'stream')
            inspector.expect('request-before')
            with self.assertRaises(SafetyRefusal) as ctx:
                ctl.before('stream123b-s00000001')
            reasons[mode] = (str(ctx.exception), ctl.failed)
            self.assertEqual(latches, [])
        self.assertEqual(reasons['walk'], reasons['fingerprint'])
        self.assertIn('Admitted tensor ownership changed', reasons['walk'][0])

    def test_policy_dual_in_qualification_every_20th_and_near_floor(self):
        w, ctl, inspector, _, _ = self.build('fingerprint')
        calls = []
        inner = inspector.walk_inspect
        inspector.walk_inspect = lambda o, obs=False: (calls.append(1), inner(o, obs))[1]
        inspector.begin_request(-1, 'stream_qualification')
        inspector.expect('request-before')
        ctl.before('stream123b-qeager-c000000')
        self.assertEqual(inspector.records[-1]['dual'], True)
        inspector.expect('request-after')
        ctl.after()
        self.assertEqual(len(calls), 2)
        for seq, dual in ((19, False), (20, True), (21, False), (40, True)):
            calls.clear()
            inspector.begin_request(seq, 'stream')
            inspector.expect('request-before')
            ctl.before('stream123b-s%08d' % seq)
            inspector.expect('request-after')
            ctl.after()
            self.assertEqual([r['dual'] for r in inspector.drain()], [dual, dual], seq)
            self.assertEqual(len(calls), 2 if dual else 0)
        # near floor: xpu:0 within 0.5 GiB of 8 GiB from the second snapshot of this chunk on
        inspector.begin_request(41, 'stream')
        inspector.expect('request-before')
        ctl.before('stream123b-s00000041')
        w.free['xpu:0'] = 8 * GIB + sf.NEAR_FLOOR_BYTES - 1
        inspector.expect('A-before', 'A-after')
        ctl._snapshot('conditioning-A-before', PRE_BYTES)
        w.free['xpu:0'] = 10 * GIB
        ctl._snapshot('conditioning-A-after', {c: 2 * GIB for c in CARDS})
        inspector.expect('request-after')
        ctl.after()
        self.assertEqual([r['dual'] for r in inspector.drain()], [False, True, True, True])
        inspector.begin_request(42, 'stream')                    # the next chunk starts without the flag
        inspector.expect('request-before')
        ctl.before('stream123b-s00000042')
        self.assertEqual(inspector.records[-1]['dual'], False)
        self.assertEqual(inspector.records[-1]['min_margin_bytes'], 2 * GIB)

    def test_disagreement_latches_and_raises(self):
        latched = []
        w, ctl, inspector, _, _ = self.build('fingerprint', phase='stream_qualification', latch=latched.append)
        inner = inspector.walk_inspect

        def lying_walk(objects, observation=False):
            snap = inner(objects, observation)
            snap['residence']['audio_vae'] = dict(snap['residence']['audio_vae'], ownership_sha256='0' * 64)
            return snap
        inspector.walk_inspect = lying_walk
        inspector.begin_request(-1, 'stream_qualification')
        inspector.expect('request-before')
        with self.assertRaises(SafetyRefusal) as ctx:
            ctl.before('stream123b-qeager-c000000')
        self.assertIn('Snapshot fingerprint disagrees with the walk', str(ctx.exception))
        self.assertEqual(len(latched), 1)
        self.assertIn("['residence']", latched[0])
        self.assertEqual(inspector.ledger.stats['disagreements'], 1)

    def test_one_mode_refusing_is_a_disagreement_both_refusing_is_not(self):
        latched = []
        w, ctl, inspector, _, _ = self.build('fingerprint', phase='stream_qualification', latch=latched.append)
        inspector.walk_inspect = lambda objects, observation=False: (_ for _ in ()).throw(RuntimeError('walk only'))
        with self.assertRaises(sf.SnapshotDisagreement):
            inspector._dual(w.objects, False, None)
        self.assertEqual(len(latched), 1)
        latched.clear()
        w2, ctl2, inspector2, _, _ = self.build('fingerprint', phase='stream_qualification', latch=latched.append)
        m_unregistered(w2, 'upsampler')                       # both modes refuse: the walk's refusal, no latch
        with self.assertRaises(SafetyRefusal) as ctx:
            inspector2._dual(w2.objects, False, None)
        self.assertIn('Reference owner absent from loaded registry', str(ctx.exception))
        self.assertEqual(latched, [])

    def test_walk_mode_needs_no_ledger_and_observation_is_always_the_walk(self):
        w, ctl, inspector, _, _ = self.build('walk')
        self.assertIsNone(inspector.ledger)
        inspector.begin_request(1, 'stream')
        inspector.expect('request-before')
        ctl.before('stream123b-s00000001')
        self.assertEqual(inspector.records[-1]['parts_s'].keys(), {'walk'})
        w2, ctl2, inspector2, _, _ = self.build('fingerprint')
        calls = []
        inner = inspector2.walk_inspect
        inspector2.walk_inspect = lambda o, obs=False: (calls.append(obs), inner(o, obs))[1]
        inspector2(w2.objects, observation=True)
        self.assertEqual(calls, [True])
        with self.assertRaises(sf.LedgerRefusal):
            sf.SnapshotInspector(mode='fingerprint', adapter=w, walk_inspect=w._inspect, ledger=None, roles=ROLES,
                                 cards=CARDS, pre_floors=PRE_BYTES, phase=lambda: 'stream', latch=print)

    def test_xpu3_callbacks_follow_the_policy(self):
        latched = []
        w, ctl, inspector, _, _ = self.build('fingerprint', latch=latched.append)
        free = {'value': 13 * GIB}
        rows, fingerprint = inspector.xpu3_callbacks(lambda: free['value'], 9 * GIB)
        self.assertEqual(rows('video_vae'), 'video_vae')
        inspector.begin_request(1, 'stream')
        before = dict(inspector.ledger.stats)
        for role in ('text_secondary', 'video_vae', 'audio_vae'):
            self.assertEqual(fingerprint(role), ctl.expected_residence[role])
        self.assertEqual(inspector.ledger.stats['xpu3_dual'], before['xpu3_dual'])
        free['value'] = 9 * GIB + 1                            # near the 9 GiB floor: dual
        self.assertEqual(fingerprint('audio_vae'), ctl.expected_residence['audio_vae'])
        self.assertEqual(inspector.ledger.stats['xpu3_dual'], before['xpu3_dual'] + 1)
        self.assertTrue(inspector.near_floor)
        free['value'] = 13 * GIB
        inspector.begin_request(20, 'stream')                  # every 20th chunk: dual
        fingerprint('video_vae')
        self.assertEqual(inspector.ledger.stats['xpu3_dual'], before['xpu3_dual'] + 2)
        inspector.ledger.bound['video_vae'] = '0' * 64        # a fingerprint that would differ from the walk
        with self.assertRaises(sf.SnapshotDisagreement):
            fingerprint('video_vae')
        self.assertEqual(len(latched), 1)
        w2, ctl2, inspector2, _, _ = self.build('walk')
        with self.assertRaises(sf.LedgerRefusal):              # walk mode keeps packet 117's P7 callables
            inspector2.xpu3_callbacks(lambda: 13 * GIB, 9 * GIB)


    def test_review_decode_policy_survives_successor_request(self):
        _, ctl, inspector, _, _ = self.build('fingerprint')
        inspector.begin_request(20, 'stream')
        rows, fingerprint = inspector.xpu3_callbacks(lambda: 13 * GIB, 9 * GIB, always_dual=True)
        inspector.begin_request(21, 'stream')
        before = inspector.ledger.stats['xpu3_dual']
        for role in ('text_secondary', 'video_vae', 'audio_vae'):
            self.assertEqual(fingerprint(rows(role)), ctl.expected_residence[role])
        self.assertEqual(inspector.ledger.stats['xpu3_dual'] - before, 3)

    def test_review_actual_p5_reading_inclusive_boundary_is_sticky(self):
        import precompute_guard as pg
        w, ctl, inspector, _, _ = self.build('fingerprint')
        inspector.begin_request(21, 'stream')
        # No extra memory read is allowed to replace P5's observed near-floor reading.
        def reread():
            self.fail('P7 must not reread memory to choose its runtime policy')
        rows, fingerprint = inspector.xpu3_callbacks(reread, pg.PRE_FLOOR, always_dual=True)
        synced = []
        guard = pg.Xpu3Snapshot(
            controller=ctl, phase_ok=lambda: True, fault=lambda: False, synchronize=synced.append,
            free_bytes=lambda card: pg.PRE_FLOOR + sf.NEAR_FLOOR_BYTES,
            counters=lambda card: {'allocated': 1, 'reserved': 2, 'peak': 3},
            rows=rows, fingerprint=fingerprint,
            observe_free=lambda free: inspector.observe_xpu3_free(free, pg.PRE_FLOOR))
        before = inspector.ledger.stats['xpu3_dual']
        guard.take('precompute-A-before', pg.PRE_FLOOR)
        self.assertEqual(synced, ['xpu:3'])
        self.assertTrue(inspector.near_floor)
        self.assertEqual(inspector.ledger.stats['xpu3_dual'] - before, 3)
        inspector.expect('request-before')
        ctl.before('successor')
        self.assertTrue(inspector.records[-1]['dual'])

    def test_review_dual_checks_floor_and_counter_verdicts(self):
        for mutate in (lambda s: s['physical_free_bytes'].__setitem__('xpu:3', 0),
                       lambda s: s['peaks']['xpu:3'].__setitem__('reserved', 0)):
            w, _, inspector, _, latches = self.build('fingerprint')
            original = inspector._fingerprint
            def changed(objects, observation=False):
                snap, parts = original(objects, observation)
                mutate(snap)
                return snap, parts
            inspector._fingerprint = changed
            with self.assertRaises(sf.SnapshotDisagreement):
                inspector._dual(w.objects, False, None, 'request-before')
            self.assertEqual(len(latches), 1)

    def test_review_dual_compares_admission_not_exact_bytes_or_wrong_floor(self):
        w, _, inspector, _, latches = self.build('fingerprint')
        original = inspector._fingerprint
        def changed(objects, observation=False):
            snap, parts = original(objects, observation)
            snap['physical_free_bytes']['xpu:3'] = 3 * GIB
            return snap, parts
        inspector._fingerprint = changed
        inspector._dual(w.objects, False, None, 'B-after')
        self.assertEqual(latches, [])
        self.assertTrue(inspector.near_floor)

    def test_review_near_floor_equality_and_dual_walk_reading(self):
        w, _, inspector, _, _ = self.build('fingerprint')
        inspector.begin_request(21, 'stream')
        w.free['xpu:3'] = 9 * GIB + sf.NEAR_FLOOR_BYTES
        inspector.expect('request-before')
        inspector(w.objects)
        self.assertTrue(inspector.records[-1]['dual'])
        self.assertTrue(inspector.near_floor)
        inspector.begin_request(40, 'stream')
        original = inspector._fingerprint
        def high(objects, observation=False):
            snap, parts = original(objects, observation)
            snap['physical_free_bytes']['xpu:3'] = 13 * GIB
            return snap, parts
        inspector._fingerprint = high
        inspector._dual(w.objects, False, None, 'request-before')
        self.assertTrue(inspector.near_floor)


class Wiring(unittest.TestCase):
    """The runtime routes every four-card snapshot and the decode thread's P7 through the inspector."""

    def test_runtime_wiring(self):
        import ast
        text = (HERE / 'integration.py').read_text()
        tree = ast.parse(text)
        fn = {n.name: ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertIn('self.adapter._inspect = self.registry.wrap(inspect)', fn['prepare'])
        self.assertIn('self.registry.wrap(self.ledger.capture)(self.adapter.controller)', fn['prepare'])
        self.assertLess(fn['prepare'].index('self.adapter._inspect = self.registry.wrap(inspect)'),
                        fn['prepare'].index('self.adapter.prepare()'))
        self.assertIn("self.inspector.xpu3_callbacks(", fn['_xpu3_guard'])
        self.assertIn("self.inspector.expect('request-before')", fn['before_request'])
        self.assertIn("self.inspector.expect('request-after')", fn['_after_chunk'])
        self.assertIn("self.inspector.expect(stage + '-before', stage + '-after')", fn['condition'])
        self.assertIn("self.inspector.expect('B-before', 'B-after')", fn['mixed_condition_b'])
        self.assertIn('snapshot_fingerprint.SnapshotDisagreement', fn['_precompute'])

    def test_the_sealed_controller_is_unchanged(self):
        import hashlib
        import conditioning_guard
        self.assertEqual(hashlib.sha256((HERE / 'candidate_safety.py').read_bytes()).hexdigest(),
                         conditioning_guard.CANDIDATE_SHA256)


if __name__ == '__main__':
    unittest.main()
