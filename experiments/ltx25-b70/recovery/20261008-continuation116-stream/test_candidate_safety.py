"""CPU tests: candidate safety contract (pinned 48-route inventory, owners, floors)."""
import copy
import hashlib
import subprocess
import sys
import types
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SEALED = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-native-111/source/scripts')
sys.path.insert(0, str(HERE))
sys.path.append(str(SEALED))   # sealed native_safety / native_adapter only; -B keeps it untouched
import candidate_safety as cs  # noqa: E402
from native_safety import GIB, SafetyRefusal, ROLES, CARDS  # noqa: E402

OWNER = 1234


def registry_row(i, pinned=True, threads=None, digest='d'):
    row = {'index': i, 'device': cs.ROUTE_DEVICES[i], 'primary': 'xpu:0', 'last': i == 47}
    if pinned:
        row.update(type='GraphBlockRoute', head_index=i, native_block=True, original_is_pinned=True,
                   threads={str(OWNER): 4} if threads is None else threads, signature_digest=digest)
    else:
        row.update(type='_BlockRoute')
    return row


def snapshot(pinned=True, frozen=False):
    if not pinned:
        return {'installed': False, 'install_record': None, 'gate_failed': False, 'route_objects': 0,
                'route_list_is_registry': True, 'registry': [registry_row(i, False) for i in range(48)],
                'groups': [], 'pool_owners': [], 'captures_frozen': False, 'captured_graphs': 0}
    return {'installed': True, 'gate_failed': False, 'route_objects': 48, 'route_list_is_registry': True,
            'install_record': {'model_is_primary': True, 'originals': list(range(48)), 'selection': 'all48', 'chain': 1},
            'registry': [registry_row(i) for i in range(48)],
            'groups': [['xpu:0', OWNER], ['xpu:1', OWNER]], 'pool_owners': [['xpu:0', OWNER], ['xpu:1', OWNER]],
            'captures_frozen': frozen, 'captured_graphs': 192}


def expected(state='pinned', frozen=False, sigs=None):
    return {'state': state, 'owner_thread': OWNER, 'frozen': frozen, 'frozen_signatures': sigs}


class RouteInventory(unittest.TestCase):
    def test_absent_and_pinned_pass(self):
        self.assertEqual(cs.check_route_inventory(snapshot(False), expected('absent'))['routes'], 0)
        verdict = cs.check_route_inventory(snapshot(), expected())
        self.assertEqual((verdict['routes'], verdict['signatures_per_route']), (48, 4))

    def test_installing_accepts_either(self):
        self.assertEqual(cs.check_route_inventory(snapshot(False), expected('installing'))['state'], 'absent')
        self.assertEqual(cs.check_route_inventory(snapshot(), expected('installing'))['state'], 'pinned')

    def refuse(self, snap, exp=None):
        with self.assertRaises(SafetyRefusal):
            cs.check_route_inventory(snap, exp or expected())

    def test_refusals(self):
        s = snapshot(); s['registry'][5]['threads'] = {str(OWNER): 4, '999': 4}; self.refuse(s)
        s = snapshot(); s['registry'][5]['threads'] = {str(OWNER): 9}
        for r in s['registry']:
            r['threads'] = {str(OWNER): 9}
        self.refuse(s)
        s = snapshot(); s['registry'][7]['threads'] = {str(OWNER): 3}; self.refuse(s)
        s = snapshot(); s['registry'][30]['device'] = 'xpu:0'; self.refuse(s)
        s = snapshot(); s['registry'][22]['device'] = 'xpu:1'; self.refuse(s)
        s = snapshot(); s['registry'][47]['last'] = False; self.refuse(s)
        s = snapshot(); s['registry'][3]['original_is_pinned'] = False; self.refuse(s)
        s = snapshot(); s['registry'][3]['native_block'] = False; self.refuse(s)
        s = snapshot(); s['route_objects'] = 49; self.refuse(s)
        s = snapshot(); s['route_list_is_registry'] = False; self.refuse(s)
        s = snapshot(); s['install_record']['chain'] = 4; self.refuse(s)
        s = snapshot(); s['install_record']['selection'] = 'single24'; self.refuse(s)
        s = snapshot(); s['groups'].append(['xpu:2', OWNER]); self.refuse(s)
        s = snapshot(); s['pool_owners'].append(['xpu:0', 999]); self.refuse(s)
        s = snapshot(); s['gate_failed'] = True; self.refuse(s)
        s = snapshot(); s['registry'][0]['type'] = 'PassthroughRoute'; self.refuse(s)
        self.refuse(snapshot(), expected('absent'))
        self.refuse(snapshot(False), expected('pinned'))

    def test_freeze(self):
        sigs = {i: 'd' for i in range(48)}
        cs.check_route_inventory(snapshot(frozen=True), expected(frozen=True, sigs=sigs))
        self.refuse(snapshot(frozen=False), expected(frozen=True, sigs=sigs))
        self.refuse(snapshot(frozen=True), expected(frozen=False))
        s = snapshot(frozen=True); s['registry'][9]['signature_digest'] = 'new'
        self.refuse(s, expected(frozen=True, sigs=sigs))
        self.refuse(snapshot(frozen=True), expected(frozen=True, sigs=None))


