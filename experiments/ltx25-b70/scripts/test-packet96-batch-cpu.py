#!/usr/bin/env python3
"""CPU-only tests for packet 96 (batched sampler, LTX_SAMPLER_BATCH 1/2/4). No XPU, no server.

1. Grouping: the sampler node's batch step groups B consecutive clips into one job, for
   workers 1/2/3/4 and batches 2/4 at the timed depth (W+1)B-1 and the serial depth B-1;
   every clip is emitted exactly once, in clip order, while jobs finish out of order; jobs
   really overlap W ways; every job has B rows.
2. Fixed shape: a stream's last prompt flushes the open group with fill rows that repeat
   the last real clip; fill outputs are never emitted; a non-consecutive clip, a changed
   request signature and a reused index are refused.
3. Noise: BatchNoise over the real Noise_RandomNoise / prepare_noise gives every row
   exactly the batch-1 draw of its own seed (one batch draw would not); the batched
   ancestral sampler gives every row exactly the batch-1 default_noise_sampler sequence.
4. Stacking: on packet 72's recorded census, the real batchproof stacker
   (concurrent_cfg_node._stack_rows/_double_batch_lists) and ltx_sampler_batch's expected
   census agree; the forward guard accepts the stacked layout, refuses any unstacked
   per-row tensor and refuses rows at different timesteps (lockstep); stacked conds hold
   each clip's own text features and refuse unequal metadata.
5. Env allowlist: LTX_SAMPLER_BATCH 1/2/4 accepted, 3 and junk refused, unset = 1;
   LTX_SAMPLER_WORKERS=1 accepted.
6. Lockstep: unequal sigma schedules and rows disagreeing on an all-zero latent refuse.
7. Batch 1 unchanged: the 95 arm graphs of the built packet are byte-identical to packet
   95's; the batch-1 run_behind call is untouched; the lean memo behaves exactly like
   packet 95's on batch-1 contexts; a batch arm is refused on a batch-1 server; started
   stages still refuse a worker decrease.
8. Agreement: generator, gate, runner and client agree on arm names, depths, reference
   prompt counts and index bases (no overlap); the built packet's graphs carry them.
9. Proof arrangements: the neighbour order changes every fixture's neighbours, the slot
   order every fixture's slot (check-batch-proof-96 logic on synthetic rows); the batch-4
   reference repeats fixtures 0 and 1 in other slots.
10. Memory: worker-headroom-96 plan/live on the 95b figures; missing-markers-96 expects
   markers only for submitted batch jobs.
"""
import ast
import importlib.util
import json
import os
import random
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LANE = HERE.parent
R = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
P95 = R / 'prepared-encoder-workers-95'
P96 = R / 'prepared-encoder-batch-96'
sys.path.insert(0, str(HERE))
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' ' + ' | '.join(traceback.format_exc().splitlines()[-4:])))


def raises(fn, text=None):
    try:
        fn()
    except Exception as error:  # noqa: BLE001
        assert text is None or text in str(error), (text, str(error))
        return
    raise AssertionError('expected a refusal')


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ComfyUI (CPU) from the inherited packet tree, as test-packet95 does.
# ComfyUI tree: packet 96's copy when built (byte-identical inherited files; keeps reads off packet 95)
COMFY_SRC = str((P96 if (P96 / 'manifest.json').is_file() else P95) / 'source')
sys.path.insert(1, COMFY_SRC)
_saved = sys.argv
sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram']
import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
try:
    import torch  # noqa: E402
    import comfy.sample  # noqa: E402,F401
    import comfy.samplers  # noqa: E402
    import comfy.nested_tensor  # noqa: E402
    from comfy.k_diffusion.sampling import default_noise_sampler  # noqa: E402
    from comfy_extras.nodes_custom_sampler import Noise_RandomNoise  # noqa: E402
finally:
    sys.argv = _saved

import ltx_pipeline as p  # noqa: E402
import ltx_sampler_batch as b  # noqa: E402

stub = types.ModuleType('encoder_diagnostics')
stub._context = lambda: None
sys.modules.setdefault('encoder_diagnostics', stub)
import pipeline_sampler_node as n  # noqa: E402

NT = comfy.nested_tensor.NestedTensor


