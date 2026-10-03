#!/usr/bin/env python3
"""Offline checks for the packet-90b instrumentation. No XPU, no ComfyUI.

1. busy_window_report (extracted from ltx_graph_capture.py source, stdlib
   only, fake events): completed windows are aggregated per device/route,
   in-flight windows carry over without blocking, broken events are
   counted not raised, and repeated reports drain (the picked 6296a0e20
   version raised UnboundLocalError on its first call).
2. decode split association (with ltx_pipeline, imports torch on CPU only):
   the split reported with an emitted clip is that clip's own, recorded by
   its own job, never the still-running current clip's (99f4940fe bug).
3. analyze-phases.py on synthetic 90b receipts: occupancy, decode split,
   relative steady filter, and graceful handling of a 0-byte receipt.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
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


# --- 1. busy windows ---------------------------------------------------------
def load_busy():
    text = (HERE / 'ltx_graph_capture.py').read_text()
    start = text.index('_BUSY_LOCK = threading.Lock()')
    end = text.index('class GraphBlockRoute:')
    ns = {'threading': threading}
    exec(compile(text[start:end], 'ltx_graph_capture.py[busy]', 'exec'), ns)
    return ns


class FakeEvent:
    def __init__(self, t=None, done=True, broken=False):
        self.t, self.done, self.broken = t, done, broken

    def query(self):
        if self.broken:
            raise RuntimeError('event not created with enable_timing')
        return self.done

    def elapsed_time(self, other):
        return (other.t - self.t) * 1000.0


def busy_cases():
    ns = load_busy()
    rec, report = ns['_busy_record'], ns['busy_window_report']
    rec('xpu:0', 3, FakeEvent(0.0), FakeEvent(0.010))
    rec('xpu:0', 3, FakeEvent(1.0), FakeEvent(1.005))
    rec('xpu:1', 40, FakeEvent(0.0), FakeEvent(0.020))
    late_end = FakeEvent(2.0, done=False)
    rec('xpu:1', 41, FakeEvent(1.990), late_end)
    out = report()
    assert out['xpu:0/route3'] == {'count': 2, 'ms': 15.0}, out
    assert out['xpu:1/route40'] == {'count': 1, 'ms': 20.0}, out
    assert 'xpu:1/route41' not in out and out['_meta']['carried'] == 1, out
    late_end.done = True
    out = report()
    assert out == {'xpu:1/route41': {'count': 1, 'ms': 10.0}}, out
    assert report() == {}, 'drained report must be empty'
    rec('xpu:0', 1, FakeEvent(broken=True), FakeEvent(broken=True))
    out = report()
    assert out == {'_meta': {'carried': 0, 'dropped': 0, 'errors': 1}}, out
    for _ in range(ns['_BUSY_MAX'] + 5):
        rec('xpu:0', 2, FakeEvent(0.0), FakeEvent(0.001))
    out = report()
    assert out['xpu:0/route2']['count'] == ns['_BUSY_MAX'] and out['_meta']['dropped'] == 5, out['_meta']


case('busy windows: aggregate, carry, drain, errors, cap', busy_cases)


# --- 2. decode split association --------------------------------------------
def split_cases():
    sys.path.insert(0, str(HERE))
    import ltx_pipeline as pipeline
    pipeline.clear()

    def node_prompt(decode_index, depth=1):
        # Mirrors LTXPipelineDecode's pipeline branch (packet 90b).
        def decode_job(decode_index=decode_index):
            timing = {}
            time.sleep(0.01)
            timing['vae_s'] = round(decode_index / 1000.0, 4)   # tags the job by its index
            timing['save_s'] = 0.001
            pipeline.record_fingerprint(('decode-split', decode_index), timing)
            return ('clip', decode_index)

        out, detail = pipeline.run_behind('decode', decode_index, depth, decode_job)
        split = (pipeline.fingerprint(('decode-split', detail['emitted_index']))
                 if detail.get('emitted_index', -1) >= 0 else None)
        return out, detail, split

    base = 700100
    out, detail, split = node_prompt(base)
    assert out is None and detail['emitted_index'] == -1 and split is None, (detail, split)
    for k in range(1, 6):
        out, detail, split = node_prompt(base + k)
        emitted = detail['emitted_index']
        assert out == ('clip', emitted) and emitted == base + k - 1, (out, detail)
        assert split == {'vae_s': round(emitted / 1000.0, 4), 'save_s': 0.001}, (emitted, split)
    pipeline.clear()


case('decode split belongs to the emitted clip', split_cases)


# --- 3. analyzer on synthetic 90b receipts ----------------------------------
def analyzer_cases():
    base = 900000
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        t0 = 1_800_000_000.0
        for n in range(12):
            clip = base + n
            emitted = clip - 3 if n >= 3 else -1
            det = {'emitted_index': emitted, 'primed': n >= 3, 'stage_seconds': 2.7}
            rcpt = {'clip_index': clip, 'detail': det, 'written_unix': t0 + 1.5 * n}
            if n >= 3:
                det['emitted_phases'] = {
                    'concat_a->sample_a': {'cpu_s': 1.7, 'xpu0_ms': 1700.0, 'xpu1_ms': 1690.0},
                    'separate_a->upsample': {'cpu_s': 0.03},
                    'concat_b->sample_b': {'cpu_s': 0.85, 'xpu0_ms': 850.0, 'xpu1_ms': 860.0}}
                rcpt['route_busy_ms'] = {'xpu:0/route0': {'count': 100, 'ms': 1200.0},
                                         'xpu:1/route47': {'count': 100, 'ms': 900.0}}
            (run / f'pipeline-sampler-t90-endure-{n:02d}.json').write_text(json.dumps(rcpt))
            ddet = {'emitted_index': emitted, 'stage_seconds': 1.6}
            if emitted >= 0:
                ddet['decode_split'] = {'vae_s': 1.2, 'save_s': 0.3}
            (run / f'pipeline-decode-t90-endure-{n:02d}.json').write_text(
                json.dumps({'clip_index': clip, 'detail': ddet}))
        (run / 'pipeline-sampler-t90-endure-12.json').write_text('')   # freeze-zeroed
        res = subprocess.run([sys.executable, '-B', str(HERE / 'analyze-phases.py'), str(run), 't90-endure'],
                             capture_output=True, text=True, timeout=60)
        out = res.stdout
        assert res.returncode == 0, res.stderr
        assert f'index base {base}' in out, out
        # receipts 03..11 emit clips 0..8; skip 2 -> clips 2..8 = 7 steady
        assert 'with phases: 9 (steady 7)' in out, out
        # 7 steady receipts 1.5 s apart -> 9.0 s wall; 6 counted intervals
        assert 'wall 9.0s' in out, out
        assert ' 80.0%' in out and ' 60.0%' in out, out          # 6*1.2/9, 6*0.9/9
        assert 'save share 20.0%' in out, out
        assert 'decode receipts: 12 (steady emitted 7)' in out, out


case('analyzer: occupancy, split, relative steady filter, 0-byte receipt', analyzer_cases)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
