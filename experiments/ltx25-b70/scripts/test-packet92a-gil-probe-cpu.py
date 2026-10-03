#!/usr/bin/env python3
"""CPU-only tests for packet 92a's interpreter-contention instruments.

1. Lock-wait probe: starts once, drains a consistent histogram, reports its
   own CPU, and percentiles read the histogram correctly.
2. Per-thread CPU snapshot: names lane threads, sees a CPU-burning thread.
3. Never raise: every public helper survives a broken environment.
4. Knob: refuses while pipeline jobs are queued/running, applies once idle,
   refuses out-of-range values; restore_default puts back 5 ms.
5. ltx_pipeline: per-job cpu_seconds in collect detail; busy() counts only
   queued/running jobs, not finished uncollected tails.
6. Nodes: the knob node writes a receipt and refuses while busy; a latched
   decode failure restores the 5 ms default; receipts carry the switch interval.
7. Analyzer: verdict logic on synthetic arms (confirm / refute / indeterminate).
"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import torch  # noqa: E402,F401  (CPU only; nothing here touches torch.xpu)
import ltx_gil_probe as gil  # noqa: E402

results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' | ' + traceback.format_exc().splitlines()[-3].strip()))


def probe_case():
    assert gil.start_probe() and gil.start_probe()
    names = [t.name for t in threading.enumerate()]
    assert names.count('ltx-gil-probe') == 1, names
    gil.drain_lag()
    time.sleep(0.6)
    d = gil.drain_lag()
    assert d['samples'] > 100 and sum(d['counts']) == d['samples'], d['samples']
    assert d['probe_cpu_s_total'] < 0.6, d   # the probe must stay cheap
    counts = [0] * (len(gil.EDGES_US) + 1)
    counts[gil._bucket(50.0)] += 90
    counts[gil._bucket(5000.0)] += 10
    assert gil.percentile_us(counts, 0.5) <= 60 and gil.percentile_us(counts, 0.95) >= 5000
    assert gil.percentile_us([0] * len(counts), 0.5) is None


case('probe: single thread, consistent drain, cheap, percentiles', probe_case)


def snapshot_case():
    stop = threading.Event()

    def burn():
        x = 0
        while not stop.is_set():
            x += 1
    t = threading.Thread(target=burn, name='ltx-test-burn')
    t.start()
    gil.mark_lane_thread('prompt')
    s0 = gil.cpu_snapshot()
    time.sleep(0.6)
    s1 = gil.cpu_snapshot()
    stop.set()
    t.join()
    rows = {r['name']: (tid, r) for tid, r in s1['threads'].items()}
    assert 'ltx-gil-probe' in rows and 'lane-prompt:prompt' in rows, sorted(rows)
    tid, row = rows['ltx-test-burn']
    burned = row['cpu_s'] - s0['threads'][tid]['cpu_s']
    assert burned >= 0.2, burned
    assert s1['wall_unix'] > s0['wall_unix'] and s1['process_cpu_s'] >= s0['process_cpu_s']


case('cpu snapshot: lane names, a busy thread accrues CPU', snapshot_case)


def never_raise_case():
    real_listdir = gil.os.listdir
    gil.os.listdir = lambda p: (_ for _ in ()).throw(OSError('no proc'))
    try:
        snap = gil.cpu_snapshot()
        assert 'error' in snap, snap
        rep = gil.report()
        assert 'switch_interval_s' in rep and 'error' in rep['cpu']
    finally:
        gil.os.listdir = real_listdir
    real = gil.sys.setswitchinterval
    gil.sys.setswitchinterval = lambda v: (_ for _ in ()).throw(RuntimeError('nope'))
    try:
        assert gil.restore_default('x') is False
        r = gil.set_switch_interval(0.002, lambda: 0)
        assert r['applied'] is False and r['reason'].startswith('error'), r
    finally:
        gil.sys.setswitchinterval = real
    r = gil.set_switch_interval(0.002, lambda: (_ for _ in ()).throw(RuntimeError('busy broke')))
    assert r['applied'] is False and 'busy broke' in r['reason'], r
    gil.mark_lane_thread(object())   # odd input: swallowed


case('never raise: broken /proc, broken setswitchinterval, broken busy()', never_raise_case)


def knob_case():
    sys.setswitchinterval(0.005)
    state = {'n': 3}

    def busy():
        state['n'] -= 1
        return max(0, state['n'])
    r = gil.set_switch_interval(0.001, busy, wait_s=10, poll_s=0.01, sleep=lambda s: None)
    assert r['applied'] and sys.getswitchinterval() == 0.001 and r['waited_s'] > 0, r
    r = gil.set_switch_interval(0.02, lambda: 2, wait_s=0.05, poll_s=0.01, sleep=lambda s: None)
    assert not r['applied'] and 'busy' in r['reason'] and sys.getswitchinterval() == 0.001, r
    for bad in (0.0, 1.0, 'x'):
        r = gil.set_switch_interval(bad, lambda: 0)
        assert not r['applied'] and sys.getswitchinterval() == 0.001, (bad, r)
    assert gil.restore_default('test') and sys.getswitchinterval() == 0.005


case('knob: refuses while busy, applies when idle, range-checked; restore to 5 ms', knob_case)


def pipeline_case():
    import ltx_pipeline as p
    p.clear()
    gate = threading.Event()

    def job():
        x = 0
        t0 = time.monotonic()
        while time.monotonic() - t0 < 0.3:
            x += 1
        gate.wait(5)
        return x
    p.submit('decode', 930001, job)
    time.sleep(0.05)
    assert p.busy() == 1
    gate.set()
    value, detail = p.collect('decode', 930001)
    assert detail['cpu_seconds'] is not None and detail['cpu_seconds'] >= 0.2, detail
    p.submit('decode', 930002, lambda: 1)
    time.sleep(0.2)
    assert p.busy() == 0 and p.pending('decode') == [930002], 'finished tail must not count as busy'
    p.clear()


case('pipeline: per-job cpu_seconds, busy() ignores finished tails', pipeline_case)


def import_decode_node():
    if 'encoder_diagnostics' not in sys.modules:
        stub = types.ModuleType('encoder_diagnostics')
        stub._context = lambda: (_ for _ in ()).throw(RuntimeError('stub context'))
        sys.modules['encoder_diagnostics'] = stub
    import pipeline_decode_node as node
    return node


def node_case():
    node = import_decode_node()
    import ltx_pipeline as p
    import ltx_decode_replica as placement
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64
        identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
        shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                for n, m in (('ltx_pipeline.py', p), ('ltx_decode_replica.py', placement),
                             ('ltx_gil_probe.py', gil), ('pipeline_decode_node.py', node))}
        (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas}))
        node._context = lambda: (run, identity)
        torch.use_deterministic_algorithms(True)
        real_set = gil.set_switch_interval
        node.gil.set_switch_interval = lambda s, busy: real_set(s, busy, wait_s=0.2, poll_s=0.05)
        try:
            out = node.LTXSchedulerKnob().apply(1.0, 'knob-a')
            r = json.loads((run / 'scheduler-knob-knob-a.json').read_text())
            assert r['knob']['applied'] and abs(sys.getswitchinterval() - 0.001) < 1e-9, r['knob']
            assert 'lag' in r['gil'] and 'threads' in r['gil']['cpu'] and 'applied' in out['ui']['text'][0]
            gate = threading.Event()
            p.submit('decode', 931000, lambda: gate.wait(5))
            out = node.LTXSchedulerKnob().apply(20.0, 'knob-b')
            r = json.loads((run / 'scheduler-knob-knob-b.json').read_text())
            assert not r['knob']['applied'] and 'busy' in r['knob']['reason'] and 'REFUSED' in out['ui']['text'][0]
            assert abs(sys.getswitchinterval() - 0.001) < 1e-9
            gate.set()
            p.collect('decode', 931000)
            # a latched decode failure restores the default
            try:
                node.LTXPipelineDecode().apply(None, None, {}, {}, 'bogus-mode', 1, 1, 'latch-a')
                raise AssertionError('bogus mode admitted')
            except RuntimeError:
                pass
            assert node._failed is True and sys.getswitchinterval() == 0.005
            r = json.loads((run / 'pipeline-decode-latch-a.json').read_text()) if (run / 'pipeline-decode-latch-a.json').exists() else None
            if r is not None:
                assert r['gil']['switch_interval_s'] in (0.001, 0.005)
        finally:
            node.gil.set_switch_interval = real_set
            node._failed = False
            sys.setswitchinterval(0.005)
            os.environ.pop('LTX_ENCODER_IDENTITY_SHA256', None)
            p.clear()


case('nodes: knob receipt, refusal while busy, latch restores 5 ms', node_case)


def receipt_case():
    node = import_decode_node()
    import ltx_pipeline as p
    import ltx_decode_replica as placement
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64
        os.environ['LTX_ENCODER_RUN_DIR'] = tmp
        identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
        shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                for n, m in (('ltx_pipeline.py', p), ('ltx_decode_replica.py', placement),
                             ('ltx_gil_probe.py', gil), ('pipeline_decode_node.py', node))}
        (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas}))
        node._context = lambda: (run, identity)
        saved = (node.decode_native, node._WRITER.save_fn)
        node.decode_native = lambda *a: (torch.zeros(1, 2, 2, 3), {'waveform': torch.zeros(1, 2, 4),
                                                                  'sample_rate': 48000}, {'wait_s': 0, 'vae_s': 0})
        node._WRITER.save_fn = lambda *a: 'x.mp4'
        node._LAST_PLACEMENT['mode'] = None
        try:
            sys.setswitchinterval(0.002)
            v = {'samples': torch.zeros(1, 4)}
            a = {'samples': torch.zeros(1, 2)}
            sha = lambda t: hashlib.sha256(t.view(torch.uint8).numpy().tobytes()).hexdigest()
            for k in range(3):
                p.record_fingerprint(('sample-output', 932000 + k), {'video_finite': True, 'audio_finite': True,
                                                                     'video_sha256': sha(v['samples']),
                                                                     'audio_sha256': sha(a['samples'])})
                node.LTXPipelineDecode().apply(None, None, v, a, 'pipeline-save', 932000 + k, 1, 'rc-%d' % k)
            r = json.loads((run / 'pipeline-decode-rc-2.json').read_text())
            assert r['gil']['switch_interval_s'] == 0.002 and 'apply_cpu_seconds' in r, sorted(r)
            assert r['detail']['cpu_seconds'] is not None, r['detail']
        finally:
            node.decode_native, node._WRITER.save_fn = saved
            sys.setswitchinterval(0.005)
            os.environ.pop('LTX_ENCODER_IDENTITY_SHA256', None)
            os.environ.pop('LTX_ENCODER_RUN_DIR', None)
            node._WRITER.queue.join()
            time.sleep(0.1)
            p.clear()


case('receipts: switch interval, apply CPU and job CPU recorded', receipt_case)


def analyzer_case():
    spec = importlib.util.spec_from_file_location('analyze_gil', HERE / 'analyze-gil-92a.py')
    an = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(an)

    def arm(name, cpu, lag, sampler, decode):
        return {'arm': name, 'lane_cpu': cpu, 'max_thread': min(cpu, 0.6), 'lag_median_ms': lag,
                'sampler_job': sampler, 'decode_job': decode}
    confirm = [arm('s05a', 0.95, 3.0, 2.6, 1.7), arm('s01', 0.95, 1.5, 2.4, 1.6),
               arm('s20', 0.95, 9.0, 2.9, 1.9), arm('s05b', 0.93, 3.2, 2.6, 1.7)]
    assert an.verdict(confirm, 0.08)[0].startswith('CONFIRMED')
    assert an.verdict(confirm, 0.5)[0].startswith('INDETERMINATE'), 'noisy idle probe must not confirm'
    refute = [arm('s05a', 0.5, 0.1, 2.6, 1.7), arm('s01', 0.5, 0.1, 2.6, 1.7),
              arm('s20', 0.5, 0.1, 2.62, 1.71), arm('s05b', 0.5, 0.1, 2.6, 1.7)]
    assert an.verdict(refute, 0.08)[0].startswith('REFUTED')
    middle = [arm('s05a', 0.75, 0.8, 2.6, 1.7), arm('s01', 0.75, 0.5, 2.55, 1.7),
              arm('s20', 0.75, 2.0, 2.7, 1.75), arm('s05b', 0.75, 0.8, 2.6, 1.7)]
    assert an.verdict(middle, 0.08)[0].startswith('INDETERMINATE')
    assert an.verdict(confirm[:2], 0.08)[0].startswith('INDETERMINATE')
    a = {'wall_unix': 0.0, 'threads': {'1': {'name': 'ltx-sample-0', 'cpu_s': 1.0},
                                       '2': {'name': 'lane-prompt:prompt', 'cpu_s': 0.0},
                                       '3': {'name': 'ltx-gil-probe', 'cpu_s': 0.0},
                                       '4': {'name': 'native:sycl', 'cpu_s': 0.0}}}
    b = {'wall_unix': 10.0, 'threads': {'1': {'name': 'ltx-sample-0', 'cpu_s': 5.0},
                                        '2': {'name': 'lane-prompt:prompt', 'cpu_s': 3.0},
                                        '3': {'name': 'ltx-gil-probe', 'cpu_s': 0.1},
                                        '4': {'name': 'native:sycl', 'cpu_s': 9.0}}}
    total, best, best_name, probe, wall = an.cpu_rates([a, b])
    assert abs(total - 0.7) < 1e-9 and abs(best - 0.4) < 1e-9 and best_name == 'ltx-sample-0'
    assert abs(probe - 0.01) < 1e-9 and wall == 10.0


case('analyzer: verdict rules and lane CPU arithmetic', analyzer_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