# --- 1. grouping and ordered emission through the node's batch step -------------------
def run_stream(batch, workers, depth, count, base, delays):
    p.clear()
    p.set_stage_workers('sample', 4)
    n.SAMPLER_BATCH = batch
    n._GROUPER = b.Grouper(batch)
    spans, jobs = {}, []

    def fake_sample_batch(job, lean_mode):
        t0 = time.monotonic()
        time.sleep(delays[(job['key'] - base) // batch % len(delays)])
        spans[job['key']] = (t0, time.monotonic())
        jobs.append(job)
        return {c: ('clip', c) for c, _ch in job['rows'] if c is not None}

    n.sample_batch = fake_sample_batch
    emitted = []
    node = n.LTXPipelineSampler()
    for k in range(count):
        report = {}
        out, detail = node._batch_step(report, 'pipeline-lean', base + k, depth, k == count - 1, True,
                                       {'clip': base + k}, None)
        emitted.append(detail['emitted_index'])
        if out is not None:
            assert out == ('clip', detail['emitted_index']), (out, detail)
    for _ in range(200):
        if sum(len([c for c, _ in j['rows'] if c is not None]) for j in jobs) >= count:
            break
        time.sleep(0.02)
    return emitted, spans, jobs


def grouping_case():
    random.seed(96)
    for batch in (2, 4):
        for workers in (1, 2, 3, 4):
            depth = b.timed_depth(workers, batch)
            count = depth + 6 * batch                # (W+7)B-1 prompts: ends on a partial group (the flush)
            base = 960000 + 1000 * batch + 100 * workers
            delays = [0.25, 0.03, 0.18, 0.02, 0.12, 0.05, 0.20, 0.01]
            emitted, spans, jobs = run_stream(batch, workers, depth, count, base, delays)
            assert emitted[:depth] == [-1] * depth, emitted
            assert emitted[depth:] == [base + k for k in range(count - depth)], (batch, workers, emitted)
            assert all(len(j['rows']) == batch for j in jobs)
            assert [c for j in sorted(jobs, key=lambda j: j['key']) for c, _ in j['rows'] if c is not None] == \
                [base + k for k in range(count)]
            last = max(jobs, key=lambda j: j['key'])
            assert last['fill_slots'] and all(c is None for c, _ in (last['rows'][s] for s in last['fill_slots']))
            if workers >= 2:
                conc = max(sum(1 for a, z in spans.values() if a <= t < z) for t, _ in spans.values())
                assert conc >= min(workers, 2), (batch, workers, conc)
        # serial depth: one job at a time
        emitted, spans, jobs = run_stream(batch, 4, b.serial_depth(batch), 3 * batch, 969000 + batch * 100, [0.05])
        conc = max(sum(1 for a, z in spans.values() if a <= t < z) for t, _ in spans.values())
        assert conc == 1, conc
        assert emitted[b.serial_depth(batch):] == [969000 + batch * 100 + k for k in range(2 * batch + 1)], emitted
    p.clear()


case('grouping B consecutive clips per job, workers 1-4, batches 2/4; ordered emission out of order', grouping_case)


# --- 2. fixed shape, fill and refusals --------------------------------------------------
def fill_case():
    g = b.Grouper(4)
    assert g.deposit(10, 'a', ('m', 7, 4), False) is None
    job = g.deposit(11, 'b', ('m', 7, 4), True)
    assert job['key'] == 10 and job['clips'] == [10, 11] and job['fill_slots'] == [2, 3]
    assert job['rows'] == [(10, 'a'), (11, 'b'), (None, 'b'), (None, 'b')] and job['fill_of'] == 11
    assert g.job_of(10) == 10 and g.job_of(11) == 10 and g.job_of(12) is None
    assert g.emitted(10) is False and g.emitted(11) is True
    raises(lambda: g.deposit(11, 'x', ('m', 7, 4), False), 'already deposited')   # released, still never reused
    g2 = b.Grouper(2)
    g2.deposit(20, 'a', ('m', 3, 2), False)
    raises(lambda: g2.deposit(22, 'c', ('m', 3, 2), False), 'does not follow')
    raises(lambda: g2.deposit(21, 'c', ('m', 5, 2), False), 'signature')
    g3 = b.Grouper(2)
    j = g3.deposit(30, 'only', ('m', 1, 2), True)                          # capture pass: one clip, B-1 fills
    assert j['rows'] == [(30, 'only'), (None, 'only')] and j['fill_slots'] == [1]
    raises(lambda: b.Grouper(3), 'unsupported batch')
    assert b.depth_ok(1, 2) and not b.depth_ok(2, 4) and b.depth_ok(3, 4) and not b.depth_ok(25, 2)


case('fixed batch shape: fill rows repeat the last real clip and are discarded; refusals', fill_case)


# --- 3. per-clip noise ---------------------------------------------------------------------
def noise_case():
    seeds = [42, 17, 123, 808]
    v1, a1 = torch.zeros(1, 128, 4, 8, 8, dtype=torch.bfloat16), torch.zeros(1, 8, 26, 16, dtype=torch.bfloat16)
    alone = [list(Noise_RandomNoise(s).generate_noise({'samples': NT([v1, a1])}).unbind()) for s in seeds]
    for B in (2, 4):
        lat = {'samples': NT([v1.repeat(B, 1, 1, 1, 1), a1.repeat(B, 1, 1, 1)])}
        got = b.BatchNoise([Noise_RandomNoise(s) for s in seeds[:B]], threading.Lock()).generate_noise(lat).unbind()
        for k in range(B):
            for i in range(2):
                assert torch.equal(got[i][k:k + 1].view(torch.int16), alone[k][i].view(torch.int16)), (B, k, i)
        one = Noise_RandomNoise(seeds[0]).generate_noise(lat).unbind()
        assert not torch.equal(one[0][1:2].view(torch.int16), alone[1][0].view(torch.int16))
        raises(lambda: b.BatchNoise([Noise_RandomNoise(1)] * B, threading.Lock()).generate_noise(
            {'samples': NT([v1, a1])}), 'leading dimension')
    # ancestral per-step noise
    calls = {}

    def sample_euler_ancestral(model, x, sigmas, extra_args=None, callback=None, disable=None, noise_sampler=None):
        calls['draws'] = [noise_sampler(0.5, 0.25) for _ in range(3)]
        return x

    samplers = [comfy.samplers.KSAMPLER(sample_euler_ancestral) for _ in range(4)]
    x = torch.zeros(4, 1, 36096)
    bs = b.batched_ksampler(samplers, seeds, comfy.samplers.KSAMPLER, default_noise_sampler)
    bs.sampler_function(None, x, None, extra_args={'seed': seeds[0]})
    for k, s in enumerate(seeds):
        ref = default_noise_sampler(torch.zeros(1, 1, 36096), seed=s)
        for step in range(3):
            assert torch.equal(calls['draws'][step][k:k + 1], ref(0.5, 0.25)), (k, step)
    raises(lambda: bs.sampler_function(None, x, None, extra_args={'seed': 5}), 'first row seed')

    def sample_euler(model, x, sigmas, **kw):
        return x
    raises(lambda: b.batched_ksampler([comfy.samplers.KSAMPLER(sample_euler)], [1], comfy.samplers.KSAMPLER,
                                      default_noise_sampler), 'euler_ancestral')


case('per-clip initial and ancestral noise equal the batch-1 draws of each seed', noise_case)


# --- 4. stacking against packet 72's batchproof census ----------------------------------------
def stacking_case():
    import concurrent_cfg_node as ccfg
    rec = json.loads((R / 'encoder-server-graph-capture-72/concurrent-cfg-f72-proof-01.json').read_text())
    first = rec['batch_proofs_before_this_prompt'][0]
    c1, cs = first['census_batch1'], dict(first['census_stacked'])
    # packet 72's census was taken before _double_batch_lists; its real call stacked sigmas too
    cs['args[5].sigmas'] = [2] + cs['args[5].sigmas'][1:]
    assert b.expected_stacked_census(c1, 2) == cs, (b.expected_stacked_census(c1, 2), cs)

    def build(census):
        args, kwargs = [[None, None], None, None, None, None, {}], {}
        for path, shape in census.items():
            t = torch.zeros([d for d in shape if isinstance(d, int)])
            if path.startswith('args[0]['):
                args[0][int(path[8])] = t
            elif path == 'args[1]':
                args[1] = t
            elif path == 'args[2]':
                args[2] = t
            elif path.startswith('args[5].'):
                args[5][path.split('.', 1)[1]] = t
            elif path.startswith('kwargs.'):
                kwargs[path.split('.', 1)[1]] = t
        args[5].update({'cond_or_uncond': [0], 'uuids': ['u'], 'patches_replace': {'x': torch.zeros(1)}})
        return args, kwargs
    a1, k1 = build(c1)
    stacked = ccfg._stack_rows(list(a1), list(a1))
    stacked[5] = ccfg._double_batch_lists(a1[5], a1[5])
    kst = {k: ccfg._stack_rows(v, k1[k]) for k, v in k1.items()}
    got = b.forward_census(stacked, 'args')
    got.update(b.forward_census(kst, 'kwargs'))
    want = {k: [d for d in v if isinstance(d, int)] for k, v in cs.items()}
    assert got == want, (got, want)
    assert b.census_violations(got, 2) == []
    assert b.census_violations(b.forward_census(a1, 'args'), 2)              # unstacked: refused
    # the guard at the LTXAV forward entry (timestep tuple, context as keyword)
    refusals = []
    guard = b.make_forward_guard(2, lambda why: refusals.append(why) or (_ for _ in ()).throw(b.BatchRefused(why)))
    v, a = torch.zeros(2, 128, 4, 4, 4), torch.zeros(2, 8, 26, 16)
    ok_kwargs = {'context': torch.zeros(2, 1024, 8), 'control': None, 'frame_rate': 24.0,
                 'transformer_options': {'sigmas': torch.full((2,), 0.9), 'sample_sigmas': torch.zeros(9),
                                         'cond_or_uncond': [0], 'uuids': ['u'], 'patches_replace': {}}}
    guard('a', True, ([v, a], (torch.full((2,), 0.9), torch.full((2,), 0.9))), ok_kwargs)
    bad = dict(ok_kwargs, attention_mask=torch.zeros(1, 1024))
    raises(lambda: guard('a', False, ([v, a], (torch.full((2,), 0.9),) * 2), bad), 'without the batch dimension')
    raises(lambda: guard('b', True, ([v, a], (torch.tensor([0.9, 0.7]), torch.full((2,), 0.9))), ok_kwargs),
           'lockstep')
    # batch conds: each clip's own raw features (different token counts) registered, placeholder
    # names them; equal metadata required except the unread pooled_output
    class G:
        def __init__(self, patcher):
            self.model_patcher, self.model_options, self.cfg = patcher, patcher.model_options, 1.0
            self.original_conds = {}

        def inner_set_conds(self, conds):
            self.original_conds = {k: [{**c[1], 'cross_attn': c[0], 'model_conds': {}, 'uuid': 'new'}
                                       for c in v] for k, v in conds.items()}

        def set_cfg(self, cfg):
            self.cfg = cfg
    patcher = types.SimpleNamespace(model_options={})
    feats = [torch.randn(1, 56, 16), torch.randn(1, 31, 16)]
    gs = []
    for i, f in enumerate(feats):
        g = G(patcher)
        meta = {'frame_rate': 24.0, 'unprocessed_ltxav_embeds': True, 'pooled_output': torch.full((1, 4), float(i))}
        g.inner_set_conds({'positive': [[f, dict(meta)]], 'negative': [[f, dict(meta)]]})
        gs.append(g)
    registered = []

    def register(raws):
        registered.append(raws)
        return len(registered) - 1
    bg = b.batch_guider(gs, 'stage a', register)
    pos, neg = bg.original_conds['positive'][0]['cross_attn'], bg.original_conds['negative'][0]['cross_attn']
    assert tuple(neg.shape) == (2, 1, 1) and tuple(pos.shape) == (2, 2, 1)     # names tags 0 / 1 (sorted names)
    assert b.placeholder_tag(neg, 2) == 0 and b.placeholder_tag(pos, 2) == 1
    assert registered[1][0] is feats[0] and registered[1][1] is feats[1]
    assert bg.original_conds['positive'][0]['unprocessed_ltxav_embeds'] is True
    gs[1].original_conds['positive'][0]['frame_rate'] = 25.0
    raises(lambda: b.batch_guider(gs, 'stage a', register), 'metadata differs')
    gs[1].original_conds['positive'][0]['frame_rate'] = 24.0
    gs[1].original_conds['positive'][0]['attention_mask'] = torch.ones(1, 1024)
    gs[0].original_conds['positive'][0]['attention_mask'] = torch.zeros(1, 1024)
    raises(lambda: b.batch_guider(gs, 'stage a', register), 'metadata differs')
    for g in gs:
        g.original_conds['positive'][0].pop('attention_mask')
    gs[1].original_conds['positive'][0]['cross_attn'] = torch.randn(1, 31, 8)
    raises(lambda: b.batch_guider(gs, 'stage a', register), 'one width')
    gs[1].original_conds['positive'][0]['cross_attn'] = feats[1]
    other = G(types.SimpleNamespace(model_options={}))
    other.original_conds = gs[0].original_conds
    raises(lambda: b.batch_guider([gs[0], other], 'stage a', register), 'different patchers')
    # latent dicts: samples stacked, masks refused
    st = b.stack_latent_dicts([{'samples': torch.zeros(1, 2)}, {'samples': torch.ones(1, 2)}], 'v')
    assert torch.equal(st['samples'], torch.tensor([[0., 0.], [1., 1.]]))
    raises(lambda: b.stack_latent_dicts([{'samples': torch.zeros(1, 2), 'noise_mask': 1}] * 2, 'v'), 'masks')


case('stacking: batchproof census (packet 72) agrees; forward guard; stacked conds', stacking_case)


# --- 4b. the lean memo splits batch rows (connector at batch 1 per row, memo per row) ----------
def memo_rows_case():
    import ltx_lean_conditioning as lean
    calls = []

    def original(context, unprocessed=False):          # stand-in connector: fixed output length 4
        calls.append((tuple(context.shape), context.dtype))
        return context.float().mean(dim=1, keepdim=True).expand(1, 4, context.shape[-1]) * 2
    raws = [torch.randn(1, 56, 3), torch.randn(1, 31, 3)]           # per-prompt token counts differ
    lean.begin_clip(5, True, batch=2)
    try:
        tag = lean.register_batch_raw(raws)
        ph = b.placeholder(2, tag).to(dtype=torch.bfloat16)          # what extra_conds hands the connector
        out = lean.memo_call(original, ph, unprocessed=True)
        want = torch.cat([original(r.to(dtype=torch.bfloat16)) for r in raws])
        calls[:] = calls[:2]
        assert torch.equal(out, want) and calls == [((1, 56, 3), torch.bfloat16), ((1, 31, 3), torch.bfloat16)], calls
        lean.memo_call(original, ph, unprocessed=True)               # negative / stage b: reused per row
        assert len(calls) == 2
        raises(lambda: lean.memo_call(original, torch.zeros(3, 1, 1), unprocessed=True), 'placeholder')
        raises(lambda: lean.memo_call(original, torch.zeros(2, 9, 1), unprocessed=True), 'No registered raw')
    finally:
        summary = lean.end_clip()
    assert summary['connector_computed'] == 2 and summary['connector_reused'] == 2 and summary['batch'] == 2
    raises(lambda: lean.register_batch_raw(raws), 'No batch job context')


case('batch conds: connector per clip at batch 1 on its own raw features (any token count), memo per row', memo_rows_case)


# --- 5. env allowlist -------------------------------------------------------------------------
def env_case():
    code = ('import sys, types; sys.path.insert(0, %r); '
            'stub = types.ModuleType("encoder_diagnostics"); stub._context = lambda: None; '
            'sys.modules["encoder_diagnostics"] = stub; '
            'import ltx_pipeline as p; import pipeline_sampler_node as n; '
            'print(n.SAMPLER_BATCH, n.SAMPLER_WORKERS, p.STAGE_WORKERS["sample"])') % str(HERE)
    for batch, workers, want in (('1', None, '1 2 2'), ('2', '1', '2 1 1'), ('4', '2', '4 2 2'),
                                 (None, '3', '1 3 3'), ('2', '4', '2 4 4')):
        env = dict(os.environ, ONEAPI_DEVICE_SELECTOR='opencl:cpu')
        env.pop('LTX_SAMPLER_BATCH', None)
        env.pop('LTX_SAMPLER_WORKERS', None)
        if batch is not None:
            env['LTX_SAMPLER_BATCH'] = batch
        if workers is not None:
            env['LTX_SAMPLER_WORKERS'] = workers
        out = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env, timeout=300)
        assert out.returncode == 0 and out.stdout.strip().splitlines()[-1] == want, (batch, workers, out.stdout,
                                                                                    out.stderr[-600:])
    for bad in ('3', '8', 'two'):
        env = dict(os.environ, ONEAPI_DEVICE_SELECTOR='opencl:cpu', LTX_SAMPLER_BATCH=bad)
        out = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env, timeout=300)
        assert out.returncode != 0 and 'LTX_SAMPLER_BATCH must be one of (1, 2, 4)' in out.stderr, (bad, out.stderr[-400:])