class LiveSnapshot(unittest.TestCase):
    """snapshot_routes over fake objects shaped like the real gate/registry."""
    def build(self):
        class _BlockRoute:
            def __init__(self, i):
                self.device = cs.ROUTE_DEVICES[i]; self.primary = 'xpu:0'; self.last = i == 47
        class GraphBlockRoute:
            pass
        blocks = [object() for _ in range(48)]
        originals = {i: _BlockRoute(i) for i in range(48)}
        registry = types.SimpleNamespace(groups={('xpu:0', OWNER): 1, ('xpu:1', OWNER): 1})
        heads = []
        for i in range(48):
            r = GraphBlockRoute()
            r.index, r.blocks, r.original_route, r.registry = i, (blocks[i],), originals[i], registry
            r.entries = {OWNER: {('sigA',): 1, ('sigB',): 1}}
            heads.append(r)
        model = types.SimpleNamespace(
            model_options={'transformer_options': {'patches_replace': {'dit': {('double_block', i): heads[i] for i in range(48)}}}},
            model=types.SimpleNamespace(diffusion_model=types.SimpleNamespace(transformer_blocks=tuple(blocks))))
        import threading
        capture = types.SimpleNamespace(_ROUTES=list(heads), _POOL_LOCK=threading.Lock(),
                                        _POOL_OWNERS={('xpu:0', OWNER): [1], ('xpu:1', OWNER): [1]},
                                        CAPTURES_FROZEN=[False])
        gate = {'_installed': (model, originals, None, ('all48', 1)), '_failed': False}
        return capture, gate, model

    def test_snapshot_passes_contract(self):
        capture, gate, model = self.build()
        snap = cs.snapshot_routes(capture, gate, model)
        verdict = cs.check_route_inventory(snap, expected())
        self.assertEqual(verdict['signatures_per_route'], 2)
        self.assertEqual(snap['captured_graphs'], 96)

    def test_foreign_thread_entry_detected(self):
        capture, gate, model = self.build()
        capture._ROUTES[10].entries[777] = {('x',): 1}
        with self.assertRaises(SafetyRefusal):
            cs.check_route_inventory(cs.snapshot_routes(capture, gate, model), expected())


class Layout(unittest.TestCase):
    def fake(self, split=23, segments=None, devices=('xpu:0', 'xpu:1')):
        blocks = tuple(object() for _ in range(48))

        class _BlockRoute:
            def __init__(self, i):
                self.device = 'xpu:0' if i < split else 'xpu:1'; self.primary = 'xpu:0'; self.last = i == 47
        secondary = types.SimpleNamespace(load_device=devices[1], model=types.SimpleNamespace(blocks=blocks[split:]))
        identity = {'split_index': split, 'block_count': 48, 'primary': 'xpu:0', 'secondary': 'xpu:1'}
        if segments:
            identity['segments'] = segments
        diffusion = types.SimpleNamespace(_ltx_layer_shard_identity=identity, transformer_blocks=blocks,
                                          _ltx_primary_blocks=blocks[:split])
        model = types.SimpleNamespace(load_device=devices[0], model=types.SimpleNamespace(diffusion_model=diffusion),
                                      model_options={'transformer_options': {'patches_replace': {'dit': {
                                          ('double_block', i): _BlockRoute(i) for i in range(48)}}}},
                                      get_additional_models_with_key=lambda key: [secondary])
        return model, secondary

    def test_two_way_23_25(self):
        model, secondary = self.fake()
        self.assertIs(cs.candidate_layout(model, 'two-way'), secondary)

    def test_named_two_way20_28(self):
        model, secondary = self.fake(split=20, segments=[['xpu:0', 0, 20], ['xpu:1', 20, 48]])
        identity = model.model.diffusion_model._ltx_layer_shard_identity
        identity.update(split_index=None, devices=['xpu:0', 'xpu:1'])
        identity.pop('secondary')
        self.assertIs(cs.candidate_layout(model, 'two-way20-28'), secondary)
        with self.assertRaises(SafetyRefusal):
            cs.candidate_layout(model, 'two-way')
        rows = [dict(registry_row(i), device=cs.route_devices('two-way20-28')[i]) for i in range(48)]
        snap = dict(snapshot(), registry=rows)
        cs.check_route_inventory(snap, dict(expected(), placement='two-way20-28'))
        with self.assertRaises(SafetyRefusal):
            cs.check_route_inventory(snap, dict(expected(), placement='two-way'))

    def test_refuses_other_placements(self):
        model, _ = self.fake()
        with self.assertRaises(SafetyRefusal):
            cs.candidate_layout(model, 'two-way20-28')
        with self.assertRaises(SafetyRefusal):
            cs.candidate_layout(model, 'shard3-c')
        model, _ = self.fake(split=20)
        with self.assertRaises(SafetyRefusal):
            cs.candidate_layout(model, 'two-way')
        model, _ = self.fake(segments=[['xpu:0', 0, 23], ['xpu:1', 23, 48]])
        with self.assertRaises(SafetyRefusal):
            cs.candidate_layout(model, 'two-way')


