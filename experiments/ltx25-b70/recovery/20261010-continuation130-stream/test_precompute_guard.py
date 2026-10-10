"""CPU tests (packet117): the precomputed stage-A / stage-B anchor encodes (precompute_guard.py) and the proof
that no conditioning check is weakened.

1. The SEALED native LTXVImgToVideoInplace.execute (compiled on CPU from nodes_lt.py, with the sealed
   comfy.utils.common_upscale) gives byte-identical samples and masks with the real encode and with the
   precomputed encode replayed through ReplayVAE, for stage A (resized 256 -> 128) and stage B at 49, 97 and
   121 frames; ReplayVAE refuses other pixels, a second encode and a changed encode.
2. Xpu3Snapshot: each check P1-P8 refuses on its own fault; it synchronises xpu:3 and nothing else.
3. PrecomputeStore: reservation, supersession of an older anchor, cancel, failure, the bounded wait,
   consume-once.
4. No check is weakened: the REAL CandidateSafety (over the sealed NativeReferenceSafety) and the REAL
   ConditioningStageGuard run one anchored A+B conditioning in the native mode and in the precomputed mode
   (both stages from ReplayVAE through the sealed native node): the four-card snapshot sequence (events,
   required floors, the cards synchronised for each), the guard's receipts and the outputs are identical.
   The checks of the four-card snapshot are listed with where each still runs, and the runtime source is
   checked to route every precomputed stage through the guard's run_stage under the encoder lock.
"""
import ast
import copy
import hashlib
import threading
import time
import types
import unittest
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SEALED111 = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-native-111/source/scripts')
SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-116b/source')
sys.path.insert(0, str(HERE))
sys.path.append(str(SEALED111))     # sealed native_safety / native_adapter only; -B keeps it untouched
import torch  # noqa: E402
import precompute_guard as pg  # noqa: E402
import candidate_safety as cs  # noqa: E402
from native_safety import GIB, ROLES, CARDS  # noqa: E402

KINDS = {}


