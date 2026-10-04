#!/usr/bin/env python3
"""CPU-only tests for packet 94 (multi-segment transformer placement). No XPU, no server.

1. Segment routing for arbitrary splits: every block runs exactly once, in order, on
   its segment's device; each boundary is one cross-card move; the last block moves
   the state back to the primary. Invalid placements are refused.
2. Multi-segment install on a tiny CPU model: disjoint ownership covering every
   tensor, one shard patcher per extra segment, routes and arithmetic exact,
   verify_placement walks every shard, rollback on failure.
3. The two-way path is the previous code: install(), _BlockRoute, _move and the
   transfer helpers are byte-identical to the committed packet-93c version, and
   the graph adapter pins the new shard source.
4. Memory floor: memory_plan and the freeze admission refuse below 2 GiB.
5. Capture refusal in timed arms: refuse_if_frozen and its call before capture.
6. Best-candidate rule (decide-94.py) and the manifest/allowlist agreement.
"""
import ast
import importlib.util
import json
import random
import subprocess
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LANE = HERE.parent
REPO = LANE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(1, '/home/steve/src/ComfyUI-ltx25-baseline')
sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram']
import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
import torch  # noqa: E402
from torch import nn  # noqa: E402
from comfy.model_patcher import ModelPatcher  # noqa: E402
import ltx_layer_shard as shard  # noqa: E402

results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' ' + ' | '.join(traceback.format_exc().splitlines()[-3:])))


def raises(fn, text=None):
    try:
        fn()
    except Exception as error:  # noqa: BLE001
        assert text is None or text in str(error), (text, str(error))
        return
    raise AssertionError('expected a refusal')


def random_split(rng, n=48):
    k = rng.randint(2, 4)
    cuts = sorted(rng.sample(range(1, n), k - 1))
    bounds = [0] + cuts + [n]
    devices = ['xpu:%d' % i for i in range(4)]
    return tuple((devices[i], bounds[i], bounds[i + 1]) for i in range(k))


def simulate(plan):
    """Walk the forward as the routes do: move to the block's device, run, last block back."""
    where, order, moves = plan[0][1], [], 0
    for i, (device, primary, last) in enumerate(plan):
        if where != device:
            moves += 1
            where = device
        order.append((i, where))
        if last:
            if where != primary:
                moves += 1
            where = primary
    return order, moves, where


def routing_case():
    rng = random.Random(94)
    for name, segs in shard.PLACEMENTS.items():
        rng_cases = [segs] + [random_split(rng) for _ in range(200)]
        for segments in rng_cases:
            plan = shard.segment_plan(segments)
            order, moves, end = simulate(plan)
            assert [i for i, _ in order] == list(range(48)), 'blocks out of order or repeated'
            for i, dev in order:
                expect = next(d for d, a, b in segments if a <= i < b)
                assert dev == expect, (i, dev, expect)
            assert moves == len(segments), (segments, moves)   # k-1 boundaries + the move back
            assert end == 'xpu:0' and sum(1 for p in plan if p[2]) == 1 and plan[-1][2]
    bad = [((('xpu:0', 0, 20), ('xpu:1', 21, 48)), 'contiguous'),
           ((('xpu:0', 0, 20), ('xpu:1', 19, 48)), 'contiguous'),
           ((('xpu:0', 0, 0), ('xpu:1', 0, 48)), 'non-empty'),
           ((('xpu:0', 0, 20), ('xpu:1', 20, 47)), 'cover'),
           ((('xpu:0', 0, 48),), 'two segments'),
           ((('xpu:0', 0, 20), ('xpu:0', 20, 48)), 'own device'),
           ((), 'at least one')]
    for segments, text in bad:
        raises(lambda s=segments: shard.segment_plan(s), text)
    for name in ('two-way', 'unknown'):
        raises(lambda n=name: shard.apply_layer_segments(None, n), 'Unknown multi-segment')


