#!/usr/bin/env python3
"""CPU-only tests for packet 92b (decode in a child process). No XPU, no ComfyUI.

A fake child (a small script speaking ltx_decode_child's protocol) stands in
for the real one, which needs XPU and ComfyUI.

1. Framing: round trip; sha256 mismatch, short payload and EOF mid-message
   are refused.
2. Child lifecycle: ready; a request; child death mid-job fails the request
   and marks the child dead; cooperative stop exits 0 and never kills.
3. Ordered emission with a slow child through the decode node's
   pipeline-child path (images belong to the emitted clip).
4. Fail-closed probe: mismatch and low memory stop the child and keep the
   child arm refused; a matching probe admits it.
5. Stop node: refuses while the pipeline is busy, exits the child when idle.
6. 92a review fixes: a clock error cannot strand a pipeline job; the 92a
   analyzer tolerates missing arms.
"""
import hashlib
import importlib.util
import json
import multiprocessing.connection
import os
import socket
import sys
import tempfile
import textwrap
import threading
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import torch  # noqa: E402  (CPU only)
import ltx_decode_child as child  # noqa: E402

results = []
TMP = Path(tempfile.mkdtemp(prefix='ltx92b-'))


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' | ' + traceback.format_exc().splitlines()[-3].strip()))


FAKE = TMP / 'fake_child.py'
FAKE.write_text(textwrap.dedent('''
    import argparse, json, os, sys, time
    import multiprocessing.connection
    sys.path.insert(0, %r)
    import torch
    import ltx_decode_child as c
    ap = argparse.ArgumentParser()
    ap.add_argument('--fd', type=int); ap.add_argument('--config')
    a = ap.parse_args()
    cfg = json.loads(a.config)
    conn = multiprocessing.connection.Connection(a.fd)
    c.send(conn, {'op': 'ready', 'pid': os.getpid(), 'memory': {'free': cfg.get('free', 20 << 30)}, 'cpu': {}})
    jobs = 0
    while True:
        try:
            h, t = c.recv(conn, None)
        except c.ChildError:
            sys.exit(0)
        got = {e['name']: e['sha256'] for e in h['tensors']}
        if h['op'] == 'stop':
            c.send(conn, {'op': 'stopping', 'received_sha256': got}); sys.exit(0)
        if h['op'] == 'stats':
            c.send(conn, {'op': 'stats', 'received_sha256': got,
                          'memory': {'free': cfg.get('free_after', 20 << 30)}}); continue
        jobs += 1
        if cfg.get('die_on_job') == jobs:
            os._exit(9)
        v = float(t['video'].flatten()[0])
        time.sleep(cfg.get('delay', 0.0) if v %% 2 == 0 else 0.0)
        images = torch.full((2, 4, 4, 3), v + cfg.get('offset', 0.0))
        wave = torch.full((1, 2, 8), v)
        reply = {'op': 'result', 'index': h.get('index'), 'sample_rate': 48000, 'received_sha256': got,
                 'decode_s': 0.01, 'job_cpu_s': 0.001, 'memory': {'free': 20 << 30},
                 'cpu': {'process_cpu_s': 1.0 * jobs, 'wall_unix': time.time()}}
        if cfg.get('corrupt'):
            entry, raw = c.tensor_entry('images', images)
            entry['sha256'] = '0' * 64
            conn.send_bytes(json.dumps(dict(reply, protocol=c.PROTOCOL, tensors=[entry])).encode())
            conn.send_bytes(raw)
            continue
        c.send(conn, reply, {'images': images, 'waveform': wave})
''' % str(HERE)))


def reset():
    child._STATE.update(proc=None, conn=None, ready=None, error=None, stopped=False, started_unix=None)


def spawn(**cfg):
    reset()
    return child.ensure_started(dict(cfg, ready_timeout_s=60), child_script=str(FAKE))