case('LTX_SAMPLER_BATCH allowlist 1/2/4 (3 refused), default 1; one sampler worker accepted', env_case)


# --- 6. lockstep ---------------------------------------------------------------------------------
def lockstep_case():
    s = torch.tensor([1.0, 0.9, 0.0])
    assert b.lockstep_sigmas([s, s.clone()], 'a') is s
    raises(lambda: b.lockstep_sigmas([s, torch.tensor([1.0, 0.8, 0.0])], 'a'), 'lockstep')
    raises(lambda: b.lockstep_sigmas([s, s.to(torch.float64)], 'a'), 'lockstep')
    ok, flags = b.rows_uniform_nonzero(NT([torch.zeros(2, 3), torch.zeros(2, 4)]), 2)
    assert ok and flags == [False, False]
    v = torch.zeros(2, 3)
    v[1, 0] = 1
    ok, flags = b.rows_uniform_nonzero(NT([v, torch.zeros(2, 4)]), 2)
    assert not ok and flags == [False, True]
    assert b.rows_equal(torch.full((4,), 0.5)) and not b.rows_equal(torch.tensor([0.5, 0.5, 0.4, 0.5]))


case('lockstep: unequal sigma schedules and mixed all-zero rows refuse', lockstep_case)


# --- 7. batch 1 unchanged -------------------------------------------------------------------------
def b1_case():
    src = (HERE / 'pipeline_sampler_node.py').read_text()
    assert ("out, detail = pipeline.run_behind(\n                        'sample', clip_index, depth,\n"
            "                        lambda: sample_clip(clip_index, lean_mode=lean_mode, **chain), target=target)") in src
    assert "target = _PIN[0] if not _capp.CAPTURES_FROZEN[0] else None\n                _PIN[0] = None" in src
    assert "if SAMPLER_BATCH != 1:\n                    out, detail = self._batch_step(" in src
    # the batch-1 server refuses a batch arm before anything runs
    n.SAMPLER_BATCH = 1
    n._failed = False
    raises(lambda: n.LTXPipelineSampler()._apply('pipeline', 1, 2, 'x', batch=2, stream_last=0), 'batch-1 server')
    # lean memo: identical behaviour to packet 95's module on batch-1 contexts
    import ltx_lean_conditioning as new
    spec = importlib.util.spec_from_file_location('lean95', P95 / 'source/scripts/ltx_lean_conditioning.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    for lean_flag in (True, False):
        outs = []
        for mod in (old, new):
            log = []

            def original(context, unprocessed=False, log=log):
                log.append((tuple(context.shape), unprocessed))
                return context + 1
            mod.begin_clip(7, lean_flag)
            x = torch.arange(6.0).reshape(1, 2, 3)
            r = [mod.memo_call(original, x, unprocessed=True), mod.memo_call(original, x.clone(), unprocessed=True),
                 mod.memo_call(original, x + 1, unprocessed=True)]
            mod.set_stage('a')
            mod.sentry_observe(([x], 0.5), {'context': x})
            outs.append((log, [t.tolist() for t in r], mod.end_clip()))
        assert outs[0] == outs[1], outs
    # started stages still refuse a decrease; a fresh stage admits one worker
    p.clear()
    p.set_stage_workers('decode', 2)
    p.submit('decode', 979000, lambda: 1)
    p.collect('decode', 979000)
    raises(lambda: p.set_stage_workers('decode', 1), 'may only increase')
    # every top-level name of packet 95's versions of the changed modules still exists
    for fname in ('ltx_lean_conditioning.py', 'pipeline_sampler_node.py', 'ltx_pipeline.py'):
        before = {nd.name for nd in ast.parse((P95 / 'source/scripts' / fname).read_text()).body
                  if isinstance(nd, (ast.FunctionDef, ast.ClassDef))}
        after = {nd.name for nd in ast.parse((HERE / fname).read_text()).body
                 if isinstance(nd, (ast.FunctionDef, ast.ClassDef))}
        assert before <= after, (fname, sorted(before - after))
    # the built packet: every packet 95 graph byte-identical
    if P96.is_dir():
        for g in sorted((P95 / 'graphs').glob('*.json')):
            assert (P96 / 'graphs' / g.name).read_bytes() == g.read_bytes(), g.name


case('batch 1 unchanged: graphs, run_behind call, lean memo, refusal of batch arms, worker rule', b1_case)


# --- 8. agreement ------------------------------------------------------------------------------------
def agreement_case():
    gen = (HERE / 'prepare-graph-capture-runtime.py').read_text()
    depths = ast.literal_eval(gen.split('SAMPLER_DEPTH_OVERRIDES_96 = ')[1].split('\n')[0])
    arms = ast.literal_eval(gen.split('SAMPLER_BATCH_ARMS = ')[1].split('\n')[0])
    gate_depths = ast.literal_eval(gen.split('    batch_depths = ')[1].split('\n')[0])
    gate_arms = ast.literal_eval(gen.split('    batch_arms = ')[1].split('\n')[0])
    assert depths == gate_depths and arms == gate_arms
    for name, batch in arms.items():
        if '-ref' in name or 'tsh-win-b' in name:
            assert depths[name] == b.serial_depth(batch), name
        else:
            assert depths[name] == b.timed_depth(int(name.rsplit('-w', 1)[1]), batch), name
    assert depths['pipe-samp2-tsh-rep-wlean-s1'] == b.timed_depth(1, 1)
    sh = (HERE / 'run-campaign-96.sh').read_text()
    for batch in (2, 4):
        for w in (1, 2, 3, 4):
            assert 'pipe-samp2-tsh-rep-wlean-b%d-w%d' % (batch, w) in arms
        assert 'pipe-samp2-tsh-rep-wlean-b%d-ref' % batch in arms and 'pipe-samp2-tsh-win-b%d' % batch in arms
        # prompt counts are derived by the runner from the packet graphs' depths (checked by the
        # simulated-arm case against an independent simulation), never hard-coded
        assert 'REF_N=' not in sh.split('read REF_K REF_N REF_SD REF_DD')[0]
        assert len(b.ORDERS[batch]['proof-neighbours']) == len(b.ORDERS[batch]['proof-slots']) == \
            len(b.ORDERS[batch]['ref'])
    assert 'TIMED_ARM=pipe-samp2-tsh-rep-wlean-b$BATCH-w$WORKERS' in sh and 'REF_ARM=pipe-samp2-tsh-rep-wlean-b$BATCH-ref' in sh
    assert 'CAP_ARM=pipe-samp2-tsh-win-b$BATCH' in sh and 'DEPTH=$(( (WORKERS + 1) * BATCH - 1 ))' in sh
    assert 'TIMED_ARM=pipe-samp2-tsh-rep-wlean-s$WORKERS' in sh
    assert 'NEOReadDebugKeys=1 EnableDeferBacking=0' in sh and 'EDB" = 0' in sh
    assert 'LTX_SAMPLER_BATCH' in sh and 'BASE=$((PBASE + 1000 * IDX))' in sh and 'PSUF= ; PBASE=264000' in sh
    assert 'IDX=$((12 * LI + 3 * (WORKERS - 1) + BI))' in sh
    ranges = sorted((264000 + 1000 * (12 * li + 3 * (w - 1) + bi), 264000 + 1000 * (12 * li + 3 * (w - 1) + bi) + 620)
                    for li in range(3) for w in range(1, 5) for bi in range(3))
    assert len(ranges) == 36 and all(x[1] < y[0] for x, y in zip(ranges, ranges[1:]))
    assert ranges[0][0] > 254000 + 1000 * 8 + 720          # above every 95b base
    client = (HERE / 'run-throughput-fixtures-96.py').read_text()
    assert "g['428']['inputs']['stream_last'] = 1 if i == a.count - 1 else 0" in client
    if P96.is_dir():
        man = json.loads((P96 / 'manifest.json').read_text())
        assert man['sampler_batch']['sampler_depths'] == depths and man['sampler_batch']['batch_arms'] == arms
        assert man['sampler_batch']['choices'] == [1, 2, 4] and man['sampler_workers']['choices'] == [1, 2, 3, 4]
        for name, d in depths.items():
            g = json.loads((P96 / 'graphs' / ('graph-capture-all48-%s.json' % name)).read_text())
            inputs = g['428']['inputs']
            assert inputs['depth'] == d, name
            if name in arms:
                assert inputs['batch'] == arms[name] and inputs['stream_last'] == 0, name
            else:
                assert 'batch' not in inputs and 'stream_last' not in inputs
            assert g['364']['inputs']['mode'] == 'pipeline-window'
        assert man['files']['source/scripts/ltx_sampler_batch.py'] == man['extension_sha256s']['ltx_sampler_batch.py']
        for f in ('pipeline_sampler_node.py', 'ltx_pipeline.py', 'ltx_lean_conditioning.py', 'ltx_sampler_batch.py'):
            assert (P96 / 'source/scripts' / f).read_bytes() == (HERE / f).read_bytes(), f


case('generator, gate, runner, client and packet agree on arms, depths, prompt counts and index bases', agreement_case)


# --- 9. proof arrangements ------------------------------------------------------------------------------
IDS = ['f%d' % i for i in range(10)]
FIXTURES = [{'id': i} for i in IDS]
CLIENT = load_script('client96', 'run-throughput-fixtures-96.py')


def simulate_arm(batch, sampler_depth, count, order, base, decode_depth=2, drop=None, dup=None):
    """A stream through the REAL batch step and the REAL ltx_pipeline decode run_behind (depth 2,
    as the replica decode), with a stand-in batch job that records the same batch-job fingerprint
    as sample_batch. Returns the client's rows (through its own provenance join), the sampler
    receipts and the per-prompt (sampler emitted, decode emitted) pairs."""
    p.clear()
    p.set_stage_workers('sample', 4)
    p.set_stage_workers('decode', 2)
    n.SAMPLER_BATCH = batch
    n._GROUPER = b.Grouper(batch)

    def fake_sample_batch(job, lean_mode):
        for slot, (c, _ch) in enumerate(job['rows']):
            if c is not None:
                p.record_fingerprint(('batch-job', c), {'job': job['key'], 'batch': batch,
                                                        'rows': [r for r, _ in job['rows']],
                                                        'fill_slots': job['fill_slots'], 'fill_of': job['fill_of'],
                                                        'slot': slot})
        return {c: ('clip', c) for c, _ch in job['rows'] if c is not None}
    n.sample_batch = fake_sample_batch
    node = n.LTXPipelineSampler()
    sampler_receipts, pairs, rows = [], [], []
    for i in range(count):
        out, det = node._batch_step({}, 'pipeline-lean', base + i, sampler_depth, i == count - 1, True,
                                    {'clip': base + i}, None)
        e = det['emitted_index']
        if e >= 0:
            det['emitted_batch_job'] = p.fingerprint(('batch-job', e))
        sampler_receipts.append({'detail': det})
        if e >= 0:
            _o, ddet = p.run_behind('decode', e, decode_depth, (lambda e=e: ('decoded', e)))
            d = ddet['emitted_index']
        else:
            d = -1
        pairs.append((e, d))
    p.clear()
    emitted = [(-1 if d < 0 else d - base) for _e, d in pairs]
    if drop is not None:
        emitted[drop] = -1
    if dup is not None:
        emitted[dup[1]] = emitted[dup[0]]
    pmap = CLIENT.provenance_map(sampler_receipts)
    seen = set()
    for i, rel in enumerate(emitted):
        if rel < 0:
            rows.append({'prompt': 'x-%02d' % i, 'emitted_index': -1, 'fill': True})
            continue
        rows.append({'prompt': 'x-%02d' % i, 'emitted_index': rel, 'emitted_fixture': IDS[order[rel]],
                     'fill': False, 'duplicate': rel in seen, 'reference': 'ref-' + IDS[order[rel]], 'exact': True,
                     'batch': CLIENT.batch_info_for(base + rel, pmap, order, FIXTURES, base)})
        seen.add(rel)
    return rows, sampler_receipts, pairs


def simulated_arm_case():
    for batch in (2, 4):
        ref = b.ORDERS[batch]['ref']
        k = len(ref)
        for sd in (b.serial_depth(batch), b.timed_depth(1, batch), b.timed_depth(2, batch)):
            for count in range(1, k + sd + 6):
                order = b.order_for('ref', batch, count)
                rows, recs, pairs = simulate_arm(batch, sd, count, order, 970000)
                emitted = [r['emitted_index'] for r in rows if r['emitted_index'] >= 0]
                # independent of any formula: the simulation decides what was emitted
                assert emitted == list(range(len(emitted))), emitted
                assert len(emitted) == CLIENT.expected_clip_count(count, sd, 2), (batch, sd, count, len(emitted))
                for r in rows:
                    if r['emitted_index'] >= 0:
                        info = r['batch']
                        assert info['rows'][info['slot']] == 970000 + r['emitted_index']
                        if r['emitted_index'] < k - (k % batch):
                            slot, nb = b.arrangement(order, batch, count)[r['emitted_index']]
                            assert info['slot'] == slot and info['neighbour_fixtures'] == [IDS[x] for x in nb], \
                                (batch, sd, count, r, slot, nb)
                # the old same-prompt join attaches another clip's job whenever a clip is emitted
                if emitted:
                    wrong = [i for i, (e, d) in enumerate(pairs) if d >= 0 and e != d]
                    assert wrong, 'decode no longer trails the sampler?'
        # the runner's derived count emits exactly the arrangement (13 for B=2, 17 for B=4)
        n_ref = k + b.serial_depth(batch) + 2
        assert n_ref == {2: 13, 4: 17}[batch]
        rows, _r, _p = simulate_arm(batch, b.serial_depth(batch), n_ref, b.order_for('ref', batch, n_ref), 971000)
        got = [r['emitted_fixture'] for r in rows if r['emitted_index'] >= 0]
        assert got == [IDS[x] for x in ref], got
        if batch == 4:
            assert got.count('f0') == 2 and got.count('f1') == 2          # both intended repeats present
        assert CLIENT.emission_problems([r['emitted_index'] for r in rows], k) == []
        assert CLIENT.emission_problems([0, 1, 1, 2], 3) and CLIENT.emission_problems([0, 2], 3)
    # the provenance join refuses a job that does not name the clip at its slot
    raises(lambda: CLIENT.batch_info_for(5, {5: {'slot': 0, 'rows': [6, 5]}}, list(range(10)), FIXTURES, 0),
           'names row')
    raises(lambda: CLIENT.provenance_map([{'detail': {'emitted_index': 3, 'emitted_batch_job': {}}}] * 2),
           'two sampler receipts')


case('simulated arms (real batch step, real decode lag): provenance per emitted clip, counts incl. drain', simulated_arm_case)


def proof_case():
    chk = load_script('chk96', 'check-batch-proof-96.py')
    ids = IDS
    for batch in (2, 4):
        ref = b.ORDERS[batch]['ref']
        k = len(ref)
        n_arm = k + b.serial_depth(batch) + 2
        ref_rows, _r, _p = simulate_arm(batch, b.serial_depth(batch), n_arm, b.order_for('ref', batch, n_arm), 972000)
        occ = {}
        for r in ref_rows:
            if r['emitted_index'] >= 0:
                occ.setdefault(r['emitted_fixture'], []).append(
                    {'slot': r['batch']['slot'], 'neighbour_fixtures': r['batch']['neighbour_fixtures']})
        prereg = {'batch': batch, 'campaign': 'test', 'fixtures': [
            {'id': i, 'reference': 'ref-' + i, 'arrangement': {'occurrences': occ[i]}} for i in ids]}
        if batch == 4:
            assert [len(occ['f0']), len(occ['f1'])] == [2, 2] and occ['f0'][0]['slot'] != occ['f0'][1]['slot']

        def arm(order_name, **kw):
            order = b.order_for(order_name, batch, n_arm)
            rows, _r, _p = simulate_arm(batch, b.serial_depth(batch), n_arm, order, 973000, **kw)
            return {'batch': batch, 'index_base': 973000, 'rows': rows, 'fixture_order': [ids[x] for x in order]}
        for kind, order_name in (('neighbours', 'proof-neighbours'), ('slots', 'proof-slots')):
            res = chk.evaluate(prereg, arm(order_name), kind, k)
            assert res['passed'], (batch, kind, res['problems'])
            assert not chk.evaluate(prereg, arm('ref'), kind, k)['passed']        # the reference order fails
            bad = arm(order_name)
            bad['rows'][-1]['exact'] = False
            assert not chk.evaluate(prereg, bad, kind, k)['passed']
            # review finding 4: a missing clip, a duplicate, an empty arm, a wrong count all reject
            missing = arm(order_name, drop=len(bad['rows']) - 1)
            assert not chk.evaluate(prereg, missing, kind, k)['passed']
            last = len(bad['rows']) - 1
            dup = arm(order_name, dup=(last - 1, last))
            assert not chk.evaluate(prereg, dup, kind, k)['passed']
            empty = dict(arm(order_name), rows=[])
            assert not chk.evaluate(prereg, empty, kind, k)['passed']
            assert not chk.evaluate(prereg, arm(order_name), kind, k + 1)['passed']
            assert not chk.evaluate(prereg, arm(order_name), kind, 0)['passed']
            swapped = arm(order_name)
            swapped['fixture_order'][0], swapped['fixture_order'][1] = swapped['fixture_order'][1], swapped['fixture_order'][0]
            assert not chk.evaluate(prereg, swapped, kind, k)['passed']
    shift = b.order_for('shift', 2, 40)
    pairs = {tuple(sorted(shift[i:i + 2])) for i in range(0, 40, 2)}
    assert len(pairs) > 5, pairs                                        # composition varies across cycles


case('proof checker: other neighbours / slots pass; reference order, missing, duplicate, empty, miscount fail', proof_case)


# --- 10. memory and markers ---------------------------------------------------------------------------
def memory_markers_case():
    hr = load_script('hr96', 'worker-headroom-96.py')
    ok, d = hr.plan('two-way', 1, 2)
    assert ok, d
    assert not hr.plan('two-way', 1, 4)[0]                              # predicted not to fit: skipped
    assert hr.plan('shard4-a', 1, 2)[0] and hr.plan('shard3-c', 1, 2)[0]
    assert hr.plan('two-way', 2, 1)[0] and hr.plan('two-way', 2, 1)[1]['all_workers_fit_prediction']
    G = 2**30
    after_w0 = {'xpu:0': int(2.45 * G), 'xpu:1': int(6.58 * G), 'xpu:2': int(11.8 * G), 'xpu:3': int(16.7 * G)}
    assert not hr.live(after_w0, 'two-way', 2)[0]                       # two-way: no second batch-2 worker
    assert abs(hr.needed('two-way', 1, False)['xpu:0'] - (2.0 + 0.12 * 23 + 0.1)) < 1e-9   # = packet 95 rule
    mm = load_script('mm96', 'missing-markers-96.py')
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root, run = Path(tmp), Path(tmp) / 'run'
        run.mkdir()
        for i, (sub, clips) in enumerate(((None, []), ([500, 501], [500, 501]), (None, []))):
            name = 'pfx-%02d' % i
            (root / 'requests' / name).mkdir(parents=True)
            (root / 'requests' / name / 'submission.json').write_text('{}')
            (run / ('pipeline-sampler-%s.json' % name)).write_text(json.dumps(
                {'clip_index': 500 + i, 'sampler_batch': 2, 'detail': {'submitted_job_clips': clips}}))
        assert sorted(mm.expected(root, run, ['pfx'])) == ['sample-500', 'sample-501']
        (run / 'pipeline-sampler-pfx-02.json').write_text(json.dumps({'clip_index': 502, 'detail': {}}))
        assert sorted(mm.expected(root, run, ['pfx'])) == ['sample-500', 'sample-501', 'sample-502']


case('memory plan/live on the 95b figures; missing markers only for submitted batch jobs', memory_markers_case)

def summary_and_signature_case():
    import ltx_graph_capture as g
    vx2, ax1 = torch.zeros(2, 4, 3), torch.zeros(1, 5, 3)
    assert b.leading_dims(g.describe((vx2, ax1), 'img')) == {1, 2}           # review finding 5: video counted
    assert b.leading_dims(g.describe((torch.zeros(4, 2), torch.zeros(4, 3)), 'img')) == {4}
    assert b.leading_dims(g.describe({'a': torch.zeros(3, 1), 'b': [torch.zeros(2)]}, 'o')) == {2, 3}

    class Route:
        def __init__(self, entries):
            self.entries = entries
    key2 = (g.describe((torch.zeros(2, 1), torch.zeros(2, 1)), 'img'), (), (), ())
    key_mixed = (g.describe((torch.zeros(1, 1), torch.zeros(2, 1)), 'img'), (), (), ())
    assert b.signature_batches([Route({7: {key2: 1}})], [7]) == [2]
    assert b.signature_batches([Route({7: {key2: 1, key_mixed: 1}})], [7]) == [1, 2]
    sm = load_script('sum96', 'summarize-campaign-96.py')
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        run, out = Path(tmp) / 'run', Path(tmp) / 'out'
        run.mkdir(); out.mkdir()
        fx_file = Path(tmp) / 'fx.json'
        fx_file.write_text(json.dumps({'fixtures': [{'id': i} for i in IDS]}))
        order = [IDS[x] for x in b.order_for('ref', 2, 13)]
        for prefix in ('pa', 'pb'):
            rows = []
            for i in range(13):
                name = '%s-%02d' % (prefix, i)
                se = i - 1                                   # sampler releases clip i-1, decode emits i-3
                (run / ('pipeline-sampler-%s.json' % name)).write_text(json.dumps({'detail': {
                    'emitted_index': (500 + se) if se >= 0 else -1,
                    'emitted_context_sentry': {'stage_a_context_sha256': 'A' + order[se], 'stage_b_context_sha256':
                                               'B' + order[se]} if se >= 0 else None}}))
                de = i - 3
                rows.append({'prompt': name, 'index': i, 'emitted_index': de if de >= 0 else -1, 'fill': de < 0,
                             'emitted_fixture': order[de] if de >= 0 else None, 't_done': 1000.0 + i,
                             'reference': ('ref-' + order[de]) if de >= 0 else None, 'exact': True})
            (out / ('%s-throughput.json' % prefix)).write_text(json.dumps(
                {'rows': rows, 'index_base': 500, 'fixture_order': order, 'batch': 2}))
        rc = sm.main(['--run', str(run), '--out', str(out), '--batch', '2', '--fixtures', str(fx_file),
                      '--arm', 'pa:a', '--arm', 'pb:b', '--pair', 'pa:pb'])
        summ = json.loads((out / 'summary.json').read_text())
        assert summ['arms']['pa']['context_sentries']['f0'] == [['Af0', 'Bf0']], summ['arms']['pa']['context_sentries']
        assert rc == 0 and summ['context_sentry_gate_passed'] is True
        # review finding 6: an absent arm or pair fails; finding 2: a required proof must exist and pass
        assert sm.main(['--run', str(run), '--out', str(out), '--batch', '2', '--fixtures', str(fx_file),
                        '--arm', 'pa:a', '--arm', 'pz:z', '--pair', 'pa:pz']) == 3
        assert sm.main(['--run', str(run), '--out', str(out), '--batch', '2', '--fixtures', str(fx_file),
                        '--arm', 'pa:a', '--arm', 'pb:b', '--pair', 'pa:pb', '--require-proof', 'proof-timed.json']) == 3
        (out / 'proof-timed.json').write_text(json.dumps({'passed': False}))
        assert sm.main(['--run', str(run), '--out', str(out), '--batch', '2', '--fixtures', str(fx_file),
                        '--arm', 'pa:a', '--arm', 'pb:b', '--pair', 'pa:pb', '--require-proof', 'proof-timed.json']) == 3
        (out / 'proof-timed.json').write_text(json.dumps({'passed': True}))
        assert sm.main(['--run', str(run), '--out', str(out), '--batch', '2', '--fixtures', str(fx_file),
                        '--arm', 'pa:a', '--arm', 'pb:b', '--pair', 'pa:pb', '--require-proof', 'proof-timed.json']) == 0
    sh = (HERE / 'run-campaign-96.sh').read_text()
    assert '-- "${OUT#$REPO/}" "$@" ) >/dev/null' in sh                       # finding 7: commit restricted
    assert '--kind timed --expect-clips $TIMED_K' in sh and 'finish 19' in sh  # finding 2
    assert '--require-proof proof-timed.json' in sh


case('leading_dims through the real describe(); summary attribution, missing arms and proofs; runner commit/proof', summary_and_signature_case)

def slots_of(registry, dev, tid, key):
    return registry.groups[(dev, tid)].slots[key]


def shared_pool_case():
    import ltx_graph_capture as g
    # allowlist at import (subprocess; this process keeps the default)
    code = ('import sys; sys.path.insert(0, %r); sys.path.insert(1, %r); '
            'sys.argv = [sys.argv[0], "--cpu", "--disable-dynamic-vram"]; '
            'import comfy.options; comfy.options.enable_args_parsing(); '
            'import ltx_graph_capture as g; print(g.SHARED_POOL)') % (str(HERE), COMFY_SRC)
    for value, want in (('0', '0'), ('1', '1'), (None, '0')):
        env = dict(os.environ, ONEAPI_DEVICE_SELECTOR='opencl:cpu', PYTHONDONTWRITEBYTECODE='1')
        env.pop('LTX_SAMPLER_SHARED_POOL', None)
        if value is not None:
            env['LTX_SAMPLER_SHARED_POOL'] = value
        out = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env, timeout=300)
        assert out.returncode == 0 and out.stdout.strip().splitlines()[-1] == want, (value, out.stdout, out.stderr[-500:])
    for bad in ('2', 'yes'):
        env = dict(os.environ, ONEAPI_DEVICE_SELECTOR='opencl:cpu', PYTHONDONTWRITEBYTECODE='1', LTX_SAMPLER_SHARED_POOL=bad)
        out = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env, timeout=300)
        assert out.returncode != 0 and 'LTX_SAMPLER_SHARED_POOL must be one of (0, 1)' in out.stderr
    # pool/stream keyed per (device, thread), with a stand-in graph API
    made = []
    saved = (g.SHARED_POOL, g._POOL_FACTORY[0], g._STREAM_FACTORY[0])
    g._POOL_FACTORY[0] = lambda device: made.append(('pool', str(device))) or object()
    g._STREAM_FACTORY[0] = lambda device: made.append(('stream', str(device))) or object()
    try:
        g.SHARED_POOL = 0
        p0, s0 = g.capture_resources('xpu:0')
        p1, s1 = g.capture_resources('xpu:0')
        assert p0 is None and p1 is None and s0 is not s1            # off: private pool, fresh stream each time
        g.SHARED_POOL = 1
        g.clear_shared_pools()
        a = g.capture_resources('xpu:0')
        assert g.capture_resources('xpu:0') == a                       # same (device, thread): same pool and stream
        b_ = g.capture_resources('xpu:1')
        assert b_[0] is not a[0] and b_[1] is not a[1]                 # another device: its own
        other = []
        t = threading.Thread(target=lambda: other.append(g.capture_resources('xpu:0')))
        t.start(); t.join()
        assert other[0][0] is not a[0] and other[0][1] is not a[1]     # another thread: its own
        g.clear_shared_pools()
        assert g.capture_resources('xpu:0')[0] is not a[0]             # handle dropped, never reused
    finally:
        g.SHARED_POOL, g._POOL_FACTORY[0], g._STREAM_FACTORY[0] = saved
        g.clear_shared_pools()
    src = (HERE / 'ltx_graph_capture.py').read_text()
    inst, rest = src.split('\ndef install(')[1], src.split('\ndef restore(')[1]
    assert 'clear_shared_pools()' in inst.split('\ndef ')[0] and 'clear_shared_pools()' in rest.split('\ndef ')[0]
    assert 'pool, capture_stream = capture_resources(self.device)' in src
    assert 'with torch.no_grad(), torch.xpu.graph(graph, stream=capture_stream):' in src   # off branch as in 95
    assert 'torch.xpu.graph(graph, pool=pool, stream=capture_stream)' in src
    old = (P95 / 'source/scripts/ltx_graph_capture.py').read_text()
    assert 'with torch.no_grad(), torch.xpu.graph(graph, stream=capture_stream):' in old
    # lazily cached tensors are detected
    m = torch.nn.Sequential(torch.nn.Linear(2, 2))
    before = g._module_tensors([m])
    m[0].cache = torch.zeros(1)
    assert set(g._module_tensors([m]).items()) - set(before.items())
    # chain check with stand-in graphs on CPU: two stage shapes A (2 rows x 3) and B (2 x 5),
    # a "pool" scalar shared by every graph of the (device, thread) stands for aliased scratch
    dev = torch.device('cpu')
    tid = threading.get_ident()

    def build(bad_block=None, flaky=False, drop_shape_on=None, cross_shape=False):
        pool = {'last': None}
        slots, keys = {}, ('A', 'B')
        for k, width in zip(keys, (3, 5)):
            vx, ax = torch.zeros(2, width), torch.zeros(2, 2)
            kw = {name: None for name in g.KEYWORDS}
            kw['v_context'] = torch.full((2, 1), 0.5)
            kw['transformer_options'] = {}
            slots[k] = g.Slot((vx, ax), kw, [vx, ax, kw['v_context']])
        group = types.SimpleNamespace(slots=slots)
        registry = types.SimpleNamespace(groups={(dev, tid): group})
        routes = []
        for i in range(3):
            def invoke(img, kwargs, i=i):
                v, a2 = img
                return (v * (i + 2) + kwargs['v_context'], a2 + i)
            entries = {}
            for k in keys:
                if drop_shape_on == i and k == 'B':
                    continue
                count = [0]
                slot = slots[k]

                def replay(i=i, k=k, count=count, invoke=invoke, slot=slot):
                    v, a2 = invoke(slot.img, slot.kw)
                    if i == bad_block:
                        v = v + 1
                    if flaky and i == 2:
                        count[0] += 1
                        v = v + count[0]
                    if cross_shape and i == 0:
                        # a graph of shape A that reads scratch shape B left behind: wrong only
                        # when B ran in between (A, B, A order)
                        if k == 'A' and pool['last'] == 'B':
                            v = v + 1
                        pool['last'] = k
                    slot.img[0].copy_(v); slot.img[1].copy_(a2)
                entries[k] = types.SimpleNamespace(graph=types.SimpleNamespace(replay=replay),
                                                   out_vx=slot.img[0], out_ax=slot.img[1])
            routes.append(types.SimpleNamespace(device=dev, index=i, entries={tid: entries}, _invoke=invoke))
        return routes, registry, slots
    routes, registry, slots = build()
    slots['A'].img[0].fill_(7.0)
    ok, detail = g.chain_check(routes, registry, [tid], sync=lambda d: None)
    assert ok and detail['chains_checked'] == 1 and detail['rows'][0]['passed'], detail
    assert detail['rows'][0]['order'] == 'ABAB'
    assert torch.all(slots['A'].img[0] == 7.0)                           # slot contents restored
    for kw_ in ({'bad_block': 1}, {'flaky': True}, {'cross_shape': True}, {'drop_shape_on': 2}):
        routes, registry, _s = build(**kw_)
        ok, detail = g.chain_check(routes, registry, [tid], sync=lambda d: None)
        assert not ok, (kw_, detail)
    routes, registry, _s = build()
    assert g.chain_check(routes, registry, [tid], sync=lambda d: None, expected_shapes=3)[0] is False
    assert g.chain_check(routes, registry, [tid + 1], sync=lambda d: None)[0] is False   # thread without graphs
    budget = g.chain_check_budget(routes, registry, [tid], transient_bytes=1000)
    flat = sum(t.numel() * t.element_size() for k in 'AB' for t in slots_of(registry, dev, tid, k).flat)
    img = sum(t.numel() * t.element_size() for k in 'AB' for t in slots_of(registry, dev, tid, k).img)
    assert budget == {'cpu': 2 * flat + 6 * img + 1000}, budget
    # pool retirement: a reset graph that owned nothing retires the handle; an owned pool stays
    saved = (g.SHARED_POOL, g._POOL_FACTORY[0], g._STREAM_FACTORY[0])
    g._POOL_FACTORY[0] = lambda device: object()
    g._STREAM_FACTORY[0] = lambda device: object()
    try:
        g.SHARED_POOL = 1
        g.clear_shared_pools()
        first = g.capture_resources('xpu:0')[0]
        assert g.retire_pool_if_unowned('xpu:0') is True                 # first graph reset: handle retired
        second = g.capture_resources('xpu:0')[0]
        assert second is not first                                       # the retry gets a fresh pool
        g.pool_owned('xpu:0')
        assert g.retire_pool_if_unowned('xpu:0') is False                # other graphs hold it: kept
        assert g.capture_resources('xpu:0')[0] is second
    finally:
        g.SHARED_POOL, g._POOL_FACTORY[0], g._STREAM_FACTORY[0] = saved
        g.clear_shared_pools()
    src = (HERE / 'ltx_graph_capture.py').read_text()
    assert "diag['pool_retired'] = bool(pool is not None and retire_pool_if_unowned(self.device))" in src
    assert src.count('retire_pool_if_unowned(self.device)') >= 4
    # freeze: chain-check room, release, floor judged on the second reading
    G = 2**30
    assert n.chain_room({'xpu:0': 3 * G}, {'xpu:0': int(2.6 * G)}) != {}
    assert n.chain_room({'xpu:0': 3 * G}, {'xpu:0': int(2.6 * G)}, margin=0) == {}
    node_src = (HERE / 'pipeline_sampler_node.py').read_text()
    i_check = node_src.index('chain_ok, chain = capture.chain_check(routes, registry, _sample_worker_idents())')
    i_rel = node_src.index('            _release_cached()\n            free = _read_free()')
    i_verdict = node_src.index('ok, outcome = freeze_verdict(free, pipeline.busy(), coverage_ok and batch_ok, missing=missing)', i_rel)
    i_freeze = node_src.index('capture.CAPTURES_FROZEN[0] = True')
    assert i_check < i_rel < i_verdict < i_freeze
    # freeze wiring and default-off packet equivalence
    node = (HERE / 'pipeline_sampler_node.py').read_text()
    assert "outcome_if_fail = 'chain-check-failed'" in node and "outcome_if_fail = 'chain-check-no-room'" in node
    assert "ok, outcome = False, (outcome_if_fail" in node and "'chain_check': chain" in node
    if P96.is_dir():
        m96 = json.loads((P96 / 'manifest.json').read_text())
        m95 = json.loads((P95 / 'manifest.json').read_text())
        for section in ('sampler_placement', 'decode_placement', 'health_admission',
                        'decode_child', 'gil_probe', 'host_residency'):
            assert m96[section] == m95[section], section
        tw96 = dict(m96['text_window'])
        tw96['text_mode_overrides'] = {k: v for k, v in tw96['text_mode_overrides'].items()
                                       if k in m95['text_window']['text_mode_overrides']}
        assert tw96 == m95['text_window']                    # only the new arms were added
        assert m96['sampler_shared_pool']['default'] == 0 and m96['sampler_shared_pool']['choices'] == [0, 1]
    hr = load_script('hr96p', 'worker-headroom-96.py')
    # review 2, finding 2: first pooled worker = the private-pool bound; later = measured x 1.25 + 0.25
    assert hr.worker_cost('two-way', 2, pool=1) == hr.worker_cost('two-way', 2, pool=0)
    assert hr.plan('two-way', 1, 2, 1) == hr.plan('two-way', 1, 2, 0)[:1] + (dict(hr.plan('two-way', 1, 2, 0)[1], shared_pool=1),)
    G = 2**30
    prev = {'xpu:0': 7 * G, 'xpu:1': 9 * G, 'xpu:2': 11 * G, 'xpu:3': 14 * G}
    now = {'xpu:0': 6 * G, 'xpu:1': 8 * G, 'xpu:2': 11 * G, 'xpu:3': 14 * G}
    est, basis, bound, measured = hr.worker_estimate('two-way', 2, 1, prev, now)
    assert measured == {'xpu:0': 1.0, 'xpu:1': 1.0, 'xpu:2': 0.0, 'xpu:3': 0.0} and 'measured' in basis
    assert est == {'xpu:0': 1.5, 'xpu:1': 1.5, 'xpu:2': 0.0, 'xpu:3': 0.0}, est
    assert hr.worker_estimate('two-way', 2, 1, None, now)[1] == 'private-pool bound'
    assert hr.worker_estimate('two-way', 2, 0, prev, now)[1] == 'private-pool bound'   # pool off: never measured
    assert hr.live(now, 'two-way', 2, pool=1, prev_free=prev)[0] is True              # 6 >= 2 + 1.5
    assert hr.live(now, 'two-way', 2, pool=1)[0] is False                             # bound: 6 < 2 + 5.72
    assert not hasattr(hr, 'POOL_CARD_GIB_B1')
    assert hr.worker_cost('two-way', 1, pool=0) == hr.worker_cost('two-way', 1)
    sh = (HERE / 'run-campaign-96.sh').read_text()
    assert 'POOL=${4:-0}' in sh and 'PSUF=-p1 ; PBASE=300000' in sh and 'LTX_SAMPLER_SHARED_POOL' in sh
    assert 'worker-headroom-96.py plan $LAYOUT $WORKERS $BATCH $POOL' in sh
    assert '$LAYOUT $BATCH $POOL "${PREV[@]}"' in sh and 'room$((k - 1)).json' in sh
    # pooled index bases disjoint from unpooled and from each other
    bases = sorted(pb + 1000 * (12 * li + 3 * (w - 1) + bi) for pb in (264000, 300000)
                   for li in range(3) for w in range(1, 5) for bi in range(3))
    assert all(y - x >= 1000 for x, y in zip(bases, bases[1:]))