case('routing: arbitrary splits run every block once, in order, on its device; one move per boundary',
     routing_case)


class TinyDiffusion(nn.Module):
    def __init__(self, n=6):
        super().__init__()
        self.transformer_blocks = nn.ModuleList([nn.Linear(3, 3, dtype=torch.bfloat16) for _ in range(n)])
        self.proj = nn.Linear(3, 3, dtype=torch.bfloat16)


class TinyModel(nn.Module):
    def __init__(self, n=6):
        super().__init__()
        self.diffusion_model = TinyDiffusion(n)

    def get_dtype(self):
        return torch.bfloat16


def install_case():
    patcher = ModelPatcher(TinyModel(), torch.device('cpu'), torch.device('cpu'))
    original = {id(t): t.detach().clone() for t in shard._tensors(patcher.model)}
    blocks = tuple(patcher.model.diffusion_model.transformer_blocks)
    segments = (('cpu', 0, 2), ('cpu', 2, 3), ('cpu', 3, 6))
    shard._install_segments(shard.LTXLayerShardedPatcher, patcher, segments, allow_same_device=True)
    shards = patcher.get_additional_models_with_key(shard.KEY)
    assert len(shards) == 2 and type(patcher) is shard.LTXLayerShardedPatcher
    owned = [shard._tensors(patcher.model)] + [shard._tensors(s.model) for s in shards]
    ids = [id(t) for g in owned for t in g]
    assert len(ids) == len(set(ids)) and set(ids) == set(original), 'ownership not a partition'
    assert [len(s.model.blocks) for s in shards] == [1, 3]
    assert tuple(patcher.model.diffusion_model.transformer_blocks) == blocks
    ident = patcher.ltx_layer_shard_report
    assert ident['segments'] == [['cpu', 0, 2], ['cpu', 2, 3], ['cpu', 3, 6]] and ident['split_index'] is None
    assert sum(ident['segment_bytes']) == ident['original_bytes']
    routes = patcher.model_options['transformer_options']['patches_replace']['dit']
    assert [routes[('double_block', i)].last for i in range(6)] == [False] * 5 + [True]
    assert all(type(routes[('double_block', i)]) is shard._BlockRoute for i in range(6))
    patcher.verify_placement()
    x = torch.ones((1, 3), dtype=torch.bfloat16)
    expected = x
    for b in blocks:
        expected = b(expected)

    def execute(*args):
        actual = x
        for i, b in enumerate(blocks):
            result = routes[('double_block', i)](
                {'img': (actual, actual), 'transformer_options': args[5]},
                {'original_block': lambda a, bb=b: {'img': (bb(a['img'][0]), a['img'][1])}})
            actual = result['img'][0]
        return actual

    assert torch.equal(shard._forward_transfers(execute, None, None, None, None, None, {}), expected)
    shards[1].load_device = torch.device('meta')
    raises(patcher.verify_placement, 'not fully resident')
    raises(lambda: shard._install_segments(shard.LTXLayerShardedPatcher, patcher, segments, True), 'already')
    # rollback: a placement that fails validation leaves the fresh patcher untouched
    fresh = ModelPatcher(TinyModel(), torch.device('cpu'), torch.device('cpu'))
    raises(lambda: shard._install_segments(shard.LTXLayerShardedPatcher, fresh,
                                           (('cpu', 0, 2), ('cpu', 3, 6)), True), 'contiguous')
    assert type(fresh) is ModelPatcher and isinstance(fresh.model.diffusion_model.transformer_blocks, nn.ModuleList)
    assert not fresh.additional_models


case('install: one shard per extra segment, partitioned ownership, exact arithmetic, verify walks all',
     install_case)