def framing_case():
    a, b = socket.socketpair()
    ca, cb = (multiprocessing.connection.Connection(s.detach()) for s in (a, b))
    t = {'x': torch.arange(12, dtype=torch.float32).reshape(3, 4), 'e': torch.empty(0, dtype=torch.bfloat16)}
    sent = child.send(ca, {'op': 'decode', 'index': 5}, t)
    h, out = child.recv(cb, 5)
    assert h['op'] == 'decode' and torch.equal(out['x'], t['x']) and out['e'].dtype == torch.bfloat16
    assert sent['x'] == hashlib.sha256(t['x'].numpy().tobytes()).hexdigest()
    entry, raw = child.tensor_entry('x', t['x'])
    for bad_entry, bad_raw, word in ((dict(entry, sha256='0' * 64), raw, 'sha256'),
                                     (entry, raw[:-4], 'short')):
        ca.send_bytes(json.dumps({'op': 'r', 'protocol': child.PROTOCOL, 'tensors': [bad_entry]}).encode())
        ca.send_bytes(bad_raw)
        try:
            child.recv(cb, 5)
            raise AssertionError('accepted a bad payload')
        except child.ChildError as error:
            assert word in str(error), error
    ca.send_bytes(json.dumps({'op': 'r', 'protocol': child.PROTOCOL, 'tensors': [entry]}).encode())
    ca.close()
    try:
        child.recv(cb, 5)
        raise AssertionError('accepted EOF mid-message')
    except child.ChildError as error:
        assert 'closed' in str(error) or 'mid-message' in str(error), error


case('framing: round trip; sha256 mismatch, short payload, EOF mid-message refused', framing_case)


def lifecycle_case():
    st = spawn(die_on_job=2)
    assert st['ready'] and st['error'] is None and child.alive(), st
    v = {'video': torch.full((1, 4), 3.0), 'audio': torch.zeros(1, 2)}
    reply, out = child.request('decode', {'index': 3}, v, timeout=30)
    assert reply['index'] == 3 and float(out['images'].flatten()[0]) == 3.0
    try:
        child.request('decode', {'index': 4}, v, timeout=30)
        raise AssertionError('child death mid-job was not reported')
    except child.ChildError as error:
        assert 'closed' in str(error) or 'within' in str(error), error
    assert not child.alive()
    try:
        child.request('decode', {'index': 5}, v)
        raise AssertionError('dead child accepted a request')
    except child.ChildError:
        pass
    child._STATE['proc'].wait(10)
    st = spawn()
    rec = child.stop(timeout=20)
    assert rec['exited'] and rec['returncode'] == 0 and rec.get('ack') == 'stopping', rec
    st = spawn(corrupt=True)
    try:
        child.request('decode', {'index': 1}, v, timeout=30)
        raise AssertionError('corrupted reply accepted')
    except child.ChildError as error:
        assert 'sha256' in str(error), error
    child._STATE['stopped'] = False
    child._STATE['error'] = None
    rec = child.stop(timeout=20)
    assert rec['exited'], rec


case('lifecycle: ready, request, death mid-job latches, corrupt reply refused, cooperative stop', lifecycle_case)


def import_decode_node():
    if 'encoder_diagnostics' not in sys.modules:
        stub = types.ModuleType('encoder_diagnostics')
        stub._context = lambda: (_ for _ in ()).throw(RuntimeError('stub context'))
        sys.modules['encoder_diagnostics'] = stub
    import pipeline_decode_node as node
    return node


def load_capture_lock():
    text = (HERE / 'ltx_graph_capture.py').read_text()
    start, end = text.index('class CaptureReplayLock:'), text.index('CAPTURE_LOCK = CaptureReplayLock()')
    ns = {'threading': threading}
    exec(compile(text[start:end], 'lock', 'exec'), ns)
    return ns['CaptureReplayLock']()


def server_files(node, run):
    import ltx_pipeline as p
    import ltx_decode_replica as placement
    import ltx_gil_probe as gil
    shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
            for n, m in (('ltx_pipeline.py', p), ('ltx_decode_replica.py', placement), ('ltx_gil_probe.py', gil),
                         ('ltx_decode_child.py', child), ('pipeline_decode_node.py', node))}
    (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas,
                                                           'source_packet_path': str(run)}))
    os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64
    os.environ['LTX_ENCODER_RUN_DIR'] = str(run)
    identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
    node._context = lambda: (run, identity)
    torch.use_deterministic_algorithms(True)