class Controller(unittest.TestCase):
    def make(self, free=None, inventory=None, phase='candidate-stream', reported=None):
        objects = {role: types.SimpleNamespace(name=role) for role in ROLES}
        expected_residence = {role: hashlib.sha256(role.encode()).hexdigest() for role in ROLES}
        free = free or {'xpu:0': 9 * GIB, 'xpu:1': 9 * GIB, 'xpu:2': 3 * GIB, 'xpu:3': 10 * GIB}
        inventory = inventory or {'passed': True, 'routes': 48}

        def inspect(objs):
            return {'plan_sha256': 'a' * 64, 'runtime_sha256': 'b' * 64, 'phase': phase, 'fault': False,
                    'text_graphs_captured': True, 'window_qualified': True, 'decoder_replicas': 0,
                    'sampler_routes': inventory.get('routes') if reported is None else reported, 'route_inventory': inventory,
                    'residence': {r: {'object_id': id(objects[r]), 'device': d, 'dtype': 'torch.bfloat16',
                                      'fully_resident': True, 'ownership_sha256': expected_residence[r]}
                                  for r, d in ROLES.items()},
                    'physical_free_bytes': dict(free),
                    'peaks': {c: {'allocated': 1, 'reserved': 2, 'peak': 3} for c in CARDS}}
        return cs.CandidateSafety(plan_sha256='a' * 64, runtime_sha256='b' * 64, objects=objects,
                                  expected_residence=expected_residence, synchronize=lambda card: None,
                                  inspect=inspect, require_phase=lambda: None)

    def test_admits_pinned_routes_with_floors(self):
        controller = self.make()
        receipt = controller.before('stream116-s00000000')
        self.assertTrue(receipt['admitted'])
        self.assertTrue(controller.after()['admitted'])
        self.assertEqual(len(controller.drain()), 2)
        self.assertEqual(controller.receipts, [])

    def test_floor_refusal_latches(self):
        controller = self.make(free={'xpu:0': int(7.8 * GIB), 'xpu:1': 9 * GIB, 'xpu:2': 3 * GIB, 'xpu:3': 10 * GIB})
        with self.assertRaises(SafetyRefusal):
            controller.before('stream116-s00000000')
        with self.assertRaises(SafetyRefusal):
            controller.before('stream116-s00000001')

    def test_inventory_and_phase_refusals(self):
        for kwargs in ({'inventory': {'passed': False, 'routes': 48}}, {'reported': 0},
                       {'phase': 'native-reference'}):
            with self.assertRaises(SafetyRefusal):
                self.make(**kwargs).before('x')

    def test_conditioning_guard_accepts_candidate_controller(self):
        import conditioning_guard
        controller = self.make()
        encoder = object()
        controller.objects['video_vae'].first_stage_model = types.SimpleNamespace(encoder=encoder)
        guard = conditioning_guard.ConditioningStageGuard(controller=controller, tensor_metadata=lambda t: {},
                                                          inspect_anchor=lambda t: {}, inspect_encoder_cache=lambda e, t: {},
                                                          unwrap_output=lambda r: r)
        self.assertIs(guard.encoder, encoder)


class DerivedSources(unittest.TestCase):
    def test_derived_helpers_match_and_pin_candidate(self):
        result = subprocess.run([sys.executable, '-B', str(HERE / 'derive_from_111.py')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        import conditioning_guard
        self.assertEqual(conditioning_guard.CANDIDATE_SHA256,
                         hashlib.sha256((HERE / 'candidate_safety.py').read_bytes()).hexdigest())

    def test_guard_geometry_follows_launch_frames(self):
        for frames, mask in (('49', [1, 1, 7, 1, 1]), ('97', [1, 1, 13, 1, 1])):
            out = subprocess.run([sys.executable, '-B', '-c',
                                  'import sys; sys.path[:0]=[%r, %r]; import conditioning_guard as g, continuation_anchor as a;'
                                  'print(g.MASK_SHAPE, g.SHAPES["A"], a.FRAME_INDEX, a.SHAPES["images"][0])'
                                  % (str(HERE), str(SEALED))],
                                 capture_output=True, text=True, env={'LTX_STREAM_FRAMES': frames, 'PATH': '/usr/bin'})
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn(str(mask), out.stdout)
            self.assertIn(' %d %s' % (int(frames) - 1, frames), out.stdout)


if __name__ == '__main__':
    unittest.main()