def two_way_unchanged_case():
    old = subprocess.run(['git', '-C', str(REPO), 'show',
                          'ea72477c3:experiments/ltx25-b70/scripts/ltx_layer_shard.py'],
                         capture_output=True, text=True, check=True).stdout
    new = (HERE / 'ltx_layer_shard.py').read_text()

    def defs(text):
        tree = ast.parse(text)
        out = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                out[node.name] = ast.get_source_segment(text, node)
        return out

    a, b = defs(old), defs(new)
    for name in ('install', '_BlockRoute', '_move', '_forward_transfers', 'apply_layer_shard', '_Shard',
                 '_tensors', '_bytes', 'clone', 'deepclone_multigpu'):
        assert a[name] == b[name], 'two-way code changed: ' + name
    assert "DECLARED_SPLIT_INDEX = 23" in new
    # verify_placement: same checks; for two-way it walks the one shard as before
    p = ModelPatcher(TinyModel(4), torch.device('cpu'), torch.device('cpu'))
    shard.LTXLayerShardedPatcher.install(p, torch.device('cpu'), torch.device('cpu'), 2)
    assert len(p.get_additional_models_with_key(shard.KEY)) == 1
    p.verify_placement()
    gc = (HERE / 'ltx_graph_capture.py').read_text()
    import hashlib
    assert "SHARD_SOURCE_SHA256 = '%s'" % hashlib.sha256((HERE / 'ltx_layer_shard.py').read_bytes()).hexdigest() in gc
    res = (HERE / 'host_embedding_resident_node.py').read_text()
    assert ("if SAMPLER_PLACEMENT == 'two-way':\n                    model = apply_layer_shard(model, "
            "secondary_device='xpu:1', split_index=DECLARED_SPLIT_INDEX)") in res
    assert "SAMPLER_PLACEMENT = _os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way')" in res
    smp = (HERE / 'pipeline_sampler_node.py').read_text()
    assert "return list(identity.get('devices') or []) if identity.get('segments') else []" in smp


case('two-way: install/_BlockRoute/_move/transfers byte-identical to 93c; default placement two-way',
     two_way_unchanged_case)


def memory_case():
    free = {'xpu:0': 3.4, 'xpu:1': 3.9, 'xpu:2': 10.05, 'xpu:3': 14.04}
    # free_gib here = free with the two-way blocks REMOVED from xpu:0/1 (caller's job)
    two_way_freed = {'xpu:0': free['xpu:0'] + 23 * 0.97, 'xpu:1': free['xpu:1'] + 25 * 0.97,
                     'xpu:2': free['xpu:2'], 'xpu:3': free['xpu:3']}
    left = shard.memory_plan(shard.PLACEMENTS['shard4-a'], two_way_freed)
    assert all(v >= 2.0 for v in left.values()) and abs(left['xpu:2'] - (10.05 - 8 * 0.97)) < 1e-9, left
    raises(lambda: shard.memory_plan((('xpu:0', 0, 18), ('xpu:1', 18, 30), ('xpu:2', 30, 48)), two_way_freed),
           'less than 2.0 GiB')
    spec = importlib.util.spec_from_file_location('psn', HERE / 'pipeline_sampler_node.py')
    src = (HERE / 'pipeline_sampler_node.py').read_text()
    ns = {}
    start = src.index('MEMORY_FLOOR_GIB = 2.0')
    end = src.index('class LTXSamplerCaptureFreeze')
    exec(compile(src[start:end], 'psn', 'exec'), ns)
    fv = ns['freeze_verdict']
    G = 2**30
    ok = {'xpu:0': int(2.5 * G), 'xpu:1': 2 * G, 'xpu:2': 5 * G, 'xpu:3': 9 * G}
    assert fv(ok, 0) == (True, 'frozen')
    assert fv(dict(ok, **{'xpu:1': 2 * G - 1}), 0) == (False, 'memory-floor')   # raw bytes, no rounding
    assert round((2 * G - 1) / G, 3) == 2.0, 'the 94 rounding would have admitted this'
    assert fv(dict(ok, **{'xpu:0': None}), 0) == (False, 'memory-floor')
    assert fv(ok, 2) == (False, 'pipeline-busy')
    assert fv(ok, 0, coverage_ok=False) == (False, 'captures-incomplete')