def ordered_case():
    node = import_decode_node()
    import ltx_pipeline as p
    p.clear()
    run = Path(tempfile.mkdtemp(dir=TMP))
    server_files(node, run)
    spawn(delay=0.3)
    lock = load_capture_lock()
    saved = (node._capture_lock, node._WRITER.save_fn)
    node._capture_lock = lambda: lock
    node._WRITER.save_fn = lambda *a: 'x.mp4'
    node._CHILD_PROBE.update(passed=True, outcome='child-exact')
    node._LAST_PLACEMENT['mode'] = None
    node._failed = False
    sha = lambda t: hashlib.sha256(t.view(torch.uint8).numpy().tobytes()).hexdigest()
    try:
        base = 940000
        emitted = []
        for k in range(6):
            idx = base + k
            v = {'samples': torch.full((1, 4), float(idx))}
            a = {'samples': torch.full((1, 2), float(idx))}
            p.record_fingerprint(('sample-output', idx), {'video_finite': True, 'audio_finite': True,
                                                         'video_sha256': sha(v['samples']),
                                                         'audio_sha256': sha(a['samples'])})
            vae = types.SimpleNamespace(output_device='cpu')
            out = node.LTXPipelineDecode().apply(vae, None, v, a, 'pipeline-child', idx, 1, 'oc-%d' % k)
            r = json.loads((run / ('pipeline-decode-oc-%d.json' % k)).read_text())
            e = r['detail']['emitted_index']
            emitted.append(e)
            if e >= 0:
                assert float(out[0].flatten()[0]) == float(e), 'images of another clip emitted'
                assert r['detail']['decode_split']['slot'] == 'child'
                assert r['detail']['decode_split']['child_process_cpu_s'] is not None
        assert emitted == [-1] + [base + k for k in range(5)], emitted
        assert not lock.readers and not lock.writer
        p.collect('decode', base + 5)
        node._WRITER.queue.join()
    finally:
        node._capture_lock, node._WRITER.save_fn = saved
        node._CHILD_PROBE.update(passed=False, outcome='not run')
        node._LAST_PLACEMENT['mode'] = None
        child.stop(timeout=20)
        p.clear()


case('ordered emission through the node with a slow child; images belong to the emitted clip', ordered_case)


def probe_case():
    node = import_decode_node()
    run = Path(tempfile.mkdtemp(dir=TMP))
    server_files(node, run)
    lock = load_capture_lock()
    saved = (node._capture_lock, node._load_probe_fixtures, node._load_fixture_tensors, node._free3)
    node._capture_lock = lambda: lock
    node._free3 = lambda: 1 << 30
    sha = lambda t: hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
    fixtures = []
    for i in range(10):
        v, a = torch.full((1, 4), float(2 * i + 1)), torch.zeros(1, 2)
        fixtures.append({'fixture': 'f%d' % i, 'source': 'mem', 'v': v, 'a': a,
                         'expected': {'video_latent': sha(v), 'audio_latent': sha(a),
                                      'images': sha(torch.full((2, 4, 4, 3), float(2 * i + 1))),
                                      'waveform': sha(torch.full((1, 2, 8), float(2 * i + 1)))}})
    node._load_probe_fixtures = lambda packet: fixtures
    node._load_fixture_tensors = lambda fx: {'video_latent': fx['v'], 'audio_latent': fx['a']}
    try:
        for name, cfg, outcome, passed in (('mismatch', {'offset': 1.0}, 'child-not-exact', False),
                                           ('lowload', {'free': 1 << 30}, 'insufficient-memory', False),
                                           ('lowprobe', {'free_after': 1 << 20}, 'insufficient-memory', False),
                                           ('exact', {}, 'child-exact', True)):
            spawn(**cfg)
            node.LTXDecodeChildProbe().apply('cp-' + name)
            r = json.loads((run / ('decode-child-probe-cp-%s.json' % name)).read_text())
            assert r['outcome'] == outcome and node._CHILD_PROBE['passed'] is passed, (name, r['outcome'])
            if passed:
                assert child.alive() and 'child_stop' not in r
            else:
                assert r['child_stop']['exited'] and r['child_stop']['returncode'] == 0, r.get('child_stop')
                assert not child.alive()
        child.stop(timeout=20)
        reset()
        node.LTXDecodeChildProbe().apply('cp-none')
        r = json.loads((run / 'decode-child-probe-cp-none.json').read_text())
        assert r['outcome'] == 'child-unavailable' and not node._CHILD_PROBE['passed']
    finally:
        node._capture_lock, node._load_probe_fixtures, node._load_fixture_tensors, node._free3 = saved
        node._CHILD_PROBE.update(passed=False, outcome='not run')


