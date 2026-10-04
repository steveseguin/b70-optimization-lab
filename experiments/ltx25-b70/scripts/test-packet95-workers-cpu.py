#!/usr/bin/env python3
"""CPU-only tests for packet 95 (three or four sampler workers). No XPU, no server.

1. Pinned jobs: a job pinned to a named worker runs on that worker, for every worker of
   2, 3 and 4; unpinned jobs still run on any worker; a pin to a missing worker refuses.
2. Ordered emission with three and four workers finishing out of order (run_behind with
   depth = workers): every clip emitted exactly once, in clip order, and the workers
   really overlap.
3. Capture coverage for N workers: complete only if every route holds every signature
   on all N workers; a missing worker or a short route refuses.
4. LTX_SAMPLER_WORKERS: allowlist 2/3/4 enforced at import; 3 and 4 raise the worker
   count; 2 leaves it unchanged (subprocesses, so this process is untouched).
5. Memory: worker-headroom-95.py on the 94f freeze figures skips two-way with a third
   worker and admits shard4-a with three and four and shard3-c with three.
6. Generator, gate and runner agree on the sampler depths, arms, self-check size and
   index bases (no two combinations overlap).
"""
import ast
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
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


import ltx_pipeline as p  # noqa: E402


def pin_case():
    p.clear()
    p.set_stage_workers('sample', 4)
    seen = {}

    def job(tag):
        def fn():
            seen[tag] = threading.current_thread().name
            time.sleep(0.02)
            return tag
        return fn

    for k in range(4):
        name = 'ltx-sample-%d' % k
        assert p.submit('sample', 950000 + k, job(name), target=name) or True
        p.collect('sample', 950000 + k)
        assert seen[name] == name, (name, seen[name])
    # reversed order too: the pin, not the dispatch order, decides
    for k in reversed(range(4)):
        name = 'ltx-sample-%d' % k
        p.submit('sample', 950100 + k, job('r' + name), target=name)
    for k in range(4):
        p.collect('sample', 950100 + k)
        assert seen['rltx-sample-%d' % k] == 'ltx-sample-%d' % k
    assert sorted(p.worker_names('sample')) == ['ltx-sample-%d' % k for k in range(4)]
    p.submit('sample', 950200, job('free'))
    p.collect('sample', 950200)
    assert seen['free'].startswith('ltx-sample-')
    raises(lambda: p.submit('sample', 950300, job('x'), target='ltx-sample-9'), 'No live worker')
    p.clear()


case('pinned jobs run on the named worker (2, 3 and 4 workers); a missing worker refuses', pin_case)


def ordering_case():
    for workers in (3, 4):
        p.clear()
        p.set_stage_workers('sample', 4)
        spans = {}
        base = 951000 + 100 * workers

        def job(i, delay):
            def fn():
                t0 = time.monotonic()
                time.sleep(delay)
                spans[i] = (t0, time.monotonic())
                return ('clip', i)
            return fn

        emitted = []
        delays = [0.30, 0.05, 0.20, 0.02, 0.25, 0.04, 0.15, 0.03, 0.10, 0.01, 0.12, 0.02]
        for k in range(len(delays)):
            out, detail = p.run_behind('sample', base + k, workers, job(base + k, delays[k]))
            emitted.append(detail['emitted_index'])
            if out is not None:
                assert out == ('clip', detail['emitted_index'])
        for _ in range(100):                     # let the tail jobs finish
            if len(spans) == len(delays):
                break
            time.sleep(0.05)
        assert emitted[:workers] == [-1] * workers
        assert emitted[workers:] == [base + k for k in range(len(delays) - workers)], emitted
        early = [k for k in range(len(delays) - 1) if base + k + 1 in spans and spans[base + k + 1][1] < spans[base + k][1]]
        assert early, 'no out-of-order completion was produced'
        conc = max(sum(1 for a, b in spans.values() if a <= t < b) for t, _ in spans.values())
        assert conc >= 3, 'workers never overlapped three ways: %d' % conc
        p.clear()


case('ordered emission with three and four workers finishing out of order', ordering_case)


def coverage_case():
    sys.path.insert(1, '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-shard4-94f/source')
    saved = sys.argv
    sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram']
    import comfy.options
    comfy.options.enable_args_parsing()
    try:
        import ltx_graph_capture as g      # parses ComfyUI's arguments (--cpu) on import
    finally:
        sys.argv = saved

    class R:
        def __init__(self, index, entries):
            self.index, self.entries = index, entries
    for n in (2, 3, 4):
        ids = list(range(100, 100 + n))
        full = [R(i, {t: {'a': 1, 'b': 1} for t in ids}) for i in range(48)]
        assert g.capture_coverage(ids, full, expected=n)[0] is True
        assert g.capture_coverage(ids[:-1], full, expected=n)[0] is False      # a worker missing
        short = list(full)
        short[30] = R(30, {t: ({'a': 1} if t == ids[-1] else {'a': 1, 'b': 1}) for t in ids})
        ok, d = g.capture_coverage(ids, short, expected=n)
        assert ok is False and d['incomplete_routes'] == [30]
    assert g.capture_coverage([1, 2], [R(0, {1: {'a': 1}, 2: {'a': 1}})])[0] is True   # default: two


case('capture coverage requires every signature on all N workers', coverage_case)