case('shared graph pool: allowlist, per-(device, thread) pool/stream, handles cleared, chain check, default off', shared_pool_case)

def client_end_to_end_case():
    """Review 2, finding 3: the client's whole row path (real main(), stand-in server and
    comparator, a temporary root) for a batch-1 arm, a reference arm (--no-oracle), a proof
    arm and a timed arm; plus a duplicate emission (exit 12) and a mismatch (exit 3)."""
    import tempfile
    import io
    import contextlib
    chk = load_script('chk96e', 'check-batch-proof-96.py')

    def run(arm, count, batch, order, no_oracle=False, sd=None, dd=None, dup_at=None, mismatch=False):
        tmp = tempfile.mkdtemp(prefix='p96-client-')
        root = Path(tmp)
        server_run = root / 'run'
        server_run.mkdir()
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        (server_run / 'server-identity.json').write_text(json.dumps({'boot_id': boot, 'pid': os.getpid()}))
        (server_run / 'server-args.json').write_text('{}')
        (root / 'model-verification.json').write_text(json.dumps({'status': 'passed'}))
        fixtures = [{'id': IDS[k], 'prompt': 'prompt %d' % k, 'seed': 100 + k, 'reference': 'ref-' + IDS[k]}
                    for k in range(10)]
        for f in fixtures:
            (root / 'output/validation' / f['reference']).mkdir(parents=True)
            (root / 'output/validation' / f['reference'] / 'summary.json').write_text('{}')
            (root / 'output/validation' / f['reference'] / 'tensors.safetensors').write_text('x')
            (root / 'requests' / f['reference']).mkdir(parents=True)
            (root / 'requests' / f['reference'] / 'history.json').write_text('{}')
        fx_path = root / 'fx.json'
        fx_path.write_text(json.dumps({'fixtures': fixtures}))
        graph_path = P96 / 'graphs' / ('graph-capture-all48-%s.json' % arm)
        graph = json.loads(graph_path.read_text())
        sd = graph['428']['inputs']['depth'] if sd is None else sd
        dd = graph['426']['inputs']['depth'] if dd is None else dd
        base = 980000
        if batch > 1:
            _rows, recs, pairs = simulate_arm(batch, sd, count, b.order_for(order, batch, count), base,
                                              decode_depth=dd)
        else:
            recs, pairs = [], []
            for i in range(count):
                e = i - sd
                recs.append({'detail': {'emitted_index': base + e if e >= 0 else -1}})
                d = e - dd
                pairs.append((base + e if e >= 0 else -1, base + d if d >= 0 else -1))
        if dup_at is not None:
            pairs[dup_at] = pairs[dup_at - 1]
        state = {'n': 0, 'ids': {}}

        class Resp:
            def __init__(self, body):
                self.body = json.dumps(body).encode()

            def read(self):
                return self.body

            def __enter__(self):
                return self

            def __exit__(self, *e):
                return False

        def urlopen(req, timeout=None):
            url = req.full_url
            if url.endswith('/queue'):
                return Resp({'queue_running': [], 'queue_pending': []})
            if url.endswith('/prompt'):
                g = json.loads(req.data)['prompt']
                i = state['n']
                state['n'] += 1
                name = g['428']['inputs']['run_name']
                assert g['428']['inputs']['clip_index'] == base + i
                if 'stream_last' in g['428']['inputs']:
                    assert g['428']['inputs']['stream_last'] == (1 if i == count - 1 else 0)
                (server_run / ('pipeline-sampler-%s.json' % name)).write_text(json.dumps(recs[i]))
                (server_run / ('pipeline-decode-%s.json' % name)).write_text(json.dumps(
                    {'detail': {'emitted_index': pairs[i][1], 'pending_after': [1]}}))
                pid = 'p%d' % i
                state['ids'][pid] = i
                return Resp({'prompt_id': pid})
            pid = url.rsplit('/', 1)[1]
            i = state['ids'][pid]
            return Resp({pid: {'status': {'completed': True, 'status_str': 'success', 'messages': [
                ['execution_start', {'timestamp': 1e6 + 1000 * i}],
                ['execution_success', {'timestamp': 1e6 + 1000 * i + 900}]]}}})

        def fake_run(cmd, capture_output=True, text=True, timeout=None):
            out = Path(cmd[cmd.index('--output') + 1])
            out.write_text(json.dumps({'status': 'passed', 'comparisons': {
                k: {'bitwise_equal': not mismatch} for k in ('images', 'waveform', 'video_latent', 'audio_latent')}}))
            return types.SimpleNamespace(returncode=0, stderr='')
        saved = (CLIENT.ROOT, CLIENT.urllib.request.urlopen, CLIENT.subprocess.run)
        CLIENT.ROOT = root
        CLIENT.urllib.request.urlopen = urlopen
        CLIENT.subprocess.run = fake_run
        try:
            argv = ['e2e-' + arm[-8:].strip('-').replace('_', '-'), '--graph', str(graph_path), '--arm', arm,
                    '--server-run', str(server_run), '--count', str(count), '--index-base', str(base),
                    '--out', str(root / 'out'), '--fixtures', str(fx_path), '--order', order, '--batch', str(batch)]
            if no_oracle:
                argv.append('--no-oracle')
            with contextlib.redirect_stdout(io.StringIO()):
                rc = CLIENT.main(argv)
            tp = json.loads((root / 'out' / (argv[0] + '-throughput.json')).read_text())
        finally:
            CLIENT.ROOT, CLIENT.urllib.request.urlopen, CLIENT.subprocess.run = saved
            import shutil
            shutil.rmtree(root, ignore_errors=True)
        return rc, tp

    rc, tp = run('pipe-samp2-tsh-win', 13, 1, 'cycle')                                       # batch-1 probe
    assert rc == 0 and tp['all_exact'] is True and tp['expected_clips'] == 10 and tp['emission_sequence_ok']
    assert [r['emitted_fixture'] for r in tp['rows'] if r['emitted_index'] >= 0] == IDS
    for batch in (2, 4):
        n_ref = len(b.ORDERS[batch]['ref']) + b.serial_depth(batch) + 2
        rc, ref = run('pipe-samp2-tsh-rep-wlean-b%d-ref' % batch, n_ref, batch, 'ref', no_oracle=True)
        assert rc == 0 and ref['all_exact'] is None and ref['expected_clips'] == len(b.ORDERS[batch]['ref']), ref
        for r in ref['rows']:
            if r['emitted_index'] >= 0:
                assert r['batch']['rows'][r['batch']['slot']] == 980000 + r['emitted_index']
        occ = {}
        for r in ref['rows']:
            if r['emitted_index'] >= 0:
                occ.setdefault(r['emitted_fixture'], []).append(
                    {'slot': r['batch']['slot'], 'neighbour_fixtures': r['batch']['neighbour_fixtures']})
        prereg = {'batch': batch, 'campaign': 't', 'fixtures': [
            {'id': i, 'reference': 'ref-' + i, 'arrangement': {'occurrences': occ[i]}} for i in IDS]}
        rc, pn = run('pipe-samp2-tsh-rep-wlean-b%d-ref' % batch, n_ref, batch, 'proof-neighbours')
        assert rc == 0 and pn['all_exact'] is True
        assert chk.evaluate(prereg, pn, 'neighbours', len(b.ORDERS[batch]['ref']))['passed']
        arm = 'pipe-samp2-tsh-rep-wlean-b%d-w1' % batch
        rc, tm = run(arm, 40, batch, 'shift')
        k = 40 - b.timed_depth(1, batch) - 2
        assert rc == 0 and tm['expected_clips'] == k and chk.evaluate(prereg, tm, 'timed', k)['passed']
        rc, _tp = run(arm, 40, batch, 'shift', dup_at=30)
        assert rc == 12, rc                                                               # duplicate emission
        rc, bad = run(arm, 40, batch, 'shift', mismatch=True)
        assert rc == 3 and bad['all_exact'] is False