case('memory floor: plan and freeze admission refuse below 2 GiB free', memory_case)


def capture_refusal_case():
    import ltx_graph_capture as g
    g.CAPTURES_FROZEN[0] = False
    g.refuse_if_frozen(5)
    g.CAPTURES_FROZEN[0] = True
    try:
        raises(lambda: g.refuse_if_frozen(5), 'refused before capture')
    finally:
        g.CAPTURES_FROZEN[0] = False
    src = (HERE / 'ltx_graph_capture.py').read_text()
    i_ref = src.index('            refuse_if_frozen(self.index)')
    i_lock = src.index('            CAPTURE_LOCK.acquire_exclusive()', i_ref)
    i_cap = src.index('entry = self._capture(routed, slot, key, entries)', i_ref)
    assert i_ref < i_lock < i_cap and src.count('refuse_if_frozen(self.index)') == 1


case('timed arms: a sampler capture after the freeze is refused before it starts', capture_refusal_case)


def serial_pass_case():
    # 94b: before the freeze a sampler request (and so any sampler capture) runs alone:
    # no encode/decode/sample job running, no other prompt queued; and vice versa the
    # freeze (which ends the capture window) refuses while any job is running.
    src = (HERE / 'pipeline_sampler_node.py').read_text()
    ns = {}
    exec(compile(src[src.index('MEMORY_FLOOR_GIB = 2.0'):src.index('class LTXSamplerCaptureFreeze')], 'psn', 'exec'), ns)
    sa, fv = ns['serial_admission'], ns['freeze_verdict']
    assert sa(False, 0, 0) == (True, None)
    assert sa(False, 1, 0)[0] is False and 'running' in sa(False, 1, 0)[1]      # an encode/decode job holds a card
    assert sa(False, 0, 2)[0] is False and 'queued' in sa(False, 0, 2)[1]       # lookahead would start
    assert sa(True, 3, 5) == (True, None)                                      # after the freeze: no captures at all
    assert fv({'xpu:0': 5 * 2**30}, 1)[1] == 'pipeline-busy'
    # with the real pipeline: a decode job holding its card blocks admission until it is done
    import threading
    import ltx_pipeline as p
    p.clear()
    gate = threading.Event()
    p.submit('decode', 941000, lambda: gate.wait(5))
    import time as _t
    _t.sleep(0.1)
    assert sa(False, p.busy(), 0)[0] is False
    gate.set()
    p.collect('decode', 941000)
    assert sa(False, p.busy(), 0)[0] is True
    p.clear()
    i_adm = src.index('admitted, why = serial_admission(')
    i_submit = src.index("out, detail = pipeline.run_behind(")
    assert i_adm < i_submit, 'serial admission must come before the sample job is submitted'
    assert 'except SerialPassRequired:\n            raise' in src


case('serial pass: no sampler capture while another job holds a card, and no freeze while one runs',
     serial_pass_case)


def coverage_case():
    import ltx_graph_capture as g

    class R:
        def __init__(self, index, entries):
            self.index, self.entries = index, entries
    a, b = 101, 202
    full = [R(i, {a: {'s1': 1, 's2': 1}, b: {'s1': 1, 's2': 1}}) for i in range(48)]
    assert g.capture_coverage([a, b], full)[0] is True
    part = list(full); part[7] = R(7, {a: {'s1': 1, 's2': 1}, b: {'s1': 1}})
    ok, d = g.capture_coverage([a, b], part)
    assert ok is False and d['incomplete_routes'] == [7]
    assert g.capture_coverage([a], full)[0] is False
    assert g.capture_coverage([a, b], [])[0] is False


case('freeze: every block signature must be captured on both sampler workers', coverage_case)


