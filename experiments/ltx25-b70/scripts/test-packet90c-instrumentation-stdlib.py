#!/usr/bin/env python3
"""Offline checks for the packet-90c instrumentation. No XPU, no ComfyUI.

1. busy windows (block extracted from ltx_graph_capture.py, fake events):
   aggregation, carry without blocking, drain, error counting, cap, merged
   per-card segments on the anchor clock.
2. guard: any timing exception disables the timers once, records the text,
   and the replay is still issued exactly once and in the same position;
   LTX_BUSY_WINDOWS=0 turns the timers off without touching events. The
   real _call_native must use the guarded begin/replay/end sequence.
3. decode split association (ltx_pipeline, torch imported on CPU only):
   the split reported with an emitted clip is that clip's own.
4. done markers never raise, and write the stage/index file when they can.
5. analyze-phases.py: cross-drain merge ([5,9] then carried [0,12] = 12 s
   busy, not 16), unavailable-timing counts, no fallback when no row is
   steady, decode split, 0-byte receipt.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        results.append((name, False, repr(error)))


class FakeEvent:
    log = None
    fail_record = False

    def __init__(self, t=None, done=True, broken=False, enable_timing=None):
        self.t, self.done, self.broken = t, done, broken

    def record(self):
        if FakeEvent.fail_record:
            raise RuntimeError('record refused')
        if FakeEvent.log is not None:
            FakeEvent.log.append('event')

    def query(self):
        if self.broken:
            raise RuntimeError('event not created with enable_timing')
        return self.done

    def elapsed_time(self, other):
        return (other.t - self.t) * 1000.0


def load_busy(env='1', event_cls=FakeEvent):
    text = (HERE / 'ltx_graph_capture.py').read_text()
    start = text.index('_BUSY_LOCK = threading.Lock()')
    end = text.index('class GraphBlockRoute:')
    fake_torch = types.SimpleNamespace(xpu=types.SimpleNamespace(Event=event_cls))
    fake_os = types.SimpleNamespace(environ={'LTX_BUSY_WINDOWS': env})
    ns = {'threading': threading, 'os': fake_os, 'torch': fake_torch}
    exec(compile(text[start:end], 'ltx_graph_capture.py[busy]', 'exec'), ns)
    return ns


# --- 1. busy windows ---------------------------------------------------------
def busy_cases():
    ns = load_busy()
    rec, report = ns['_busy_record'], ns['busy_window_report']
    rec('xpu:0', 3, FakeEvent(0.0), FakeEvent(0.010))
    out = report()
    assert out['xpu:0/route3'] == {'count': 1, 'ms': 10.0} and '_devices' not in out, out
    assert out['_meta']['unplaced'] == 1, out
    ns['_busy_anchor']('xpu:0', lambda: FakeEvent(0.0))
    ns['_busy_anchor']('xpu:1', lambda: FakeEvent(0.0))
    first = ns['_BUSY_ANCHORS']['xpu:0']
    ns['_busy_anchor']('xpu:0', lambda: FakeEvent(99.0))
    assert ns['_BUSY_ANCHORS']['xpu:0'] is first, 'one anchor per card'
    rec('xpu:0', 3, FakeEvent(1.000), FakeEvent(1.010))
    rec('xpu:0', 30, FakeEvent(1.005), FakeEvent(1.015))
    late = FakeEvent(2.0, done=False)
    rec('xpu:1', 41, FakeEvent(1.990), late)
    out = report()
    d0 = out['_devices']['xpu:0']
    assert d0['windows'] == 2 and abs(d0['sum_ms'] - 20.0) < 1e-6, d0
    assert d0['segments'] == [[1000.0, 1015.0]] and d0['coalesced_gap_ms'] == 0.0, d0
    assert 'xpu:1/route41' not in out and out['_meta']['carried'] == 1, out
    late.done = True
    out = report()
    assert out['_devices']['xpu:1']['segments'] == [[1990.0, 2000.0]] and '_meta' not in out, out
    assert report() == {}, 'drained report must be empty'
    rec('xpu:0', 1, FakeEvent(broken=True), FakeEvent(broken=True))
    assert report()['_meta']['errors'] == 1
    for _ in range(ns['_BUSY_MAX'] + 5):
        rec('xpu:0', 2, FakeEvent(0.0), FakeEvent(0.001))
    out = report()
    assert out['xpu:0/route2']['count'] == ns['_BUSY_MAX'] and out['_meta']['dropped'] == 5, out['_meta']
    segs = [[float(i), i + 0.5] for i in range(10)]
    bounded, gap = ns['_bound_segments'](segs, 4)
    assert len(bounded) <= 4 and gap > 0 and bounded[0][0] == 0.0 and bounded[-1][1] == 9.5, (bounded, gap)


case('busy windows: aggregate, carry, drain, errors, cap, segments', busy_cases)


# --- 2. guard and switch ------------------------------------------------------
def guard_cases():
    src = (HERE / 'ltx_graph_capture.py').read_text()
    assert ('_busy = busy_begin(self.device)\n                entry.graph.replay()\n'
            '                busy_end(_busy, self.device, self.index)') in src, 'hot path not guarded'

    def call_native(ns, log):
        token = ns['busy_begin']('xpu:0')
        log.append('replay')
        ns['busy_end'](token, 'xpu:0', 7)

    # normal: anchor, ev0, replay, ev1
    ns = load_busy()
    log = FakeEvent.log = []
    call_native(ns, log)
    assert log == ['event', 'event', 'replay', 'event'], log
    # failure in begin: replay still issued once, timers off, text kept once
    ns = load_busy()
    log = FakeEvent.log = []
    FakeEvent.fail_record = True
    call_native(ns, log)
    FakeEvent.fail_record = False
    assert log == ['replay'], log
    call_native(ns, log)
    assert log == ['replay', 'replay'], 'disabled timers must not touch events again'
    meta = ns['busy_window_report']()['_meta']
    assert meta['disabled'].startswith('disabled after error') and 'record refused' in meta['disabled'], meta

    # failure in end (after the replay was issued): nothing re-issued
    class EndFails(FakeEvent):
        made = 0

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            EndFails.made += 1
            self.n = EndFails.made

        def record(self):
            if self.n == 3:
                raise RuntimeError('end marker refused')
            FakeEvent.log.append('event')

    ns = load_busy(event_cls=EndFails)
    log = FakeEvent.log = []
    call_native(ns, log)
    assert log == ['event', 'event', 'replay'], log
    assert 'end marker refused' in ns['busy_window_report']()['_meta']['disabled']
    # env switch: no events at all
    ns = load_busy(env='0')
    log = FakeEvent.log = []
    call_native(ns, log)
    assert log == ['replay'], log
    assert ns['busy_window_report']() == {'_meta': {'carried': 0, 'dropped': 0, 'errors': 0, 'unplaced': 0,
                                                    'disabled': 'disabled by LTX_BUSY_WINDOWS=0'}}
    FakeEvent.log = None


case('guard: first error disables, replay order unchanged; LTX_BUSY_WINDOWS=0 off', guard_cases)


# --- 3. decode split association --------------------------------------------
def split_cases():
    sys.path.insert(0, str(HERE))
    import ltx_pipeline as pipeline
    pipeline.clear()

    def node_prompt(decode_index, depth=1):
        def decode_job(decode_index=decode_index):
            timing = {'vae_s': round(decode_index / 1000.0, 4), 'save_s': 0.001}
            time.sleep(0.01)
            pipeline.record_fingerprint(('decode-split', decode_index), timing)
            return ('clip', decode_index)
        out, detail = pipeline.run_behind('decode', decode_index, depth, decode_job)
        split = (pipeline.fingerprint(('decode-split', detail['emitted_index']))
                 if detail.get('emitted_index', -1) >= 0 else None)
        return out, detail, split

    base = 700100
    out, detail, split = node_prompt(base)
    assert out is None and detail['emitted_index'] == -1 and split is None
    for k in range(1, 6):
        out, detail, split = node_prompt(base + k)
        emitted = detail['emitted_index']
        assert out == ('clip', emitted) and emitted == base + k - 1
        assert split == {'vae_s': round(emitted / 1000.0, 4), 'save_s': 0.001}, (emitted, split)
    pipeline.clear()


case('decode split belongs to the emitted clip', split_cases)


# --- 4. done markers ----------------------------------------------------------
def marker_cases():
    for name in ('pipeline_sampler_node.py', 'pipeline_decode_node.py'):
        text = (HERE / name).read_text()
        start = text.index('def write_json(path, value):')
        end = text.index('    except Exception:  # noqa: BLE001  (evidence only)\n        pass\n') + \
            len('    except Exception:  # noqa: BLE001  (evidence only)\n        pass\n')
        with tempfile.TemporaryDirectory() as tmp:
            fake_os = types.SimpleNamespace(environ={'LTX_ENCODER_RUN_DIR': tmp})
            ns = {'json': json, 'os': fake_os, 'Path': Path, 'time': time}
            exec(compile(text[start:end], name, 'exec'), ns)
            ns['done_marker']('sample', 205089, {'finite': True})
            d = json.loads((Path(tmp) / 'pipeline-done-sample-205089.json').read_text())
            assert d['stage'] == 'sample' and d['index'] == 205089 and d['finite'] is True, d
            ns['done_marker']('sample', 205089)            # exists: swallowed
            fake_os.environ.clear()
            ns['done_marker']('decode', 1)                 # no run dir: swallowed
    src = (HERE / 'pipeline_sampler_node.py').read_text()
    assert "done_marker('sample', clip_index" in src
    assert "done_marker('decode', decode_index" in (HERE / 'pipeline_decode_node.py').read_text()


case('done markers: written, never raise', marker_cases)


# --- 5. analyzer ---------------------------------------------------------------
def analyzer_module():
    spec = importlib.util.spec_from_file_location('analyze_phases', HERE / 'analyze-phases.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def busy(segments, sum_ms, **meta):
    out = {'xpu:0/route0': {'count': 1, 'ms': sum_ms},
           '_devices': {'xpu:0': {'windows': 1, 'sum_ms': sum_ms, 'segments': segments,
                                  'coalesced_gap_ms': 0.0}}}
    if meta:
        out['_meta'] = meta
    return out


def cross_drain_case():
    mod = analyzer_module()
    # drain 1 completes [5,9] s; drain 2 completes the carried window [0,12] s
    occ = mod.card_occupancy([{'route_busy_ms': busy([[5000.0, 9000.0]], 4000.0)},
                              {'route_busy_ms': busy([[0.0, 12000.0]], 12000.0)}])['xpu:0']
    assert abs(occ['union_s'] - 12.0) < 1e-9, occ           # not 16
    assert abs(occ['span_s'] - 12.0) < 1e-9 and abs(occ['sum_s'] - 16.0) < 1e-9, occ


case('analyzer: [5,9] then carried [0,12] merges to 12 s', cross_drain_case)


def write_run(run, n_prompts, base, busy_for):
    for n in range(n_prompts):
        clip = base + n
        emitted = clip - 3 if n >= 3 else -1
        det = {'emitted_index': emitted, 'primed': n >= 3, 'stage_seconds': 2.7}
        rcpt = {'clip_index': clip, 'detail': det}
        if n >= 3:
            det['emitted_phases'] = {
                'concat_a->sample_a': {'cpu_s': 1.7, 'xpu0_ms': 1700.0, 'xpu1_ms': 1690.0},
                'separate_a->upsample': {'cpu_s': 0.03},
                'concat_b->sample_b': {'cpu_s': 0.85, 'xpu0_ms': 850.0, 'xpu1_ms': 860.0}}
            rcpt['route_busy_ms'] = busy_for(n)
        (run / f'pipeline-sampler-t90-endure-{n:02d}.json').write_text(json.dumps(rcpt))
        ddet = {'emitted_index': emitted, 'stage_seconds': 1.6}
        if emitted >= 0:
            ddet['decode_split'] = {'vae_s': 1.2, 'save_s': 0.3}
        (run / f'pipeline-decode-t90-endure-{n:02d}.json').write_text(json.dumps({'clip_index': clip, 'detail': ddet}))


def analyze(run):
    return subprocess.run([sys.executable, '-B', str(HERE / 'analyze-phases.py'), str(run), 't90-endure'],
                          capture_output=True, text=True, timeout=60)


def analyzer_cases():
    base = 900000
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)

        def busy_for(n):
            if n == 7:
                return 'unavailable: RuntimeError()'
            if n == 8:
                return {'_meta': {'carried': 0, 'dropped': 0, 'errors': 0, 'unplaced': 0,
                                  'disabled': 'disabled after error: X'}}
            # 1 s busy in every 2 s, plus a fully overlapping second window
            t = n * 2000.0
            return busy([[t, t + 1000.0]], 2000.0)

        write_run(run, 12, base, busy_for)
        (run / 'pipeline-sampler-t90-endure-12.json').write_text('')   # freeze-zeroed
        res = analyze(run)
        out = res.stdout
        assert res.returncode == 0, res.stderr + out
        assert f'index base {base}' in out and 'with phases: 9 (steady 7)' in out, out
        # steady receipts 05..11; 07 and 08 unavailable -> 5 usable: n=5,6,9,10,11
        assert '[timing unavailable in 2/7 steady receipts]' in out, out
        # union 5 s; span 10000..23000 ms = 13 s; summed 10 s -> overlap 50%
        assert '      5.0      13.0      38.5%      10.0           50.0%' in out, out
        assert 'save share 20.0%' in out and 'decode receipts: 12 (steady emitted 7)' in out, out
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        write_run(run, 5, base, lambda n: busy([[0.0, 1.0]], 1.0))   # emits clips 0,1 only
        res = analyze(run)
        assert res.returncode == 2 and 'NO STEADY ROWS' in res.stdout, res.stdout
        assert 'union s' not in res.stdout and 'phase shares' not in res.stdout, res.stdout


case('analyzer: unavailable counts, occupancy, no fallback, split, 0-byte receipt', analyzer_cases)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