def tsha(t):
    return hashlib.sha256(t.detach().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


def sealed_native():
    """LTXVImgToVideoInplace and get_noise_mask from the sealed nodes_lt.py, common_upscale from comfy/utils.py."""
    if 'native' in KINDS:
        return KINDS['native']

    def pick(path, names):
        tree = ast.parse(Path(path).read_bytes())
        body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        assert {n.name for n in body} == set(names)
        return compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec')

    utils_ns = {'torch': torch}
    exec(pick(SOURCE / 'comfy/utils.py', ('common_upscale',)), utils_ns)
    comfy = types.SimpleNamespace(utils=types.SimpleNamespace(common_upscale=utils_ns['common_upscale']))

    class NodeOutput:
        def __init__(self, *args, ui=None, expand=None, block_execution=None):
            self.result, self.ui, self.expand, self.block_execution = args, ui, expand, block_execution
    io = types.SimpleNamespace(ComfyNode=type('ComfyNode', (), {}), NodeOutput=NodeOutput)
    ns = {'torch': torch, 'comfy': comfy, 'io': io}
    exec(pick(SOURCE / 'comfy_extras/nodes_lt.py', ('get_noise_mask', 'LTXVImgToVideoInplace')), ns)
    KINDS['native'] = (ns['LTXVImgToVideoInplace'], NodeOutput)
    return KINDS['native']


class FakeVAE:
    """A deterministic stand-in encode: a fixed random projection of the pixels (any function of the bytes)."""
    downscale_index_formula = (8, 32, 32)

    def __init__(self):
        self.calls = []
        gen = torch.Generator().manual_seed(7)
        self.weight = torch.randn(3 * 32 * 32, 128, generator=gen)

    def encode(self, pixels):
        self.calls.append(threading.current_thread().name)
        b, h, w, c = pixels.shape
        patches = pixels.reshape(b, h // 32, 32, w // 32, 32, c).permute(0, 1, 3, 2, 4, 5).reshape(b, h // 32, w // 32, -1)
        t = (patches @ self.weight).permute(0, 3, 1, 2).unsqueeze(2)       # [1, 128, 1, h/32, w/32]
        return t.contiguous().to(torch.float32)


def anchor(seed=3):
    return torch.rand(1, 256, 256, 3, generator=torch.Generator().manual_seed(seed))


def stage_latent(stage, frames, seed=5):
    t = {49: 7, 97: 13, 121: 16}[frames]
    h = 4 if stage == 'A' else 8
    return {'samples': torch.randn(1, 128, t, h, h, generator=torch.Generator().manual_seed(seed))}


def precompute(vae, image, stage, frames):
    """What the decode thread does: the native node with a CaptureVAE on a zero latent of the stage's shape."""
    node, _ = sealed_native()
    capture = pg.CaptureVAE(torch, vae)
    shape = list(stage_latent(stage, frames)['samples'].shape)
    node.execute(vae=capture, image=image, latent={'samples': torch.zeros(shape)}, strength=1.0, bypass=False)
    record, t = capture.calls[0]
    entry = pg.Entry(tsha(image), stage, 'pred')
    entry.state, entry.t, entry.record = 'done', t.clone(), record
    return entry


class NativeNodeEquivalence(unittest.TestCase):
    def test_replayed_encode_equals_the_native_encode(self):
        node, _ = sealed_native()
        vae = FakeVAE()
        image = anchor()
        for frames in (49, 97, 121):
            for stage in ('A', 'B'):
                entry = precompute(vae, image, stage, frames)
                latent = stage_latent(stage, frames)
                native = node.execute(vae=vae, image=image, latent=latent, strength=1.0, bypass=False).result[0]
                replay = pg.ReplayVAE(torch, vae, entry)
                pre = node.execute(vae=replay, image=image, latent=latent, strength=1.0, bypass=False).result[0]
                self.assertTrue(replay.used)
                self.assertEqual(tsha(native['samples']), tsha(pre['samples']), (frames, stage))
                self.assertEqual(tsha(native['noise_mask']), tsha(pre['noise_mask']), (frames, stage))
                self.assertTrue(pg.bitwise_equal(torch, native['samples'], pre['samples']))
                self.assertEqual(entry.record['pixels_shape'], [1, 128, 128, 3] if stage == 'A' else [1, 256, 256, 3])

    def test_replay_refuses_other_pixels_a_second_encode_and_a_changed_encode(self):
        node, _ = sealed_native()
        vae = FakeVAE()
        image = anchor()
        entry = precompute(vae, image, 'B', 97)
        other = image.clone()
        other[0, 9, 9, 1] += 0.25
        with self.assertRaises(pg.PrecomputeRefusal):
            node.execute(vae=pg.ReplayVAE(torch, vae, entry), image=other, latent=stage_latent('B', 97),
                         strength=1.0, bypass=False)
        replay = pg.ReplayVAE(torch, vae, entry)
        replay.encode(image[:, :, :, :3])
        with self.assertRaises(pg.PrecomputeRefusal):
            replay.encode(image[:, :, :, :3])
        entry.t[0, 0, 0, 0, 0] += 1.0
        with self.assertRaises(pg.PrecomputeRefusal):
            pg.ReplayVAE(torch, vae, entry).encode(image[:, :, :, :3])
        capture = pg.CaptureVAE(torch, vae)
        capture.encode(image)
        with self.assertRaises(pg.PrecomputeRefusal):
            capture.encode(image)


class SafetyStub:
    def __init__(self):
        self.failed, self.closed = None, False
        self.expected_residence = {r: hashlib.sha256(r.encode()).hexdigest() for r in ROLES}
        self.objects = {r: types.SimpleNamespace(name=r) for r in ROLES}
        for role in ('video_vae', 'audio_vae'):
            setattr(self.objects[role], pg.SAFETY_ATTRIBUTE, self)


class Snapshot(unittest.TestCase):
    def make(self, **over):
        c = over.pop('controller', SafetyStub())
        state = dict(phase=True, fault=False, free=10 * GIB, counters={'allocated': 1, 'reserved': 2, 'peak': 3},
                     rows={r: [r] for r in pg.XPU3_ROLES}, synced=[])
        state.update(over)
        snap = pg.Xpu3Snapshot(controller=c, phase_ok=lambda: state['phase'], fault=lambda: state['fault'],
                               synchronize=lambda card: state['synced'].append(card),
                               free_bytes=lambda card: state['free'], counters=lambda card: dict(state['counters']),
                               rows=lambda role: state['rows'][role],
                               fingerprint=lambda rows: hashlib.sha256(rows[0].encode()).hexdigest())
        return snap, c, state

    def test_passes_and_synchronises_only_xpu3(self):
        snap, c, state = self.make()
        before = snap.take('precompute-B-before', pg.PRE_FLOOR)
        after = snap.take('precompute-B-after', pg.POST_FLOOR)
        self.assertTrue(before['admitted'] and after['admitted'])
        self.assertEqual(state['synced'], ['xpu:3', 'xpu:3'])
        self.assertEqual(before['checks'], ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8'])
        self.assertEqual(sorted(before['residence']), sorted(pg.XPU3_ROLES))
        self.assertEqual({r for r, d in ROLES.items() if d == 'xpu:3'}, set(pg.XPU3_ROLES))

    def refuse(self, check, **over):
        snap, c, state = self.make(**over)
        with self.assertRaises(pg.PrecomputeRefusal) as ctx:
            snap.take('precompute-A-before', pg.PRE_FLOOR)
        self.assertTrue(str(ctx.exception).startswith(check), str(ctx.exception))

    def test_each_check_refuses(self):
        failed = SafetyStub(); failed.failed = 'x'
        closed = SafetyStub(); closed.closed = True
        self.refuse('P1', controller=failed)
        self.refuse('P1', controller=closed)
        self.refuse('P2', phase=False)
        self.refuse('P3', fault=True)
        self.refuse('P5', free=9 * GIB - 1)
        self.refuse('P5', free=True)
        self.refuse('P6', counters={'allocated': 3, 'reserved': 2, 'peak': 3})
        self.refuse('P6', counters={'allocated': 1, 'reserved': 2, 'peak': 0})
        self.refuse('P6', counters={'allocated': -1, 'reserved': 2, 'peak': 3})
        for role in pg.XPU3_ROLES:
            rows = {r: [r] for r in pg.XPU3_ROLES}
            rows[role] = [role + '-moved']
            self.refuse('P7', rows=rows)
        unbound = SafetyStub()
        setattr(unbound.objects['video_vae'], pg.SAFETY_ATTRIBUTE, None)
        self.refuse('P8', controller=unbound)
        snap, c, state = self.make(free=3 * GIB)
        self.assertTrue(snap.take('precompute-A-after', pg.POST_FLOOR)['admitted'])   # the 2 GiB post floor
        with self.assertRaises(pg.PrecomputeRefusal):
            snap.take('precompute-A-before', pg.PRE_FLOOR)

    def test_checks_table_names_every_check(self):
        self.assertEqual(sorted(pg.CHECKS), ['E1', 'E2', 'E3', 'E4', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8'])
        self.assertEqual((pg.PRE_FLOOR, pg.POST_FLOOR), (9 * GIB, 2 * GIB))


class Store(unittest.TestCase):
    def test_reserve_supersede_cancel_fail_take(self):
        store = pg.PrecomputeStore()
        a, b = store.reserve('1' * 64, ['A', 'B'], 's1')
        self.assertIs(store.lookup('1' * 64, 'A'), a)
        self.assertIsNone(store.lookup('2' * 64, 'A'))
        self.assertTrue(store.start(a))
        self.assertFalse(store.start(a))
        store.finish(a, torch.zeros(1), {'t_sha256': 'x'})
        got, waited = store.take(a, 's2', 1.0)
        self.assertIs(got, a)
        with self.assertRaises(pg.PrecomputeRefusal):
            store.take(a, 's2', 1.0)                       # consumed once
        self.assertTrue(store.cancel(b, 'reset successor'))
        self.assertEqual(store.take(b, 's2', 1.0)[0], None)
        c, = store.reserve('2' * 64, ['B'], 's2')           # a newer anchor supersedes nothing pending here
        d, = store.reserve('3' * 64, ['B'], 's3')
        self.assertEqual(c.state, 'superseded')
        self.assertEqual(store.take(c, 's3', 1.0)[0], None)
        store.start(d)
        store.fail(d, RuntimeError('boom'))
        with self.assertRaises(pg.PrecomputeRefusal):
            store.take(d, 's4', 1.0)
        e, = store.reserve('4' * 64, ['A'], 's4')
        started = time.monotonic()
        with self.assertRaises(pg.PrecomputeRefusal):
            store.take(e, 's5', 0.1)                      # never computed: the bound refuses
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(store.summary()['anchor_sha256'], '4' * 64)

    def test_waiter_is_released_by_the_decode_thread(self):
        store = pg.PrecomputeStore()
        entry, = store.reserve('5' * 64, ['B'], 's1')
        result = {}
        th = threading.Thread(target=lambda: result.update(got=store.take(entry, 's2', 5.0)))
        th.start()
        time.sleep(0.05)
        store.start(entry)
        store.finish(entry, torch.ones(1), {'t_sha256': 'y'})
        th.join(5)
        self.assertIs(result['got'][0], entry)


class NoCheckWeakened(unittest.TestCase):
    """The real CandidateSafety + ConditioningStageGuard: native and precomputed modes take the same snapshots."""
    FOUR_CARD_CHECKS = {
        'require_phase (authority phase, active request, adapter not failed, fault observer)':
            'request before/after and each stage-A/B conditioning before/after snapshot: prompt thread, unchanged',
        'synchronize xpu:0..3': 'same four-card points (unchanged); the decode-thread encode adds a sync of xpu:3',
        'inspect: node bindings, layout, host identity, 48-route inventory, W1 B1, text capture, window':
            'same four-card points (unchanged)',
        'residence/ownership of all seven roles': 'same four-card points; xpu:3 roles also in the encode snapshot (P7)',
        'VAE safety binding': 'same four-card points; also P8',
        'physical free floors 8/8/2/9 GiB before, 2 GiB after, every card':
            'same four-card points; xpu:3 9/2 GiB also around the encode (P5)',
        'allocation counters valid, every card': 'same four-card points; xpu:3 also P6'}

    def setUp(self):
        import conditioning_guard
        self.cg = conditioning_guard

    def controller(self, log):
        objects = {role: types.SimpleNamespace(name=role) for role in ROLES}
        expected = {role: hashlib.sha256(role.encode()).hexdigest() for role in ROLES}
        free = {'xpu:0': 9 * GIB, 'xpu:1': 9 * GIB, 'xpu:2': 3 * GIB, 'xpu:3': 10 * GIB}

        def inspect(objs):
            return {'plan_sha256': 'a' * 64, 'runtime_sha256': 'b' * 64, 'phase': 'candidate-stream', 'fault': False,
                    'text_graphs_captured': True, 'window_qualified': True, 'decoder_replicas': 0,
                    'sampler_routes': 48, 'route_inventory': {'passed': True, 'routes': 48},
                    'residence': {r: {'object_id': id(objects[r]), 'device': d, 'dtype': 'torch.bfloat16',
                                      'fully_resident': True, 'ownership_sha256': expected[r]} for r, d in ROLES.items()},
                    'physical_free_bytes': dict(free), 'peaks': {c: {'allocated': 1, 'reserved': 2, 'peak': 3}
                                                                 for c in CARDS}}
        ctl = cs.CandidateSafety(plan_sha256='a' * 64, runtime_sha256='b' * 64, objects=objects,
                                 expected_residence=expected, synchronize=lambda card: log.append(card),
                                 inspect=inspect, require_phase=lambda: None)
        encoder = object()
        ctl.objects['video_vae'].first_stage_model = types.SimpleNamespace(encoder=encoder)
        return ctl, encoder

    def run_request(self, mode):
        node, NodeOutput = sealed_native()
        log = []
        ctl, encoder = self.controller(log)
        vae = ctl.objects['video_vae']
        fake = FakeVAE()
        vae.downscale_index_formula = fake.downscale_index_formula
        vae.encode = fake.encode

        def meta(t):
            return {'object_id': id(t), 'storage_id': int(t.untyped_storage().data_ptr()), 'shape': list(t.shape),
                    'dtype': str(t.dtype), 'device': str(t.device), 'contiguous': t.is_contiguous()}
        guard = self.cg.ConditioningStageGuard(
            controller=ctl, tensor_metadata=meta,
            inspect_anchor=lambda img: {'sha256': tsha(img), 'finite': bool(torch.isfinite(img).all())},
            inspect_encoder_cache=lambda enc, tid: {'source_sha256': self.cg.ENCODER_SHA256, 'encoder_id': id(enc),
                                                    'thread_ident': tid, 'entry_count': 0, 'foreign_entry_count': 0},
            unwrap_output=lambda result: result.result[0])
        image = anchor(11)
        entries = {s: precompute(fake, image, s, 49) for s in ('A', 'B')} if mode == 'precomputed' else {}

        def native_call(stage):
            def call(vae, image, latent, strength, bypass):
                use = pg.ReplayVAE(torch, vae, entries[stage]) if mode == 'precomputed' else vae
                return node.execute(vae=use, image=image, latent=latent, strength=strength, bypass=bypass)
            return call
        ctl.before('stream130-s00000001')
        guard.begin_request('stream130-s00000001', anchor=image, expected_anchor_sha256=tsha(image))
        outs = []
        for stage, seed in (('A', 1), ('B', 2)):
            latent = {'samples': stage_latent(stage, 49, seed)['samples'].contiguous()}
            result = guard.run_stage(stage, request_id='stream130-s00000001', vae=vae, latent=latent,
                                     native_call=native_call(stage))
            outs.append({k: tsha(v) for k, v in result.result[0].items()})
        guard.finish_request('stream130-s00000001')
        ctl.after()
        snaps = [(r['event'], r['required_physical_free_bytes']) for r in ctl.drain() if 'snapshot' in r]
        rows = [{k: (v if k not in ('controller_receipt_start', 'controller_receipt_end') else None)
                 for k, v in r.items() if k not in ('before', 'after', 'input', 'output', 'noise_mask', 'anchor_sha256',
                                                    'cache_before', 'cache_after', 'cache_after_before_snapshot',
                                                    'cache_after_after_snapshot')} for r in guard.receipts]
        return snaps, log, rows, outs, fake.calls

    def test_native_and_precomputed_modes_take_identical_four_card_snapshots(self):
        native = self.run_request('native')
        pre = self.run_request('precomputed')
        self.assertEqual(native[0], pre[0])                       # events and required floors, in order
        self.assertEqual([e for e, _ in native[0]], ['before', 'conditioning-A-before', 'conditioning-A-after',
                                                     'conditioning-B-before', 'conditioning-B-after', 'after'])
        self.assertEqual(native[1], pre[1])                       # the cards synchronised at each snapshot
        self.assertEqual(native[1], list(CARDS) * 6)
        self.assertEqual(native[2], pre[2])                       # the guard's receipts (stages, completion)
        self.assertEqual(native[3], pre[3])                       # outputs byte-identical
        self.assertEqual(len(native[4]), 2)                       # the native mode encodes twice on this thread
        self.assertEqual(len(pre[4]), 2)                          # the precompute encoded (the replay did not)
        floors = dict(native[0])
        self.assertEqual(floors['conditioning-A-before'], dict(zip(CARDS, (8 * GIB, 8 * GIB, 2 * GIB, 9 * GIB))))
        self.assertEqual(floors['conditioning-B-after'], {c: 2 * GIB for c in CARDS})

    def test_every_four_card_check_still_runs_somewhere(self):
        self.assertEqual(len(self.FOUR_CARD_CHECKS), 7)
        source = (HERE / 'candidate_safety.py').read_text()
        for needle in ('self.require_phase()', 'self.synchronize(card)', 'self.inspect(dict(self.objects))',
                       "'Residence/ownership changed: '", "'VAE safety binding was removed or replaced'",
                       "'Physical free-memory admission refused", "'Invalid allocation/peak readings: '"):
            self.assertIn(needle, source)
        self.assertEqual(hashlib.sha256((HERE / 'candidate_safety.py').read_bytes()).hexdigest(),
                         self.cg.CANDIDATE_SHA256)               # the controller itself is unchanged from 116b

    def test_runtime_routes_every_precomputed_stage_through_the_guard_under_the_encoder_lock(self):
        tree = ast.parse((HERE / 'integration.py').read_text())
        fn = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

        def calls(node, attr):
            return [c for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                    and c.func.attr == attr]

        def under_encoder_lock(node, attr):
            for w in [w for w in ast.walk(node) if isinstance(w, ast.With)]:
                if any(isinstance(i.context_expr, ast.Attribute) and i.context_expr.attr == 'encoder_lock'
                       for i in w.items) and any(calls(s, attr) for s in w.body):
                    return True
            return False
        self.assertEqual(len(calls(fn['condition'], 'run_stage')), 1)
        self.assertTrue(under_encoder_lock(fn['condition'], 'run_stage'))
        self.assertTrue(under_encoder_lock(fn['provide_anchor'], 'begin_request'))
        self.assertTrue(under_encoder_lock(fn['_after_chunk'], 'finish_request'))
        self.assertTrue(under_encoder_lock(fn['_precompute'], 'native_call'))
        self.assertTrue(under_encoder_lock(fn['_precompute'], 'take'))          # both xpu:3 snapshots inside
        self.assertEqual(len(calls(fn['_precompute'], 'take')), 2)
        self.assertEqual(len(calls(fn['_precomputed_call'], 'native_call')), 2)  # replay, and the dual native call
        self.assertEqual(len(calls(fn['_precompute'], 'inspect_encoder_cache')), 1)


if __name__ == '__main__':
    unittest.main()