def load_freeze_case():
    # 94f: after the freeze every load call, forced or not, goes to frozen_load (no-op on
    # wholly resident models with the free memory already there, else a refusal) before
    # any branch that could reach ComfyUI's loader. The behaviour with real ComfyUI
    # bookkeeping is tested in test-packet94c-dryrun-cpu.py.
    src = (HERE / 'resident_fastpath_node.py').read_text()
    body = src[src.index('def fast_load_models_gpu'):src.index('class LTXResidentFastPath')]
    i_frozen = body.index('if _frozen():\n            return frozen_load(models, args, kwargs)')
    i_forced = body.index("if kwargs.get('force_patch_weights') or kwargs.get('force_full_load'):")
    i_orig = body.index('return _original(models, *args, **kwargs)')
    assert i_frozen < i_forced < i_orig
    fl = src[src.index('def frozen_load'):src.index('def fast_load_models_gpu')]
    assert '_original' not in fl and 'timed_load_models_gpu' not in fl, 'frozen_load must never reach the loader'
    smp = (HERE / 'pipeline_sampler_node.py').read_text()
    assert "require(report['resident_unchanged']" in smp and 'capture.LOADS_FROZEN[0] = True' in smp


case('loads: after the freeze a non-resident load is refused before the native loader (receipt)',
     load_freeze_case)


def runner_registration_case():
    sh = (HERE / 'run-campaign-94f.sh').read_text()
    body = sh[sh.index('arm() {'):sh.index('pid_is_server()')]
    assert body.index('ARMS_RUN="$ARMS_RUN $1"') < body.index('timeout $5'), 'arm registered after its client'
    assert body.count('ARMS_RUN=') == 1
    assert 'missing-markers-93b.py --root $R --run $RUN $ARMS_RUN' in sh
    old = (HERE / 'run-campaign-94.sh').read_text()
    assert 'superseded by run-campaign-94b.sh' in old and old.index('exit 8') < old.index('MODE=${1:-}')


case('runner: an arm is registered before its client starts; 94 refuses', runner_registration_case)


def decide_case():
    spec = importlib.util.spec_from_file_location('decide94', HERE / 'decide-94.py')
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    with tempfile.TemporaryDirectory() as t:
        base = Path(t)

        def put(mode, mean, exact=True):
            (base / mode).mkdir(exist_ok=True)
            tag = {'control': 'ctl', 'shard3-c': 's3c', 'shard4-a': 's4a'}[mode]
            (base / mode / ('f94-%s-timed-throughput.json' % tag)).write_text(
                json.dumps({'all_exact': exact, 'steady_mean_s': mean}))
        assert d.decide(base, 'shard3-c')[0] is False            # no control yet
        put('control', 1.39)
        put('shard3-c', 1.25)
        assert d.decide(base, 'shard3-c')[0] is True
        put('shard4-a', 1.30)
        assert d.decide(base, 'shard4-a')[0] is False            # shard3-c faster
        put('shard4-a', 1.10)
        assert d.decide(base, 'shard4-a')[0] is True
        put('shard4-a', 1.05, exact=False)
        assert d.decide(base, 'shard4-a')[0] is False            # not exact never wins
        put('shard3-c', 1.45)
        assert d.decide(base, 'shard3-c')[0] is False            # slower than control


case('best candidate: exact, faster than control and than the other candidate', decide_case)


def manifest_case():
    gen = (HERE / 'prepare-graph-capture-runtime.py').read_text()
    want = {k: [list(s) for s in v] for k, v in shard.PLACEMENTS.items()}
    lit = gen.split("'placements': ")[1].split("},\n")[0] + '}'
    assert ast.literal_eval(lit) == want, 'generator manifest placements differ from ltx_layer_shard.PLACEMENTS'
    assert ast.literal_eval(gen.split("sp['placements'] == ")[1].split(" and\n")[0]) == want
    gcn = (HERE / 'graph_capture_node.py').read_text()
    assert "names = [name for name, segs in _shard.PLACEMENTS.items()" in gcn and 'check_shard_report(' in gcn


case('allowlist: generator manifest, gate check and ltx_layer_shard.PLACEMENTS agree', manifest_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