case('probe: mismatch / low memory stop the child and keep the arm refused; exact admits', probe_case)


def stop_node_case():
    node = import_decode_node()
    import ltx_pipeline as p
    run = Path(tempfile.mkdtemp(dir=TMP))
    server_files(node, run)
    saved_sleep, saved_free = node.time.sleep, node._free3
    node._free3 = lambda: 1 << 30          # never touch torch.xpu in a CPU test
    spawn()
    gate = threading.Event()
    p.submit('decode', 950000, lambda: gate.wait(5))
    real_busy = p.busy
    node.pipeline.busy = lambda: 1
    try:
        node.LTXPipelineDecode  # noqa: B018
        orig = node.time.sleep
        node.time.sleep = lambda s: None
        node.LTXDecodeChildStop().apply('cs-busy')
        node.time.sleep = orig
        r = json.loads((run / 'decode-child-stop-cs-busy.json').read_text())
        assert not r['exited'] and child.alive(), r
        node.pipeline.busy = real_busy
        gate.set()
        p.collect('decode', 950000)
        node.LTXDecodeChildStop().apply('cs-idle')
        r = json.loads((run / 'decode-child-stop-cs-idle.json').read_text())
        assert r['exited'] and r['returncode'] == 0 and not child.alive(), r
    finally:
        node.pipeline.busy = real_busy
        node.time.sleep, node._free3 = saved_sleep, saved_free
        p.clear()


case('stop node: refuses while busy, child exits 0 when idle (never killed)', stop_node_case)


def review_fixes_case():
    import ltx_pipeline as p
    p.clear()
    real = time.thread_time
    time.thread_time = lambda: (_ for _ in ()).throw(OSError('clock broke'))
    try:
        p.submit('decode', 960000, lambda: 7)
        deadline = time.monotonic() + 5
        while p.busy() and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        time.thread_time = real
    value, detail = p.collect('decode', 960000)
    assert value == 7 and detail['cpu_seconds'] is None, detail
    spec = importlib.util.spec_from_file_location('analyze_gil', HERE / 'analyze-gil-92a.py')
    an = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(an)
    arms = [{'arm': 's05a', 'receipts': 3, 'lane_cpu': 3.8, 'max_thread': 0.8, 'lag_median_ms': 0.06,
             'sampler_job': 2.5, 'decode_job': 1.3},
            {'arm': 's01', 'receipts': 3, 'lane_cpu': 3.9, 'max_thread': 0.9, 'lag_median_ms': 0.06,
             'sampler_job': 2.5, 'decode_job': 1.4},
            {'arm': 's20', 'receipts': 0, 'lane_cpu': None, 'max_thread': None, 'lag_median_ms': None,
             'sampler_job': None, 'decode_job': None}]
    result, _ = an.verdict(arms, 0.064)
    assert result.startswith('INDETERMINATE') and 's05b' in result and 's20' in result, result
    empty = Path(tempfile.mkdtemp(dir=TMP))
    st = an.arm_stats(empty, empty, 'f92a-s20')
    assert st['lag_median_ms'] is None and st['lane_cpu'] is None


case('review fixes: clock error cannot strand a job; 92a analyzer tolerates missing arms', review_fixes_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