case('client end to end (real main, stand-in server): batch-1, reference, proof, timed; duplicate and mismatch fail',
     client_end_to_end_case)


def second_run_summary_case():
    """Review 2, finding 4: with references already present the reference arm did not run;
    the summary must not ask for it, and passes on the proof and timed arms."""
    sh = (HERE / 'run-campaign-96.sh').read_text()
    a = sh.index('summary_args() {')
    fn = sh[a:sh.index('\n}\n', a) + 3]
    def args(batch, ref_ran):
        out = subprocess.run(['bash', '-c', fn + '\nBATCH=%d; TAG=t; REF_RAN=%d; summary_args' % (batch, ref_ran)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return out.stdout.split()
    assert 'f96-t-ref:reference' in args(2, 1) and '--require-proof' in args(2, 1)
    second = args(2, 0)
    assert 'f96-t-ref:reference' not in second and 'f96-t-proofn:f96-t-timed' in second and '--require-proof' in second
    assert 'f96-t-probe:placement-probe' in args(1, 0)
    assert '$(summary_args)' in sh
    sm = load_script('sum96b', 'summarize-campaign-96.py')
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        run, out = Path(tmp) / 'run', Path(tmp) / 'out'
        run.mkdir(); out.mkdir()
        fx_file = Path(tmp) / 'fx.json'
        fx_file.write_text(json.dumps({'fixtures': [{'id': i} for i in IDS]}))
        for prefix in ('f96-t-proofn', 'f96-t-proofs', 'f96-t-timed'):
            order = [IDS[x] for x in b.order_for('ref', 2, 13)]
            rows = []
            for i in range(13):
                name = '%s-%02d' % (prefix, i)
                se = i - 1
                (run / ('pipeline-sampler-%s.json' % name)).write_text(json.dumps({'detail': {
                    'emitted_index': (500 + se) if se >= 0 else -1,
                    'emitted_context_sentry': {'stage_a_context_sha256': 'A' + order[se],
                                               'stage_b_context_sha256': 'B' + order[se]} if se >= 0 else None}}))
                de = i - 3
                rows.append({'prompt': name, 'index': i, 'emitted_index': de if de >= 0 else -1, 'fill': de < 0,
                             'emitted_fixture': order[de] if de >= 0 else None, 't_done': 1000.0 + i,
                             'reference': ('ref-' + order[de]) if de >= 0 else None, 'exact': True})
            (out / ('%s-throughput.json' % prefix)).write_text(json.dumps(
                {'rows': rows, 'index_base': 500, 'fixture_order': order, 'batch': 2}))
        for name in ('proof-neighbours.json', 'proof-slots.json', 'proof-timed.json'):
            (out / name).write_text(json.dumps({'passed': True}))
        base = ['--run', str(run), '--out', str(out), '--batch', '2', '--fixtures', str(fx_file)]
        assert sm.main(base + second) == 0                                   # second run: passes
        assert sm.main(base + args(2, 1)) == 3                               # the old request: absent ref arm


case('second run (references present): the summary does not request the reference arm and passes',
     second_run_summary_case)

def calibration_case():
    """Pooled admission from an earlier run's measurement of the same packet and layout."""
    import tempfile
    hr = load_script('hr96c', 'worker-headroom-96.py')
    G = 2**30
    M = 'a' * 64
    before = {'xpu:0': int(7 * G), 'xpu:1': int(9 * G), 'xpu:2': int(11 * G), 'xpu:3': int(14 * G)}
    after = {'xpu:0': int(6.5 * G), 'xpu:1': int(8.4 * G), 'xpu:2': int(11 * G), 'xpu:3': int(14 * G)}
    rec = hr.calibrate(before, after, 'two-way', 1, 1, M)
    assert rec['per_card_gib'] == {'xpu:0': 0.5, 'xpu:1': 0.6, 'xpu:2': 0.0, 'xpu:3': 0.0} and rec['shared_pool'] == 1
    # third review: the identity fields are added by main(); a receipt without them is refused (below)
    bare = dict(rec)
    rec = dict(rec, source_identity_sha256='e' * 64, source_identity_match=True)
    # a partial or non-finite reading is never a measurement (no silent zero charge)
    assert hr.measured_cost({k: v for k, v in before.items() if k != 'xpu:1'}, after) is None
    assert hr.measured_cost(before, dict(after, **{'xpu:0': float('nan')})) is None
    assert hr.measured_cost(before, {'xpu:0': after['xpu:0']}) is None
    assert hr.worker_estimate('two-way', 2, 1, before, {'xpu:0': after['xpu:0']}, None)[1] == 'private-pool bound'
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def put(dirname, **over):
            d = root / dirname
            d.mkdir(parents=True, exist_ok=True)
            r = dict(rec, **over)
            (d / 'pool-calibration.json').write_text(json.dumps(r))
            return str(d / 'pool-calibration.json')
        assert hr.find_calibration(str(root), M, 'two-way', 2)[0] is None             # nothing yet: bound
        put('two-way-w2-b1-p1', packet_manifest_sha256='b' * 64)                      # other packet
        put('shard4-a-w2-b1-p1', layout='shard4-a')                                   # other layout (other dir)
        put('two-way-w2-b1', shared_pool=0)                                           # pool-off dir: not searched
        put('two-way-w3-b1-p1', shared_pool=0)                                        # pool flag off
        put('two-way-w2-b4-p1', batch=4)                                              # larger batch than 2
        put('two-way-w5-b1-p1', per_card_gib={'xpu:0': 0.5, 'xpu:1': 0.6})                   # partial figures
        put('two-way-w6-b1-p1', per_card_gib=dict(rec['per_card_gib'], **{'xpu:1': float('inf')}))  # not finite
        put('two-way-w7-b1-p1', batch=0)                                              # batch not positive
        (root / 'two-way-w8-b1-p1').mkdir()
        (root / 'two-way-w8-b1-p1' / 'pool-calibration.json').write_text(json.dumps(bare))  # no source identity
        found = hr.find_calibration(str(root), M, 'two-way', 2)
        assert found[0] is None and len(found[1]) == 7, found       # all refused (other layout dir not searched)
        assert sum('partial or not finite' in r for r in found[1]) == 2 and \
            sum('not shown to be from one server run' in r for r in found[1]) == 1 and \
            sum('not a positive integer' in r for r in found[1]) == 1, found
        good = put('two-way-w4-b1-p1', written_unix=100.0)
        newer = put('two-way-w4-b2-p1', batch=2, written_unix=50.0,
                    per_card_gib={'xpu:0': 1.0, 'xpu:1': 1.1, 'xpu:2': 0.0, 'xpu:3': 0.0})
        rec_b, path = hr.find_calibration(str(root), M, 'two-way', 2)
        assert path == newer and rec_b['batch'] == 2                                  # largest batch <= current wins
        assert hr.find_calibration(str(root), M, 'two-way', 1)[1] == good             # batch 2 ignored at batch 1
        put('two-way-w1-b1-p1', written_unix=200.0)
        assert hr.find_calibration(str(root), M, 'two-way', 1)[1].endswith('two-way-w1-b1-p1/pool-calibration.json')
        assert hr.find_calibration(str(root), None, 'two-way', 1)[0] is None
        # arithmetic: measured x (batch / cal batch) x 1.25 + 0.25 on cards with blocks
        cal = hr.find_calibration(str(root), M, 'two-way', 1)
        cost = hr.calibrated_cost('two-way', 4, cal[0])
        assert abs(cost['xpu:0'] - (0.5 * 4 * 1.25 + 0.25)) < 1e-9 and abs(cost['xpu:1'] - (0.6 * 4 * 1.25 + 0.25)) < 1e-9
        assert cost['xpu:2'] == 0.0 and cost['xpu:3'] == 0.0
        est, basis, bound, measured = hr.worker_estimate('two-way', 4, 1, None, after, cal)
        assert est == cost and basis.startswith('calibration ') and measured is None
        # an in-run measurement wins over calibration; pool off never uses either
        assert 'measured' in hr.worker_estimate('two-way', 4, 1, before, after, cal)[1]
        assert hr.worker_estimate('two-way', 4, 0, None, after, cal)[1] == 'private-pool bound'
        assert hr.worker_estimate('two-way', 4, 1, None, after, (None, []))[1] == 'private-pool bound'
        # the receipts record the basis (live and plan through main(), as the runner calls them)
        recp = root / 'room1.json'
        recp.write_text(json.dumps({'free_bytes': {k: int(9 * G) for k in before}}))
        import io
        import contextlib
        for argv, key in ((['x', 'live', str(recp), 'two-way', '2', '1', '--manifest', M,
                            '--calibration-root', str(root)], 'room_for_one_more_worker'),
                          (['x', 'plan', 'two-way', '2', '2', '1', '--manifest', M, '--calibration-root', str(root)],
                           'room_for_first_worker')):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = hr.main(argv)
            out = json.loads(buf.getvalue())
            assert rc == 0 and out[key] is True and out['basis'].startswith('calibration ') and \
                out['basis'].count(newer) == 1, out
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hr.main(['x', 'live', str(recp), 'two-way', '2', '1', '--manifest', 'c' * 64,
                     '--calibration-root', str(root)])
        assert json.loads(buf.getvalue())['basis'] == 'private-pool bound'           # manifest mismatch: bound
        outp = root / 'cal-out.json'
        rb, ra = root / 'room-before.json', root / 'room-after.json'
        rb.write_text(json.dumps({'free_bytes': before, 'server_identity_sha256': 'f' * 64, 'time': 10.0}))
        ra.write_text(json.dumps({'free_bytes': after, 'server_identity_sha256': 'f' * 64, 'time': 20.0}))
        with contextlib.redirect_stdout(io.StringIO()):
            assert hr.main(['x', 'calibrate', str(rb), str(ra), 'two-way', '1', '1', '--manifest', M,
                            '--out', str(outp)]) == 0
        made = json.loads(outp.read_text())
        assert made['schema'] == 'ltx.pool-calibration-96.v1' and made['source_identity_match'] is True and \
            made['source_identity_sha256'] == 'f' * 64 and made['per_card_gib']['xpu:1'] == 0.6
        other = root / 'room-other.json'
        other.write_text(json.dumps({'free_bytes': after, 'server_identity_sha256': '0' * 64, 'time': 20.0}))
        with contextlib.redirect_stdout(io.StringIO()):
            assert hr.main(['x', 'calibrate', str(rb), str(other), 'two-way', '1', '1', '--manifest', M,
                            '--out', str(root / 'no.json')]) == 2          # two different server runs
            assert hr.main(['x', 'calibrate', str(ra), str(rb), 'two-way', '1', '1', '--manifest', M,
                            '--out', str(root / 'no.json')]) == 2          # before is newer than after
            assert hr.main(['x', 'calibrate', str(recp), str(recp), 'two-way', '1', '1', '--manifest', M,
                            '--out', str(root / 'no.json')]) == 2          # no identity at all
        assert not (root / 'no.json').exists()
    sh = (HERE / 'run-campaign-96.sh').read_text()
    assert '--out $OUT/pool-calibration.json' in sh and 'calibrate $OUT/sampler-capture-coverage-f96-$TAG-room$LASTW.json' in sh
    assert sh.count('--manifest $MANIFEST') >= 3


case('pool calibration: matching receipt picked, mismatches refused, scaling and margin, basis recorded, fallback',
     calibration_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