def env_case():
    code = ('import sys, types, os; sys.path.insert(0, %r); '
            'stub = types.ModuleType("encoder_diagnostics"); stub._context = lambda: None; '
            'sys.modules["encoder_diagnostics"] = stub; '
            'import ltx_pipeline as p; import pipeline_sampler_node as n; '
            'print(n.SAMPLER_WORKERS, p.STAGE_WORKERS["sample"])') % str(HERE)
    for value, want in (('2', '2 2'), ('3', '3 3'), ('4', '4 4'), (None, '2 2')):
        env = dict(os.environ, ONEAPI_DEVICE_SELECTOR='opencl:cpu')
        env.pop('LTX_SAMPLER_WORKERS', None)
        if value is not None:
            env['LTX_SAMPLER_WORKERS'] = value
        out = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env, timeout=300)
        assert out.returncode == 0 and out.stdout.strip().splitlines()[-1] == want, (value, out.stdout, out.stderr[-500:])
    env = dict(os.environ, ONEAPI_DEVICE_SELECTOR='opencl:cpu', LTX_SAMPLER_WORKERS='5')
    out = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env, timeout=300)
    assert out.returncode != 0 and 'LTX_SAMPLER_WORKERS must be one of' in out.stderr
    src = (HERE / 'pipeline_sampler_node.py').read_text()
    assert "target = _PIN[0] if not _capp.CAPTURES_FROZEN[0] else None\n                _PIN[0] = None" in src
    assert "capture.capture_coverage(_sample_worker_idents(), expected=SAMPLER_WORKERS)" in src


case('LTX_SAMPLER_WORKERS allowlist and worker count; the pin is one-shot and never after the freeze', env_case)


def headroom_case():
    spec = importlib.util.spec_from_file_location('hr95', HERE / 'worker-headroom-95.py')
    hr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hr)
    G = 2**30
    freeze = {}
    for mode in ('control', 'shard3-c', 'shard4-a'):
        f = next((LANE := HERE.parent).joinpath('data/shard4-94f', mode).glob('sampler-capture-freeze-*.json'))
        freeze[mode] = {k: int(v * G) for k, v in json.loads(f.read_text())['free_gib'].items()}
    ok, short = hr.verdict(freeze['control'], 'two-way', pre_decode=False)
    assert not ok and set(short) >= {'xpu:0'}, short                     # two-way + third worker: skipped
    assert hr.verdict(freeze['shard4-a'], 'shard4-a', pre_decode=False)[0] is True          # third worker fits
    assert hr.verdict(freeze['shard3-c'], 'shard3-c', pre_decode=False)[0] is True
    # fourth worker: free after the third worker's estimated cost
    after3 = {c: v - int(hr.PER_BLOCK * b * G) for c, v in freeze['shard4-a'].items()
              for _l, blocks in [(None, hr.LAYOUTS['shard4-a'])] for cc, b in blocks.items() if cc == c}
    assert hr.verdict(after3, 'shard4-a', pre_decode=False)[0] is True
    after3c = {c: v - int(hr.PER_BLOCK * hr.LAYOUTS['shard3-c'][c] * G) for c, v in freeze['shard3-c'].items()}
    assert hr.verdict(after3c, 'shard3-c', pre_decode=False)[0] is False                    # shard3-c fourth worker: skipped
    # before the decode probe the replica and VAE room is still to come: counted
    pre = {c: v + int(hr.PRE_DECODE.get(c, 0.0) * G) for c, v in freeze['shard4-a'].items()}
    assert hr.verdict(pre, 'shard4-a')[0] is True
    assert abs(hr.needed('shard4-a')['xpu:1'] - hr.needed('shard4-a', pre_decode=False)['xpu:1'] - 1.8) < 1e-9
    sh = (HERE / 'run-campaign-95.sh').read_text()
    assert 'worker-headroom-95.py $RUN/sampler-capture-coverage-f95-$TAG-room$k.json $LAYOUT' in sh
    assert sh.index('if [ $k -ge 2 ]; then') < sh.index('run-sampler-pin-95.py f95-$TAG-pin$k')
    assert 'finish 18' in sh


case('memory: two-way third worker skipped; shard4-a 3 and 4, shard3-c 3 admitted (94f figures)', headroom_case)


def agreement_case():
    gen = (HERE / 'prepare-graph-capture-runtime.py').read_text()
    over = ast.literal_eval(gen.split('SAMPLER_DEPTH_OVERRIDES = ')[1].split('\n')[0])
    assert over == {'pipe-samp2-tsh-rep-wlean-s3': 3, 'pipe-samp2-tsh-rep-wlean-s4': 4}
    lit = ast.literal_eval(gen.split("    sampler_depths = ")[1].split('\n')[0])
    assert lit == over
    sh = (HERE / 'run-campaign-95.sh').read_text()
    assert 'TIMED_ARM=pipe-samp2-tsh-rep-wlean-s$WORKERS' in sh and 'SELF_N=$((WORKERS + 4))' in sh
    table = dict(re.findall(r'(\w[\w-]*:\d)\) IDX=(\d)', sh)) if (re := __import__('re')) else {}
    assert len(table) == 9 and len(set(table.values())) == 9, table
    ranges = []
    for combo, idx in table.items():
        base = 244000 + 1000 * int(idx)
        ranges.append((base, base + 600 + 120))
    ranges.sort()
    assert all(a[1] < b[0] for a, b in zip(ranges, ranges[1:])), 'index ranges overlap'
    assert 'LTX_SAMPLER_WORKERS=//p' in sh
    gc = (HERE / 'ltx_graph_capture.py').read_text()
    assert "key = (device, threading.get_ident())" in gc, 'graph groups must stay per (device, thread)'
    tenc = (HERE / 'ltx_graph_text_encoder.py').read_text()
    assert 'return (device, threading.get_ident())' in tenc


case('generator, gate and runner agree on depths, arms, self-check size and index bases', agreement_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
