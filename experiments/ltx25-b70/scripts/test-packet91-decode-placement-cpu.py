#!/usr/bin/env python3
"""CPU-only tests for packet 91/91b's decode placement. No XPU, no ComfyUI server.

1. Two decode workers: out-of-order completion still emits in clip order,
   and the two jobs really overlap.
2. Preview writer: bounded FIFO with back-pressure, private CPU copies,
   failures recorded (never raised), save markers written.
3. Fail-closed: a replica-mode request before a passed probe is refused with
   a receipt, submits nothing and does not latch the decode node.
4. Probe comparison logic: pass, one-byte replica difference, uncertified
   inputs.
5. Placement allowlist: slot_for parity, check_placement refusals,
   clone_module makes exact, unshared copies and repoints device attributes.
6. Mirror tripwire: the ComfyUI VAE.decode / VAEDecode / audio-decode lines
   the replica path mirrors are still present in the packet's ComfyUI.
"""
import hashlib
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
import torch  # noqa: E402  (CPU only; nothing here touches torch.xpu)

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' ' + traceback.format_exc().splitlines()[-3]))


# --- 1. ordering under two decode workers ------------------------------------
def ordering_case():
    import ltx_pipeline as p
    p.clear()
    p.set_stage_workers('decode', 2)
    spans = {}

    def job(i, delay):
        def fn():
            t0 = time.monotonic()
            time.sleep(delay)
            spans[i] = (t0, time.monotonic())
            return ('clip', i)
        return fn

    base = 900100
    # even clips slow (0.30 s), odd clips fast (0.05 s): clip k+1 finishes before clip k
    emitted = []
    for k in range(8):
        out, detail = p.run_behind('decode', base + k, 2, job(base + k, 0.30 if k % 2 == 0 else 0.05))
        emitted.append(detail['emitted_index'])
        if out is not None:
            assert out == ('clip', detail['emitted_index']), (out, detail)
    assert emitted[:2] == [-1, -1] and emitted[2:] == [base + k for k in range(6)], emitted
    overlapped = [k for k in range(0, 6, 2)
                  if spans[base + k + 1][0] < spans[base + k][1]]
    assert overlapped, 'two decode workers never ran concurrently: %s' % spans
    early = [k for k in range(0, 6, 2) if spans[base + k + 1][1] < spans[base + k][1]]
    assert early, 'test did not produce out-of-order completion'
    try:
        p.set_stage_workers('decode', 1)
        raise AssertionError('worker count decrease was admitted')
    except RuntimeError:
        pass
    p.clear()


case('two decode workers: out-of-order completion, in-order emission', ordering_case)


# --- import the decode node with stubs ---------------------------------------
def import_decode_node():
    if 'encoder_diagnostics' not in sys.modules:
        stub = types.ModuleType('encoder_diagnostics')
        stub._context = lambda: (_ for _ in ()).throw(RuntimeError('stub context'))
        sys.modules['encoder_diagnostics'] = stub
    import pipeline_decode_node as node
    return node


# --- 2. preview writer --------------------------------------------------------
def writer_case():
    node = import_decode_node()
    gate = threading.Event()
    calls, markers = [], []

    def slow_save(images, audio, prefix):
        gate.wait(5)
        calls.append((prefix, images.data_ptr(), float(images.sum())))
        if prefix.endswith('bad'):
            raise ValueError('muxer exploded')
        return prefix + '/preview_00001_.mp4'

    w = node.PreviewWriter(slow_save, maxsize=2, marker=lambda *a: markers.append(a))
    images = [torch.full((2, 4, 4, 3), float(i)) for i in range(4)]
    audio = {'waveform': torch.zeros(1, 2, 8), 'sample_rate': 48000}
    w.submit(0, images[0], audio, 'p0')          # taken by the writer, blocked in save
    time.sleep(0.1)
    w.submit(1, images[1], audio, 'p1')
    w.submit(2, images[2], audio, 'p2bad')       # queue now full (maxsize 2)
    blocked = []
    t = threading.Thread(target=lambda: blocked.append(w.submit(3, images[3], audio, 'p3')))
    t.start()
    time.sleep(0.3)
    assert t.is_alive(), 'a full writer queue must block the submitting decode worker'
    images[3].add_(100.0)                         # caller mutates AFTER submit started: copy taken first
    gate.set()
    t.join(5)
    assert not t.is_alive() and blocked[0] >= 0.25, blocked
    w.queue.join()
    assert [c[0] for c in calls] == ['p0', 'p1', 'p2bad', 'p3'], calls
    assert all(c[1] not in {im.data_ptr() for im in images} for c in calls), 'writer must own private copies'
    assert calls[3][2] == 3.0 * images[3].numel(), calls[3]   # the pre-mutation copy
    drained = w.drain()
    assert drained['completed_total'] == 4 and drained['pending'] == 0, drained
    assert drained['saves'][2]['saved'] == 'save-failed:ValueError', drained['saves'][2]
    assert [m[1] for m in markers] == [0, 1, 2, 3] and all(m[0] == 'save' for m in markers), markers
    assert w.drain()['saves'] == [], 'drain must hand records over once'


case('preview writer: bounded FIFO, back-pressure, private copies, failures recorded', writer_case)


# --- 3. fail-closed replica refusal ---------------------------------------------
def refusal_case():
    node = import_decode_node()
    import ltx_pipeline as p
    import ltx_decode_replica as placement
    p.clear()
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
        os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64
        shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                for n, m in (('ltx_pipeline.py', p), ('ltx_decode_replica.py', placement),
                             ('ltx_gil_probe.py', sys.modules['ltx_gil_probe']),
                             ('ltx_decode_child.py', sys.modules['ltx_decode_child']),
                             ('pipeline_decode_node.py', node))}
        (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas}))
        node._context = lambda: (run, identity)
        torch.use_deterministic_algorithms(True)
        node._PROBE.update(passed=False, outcome='not run')
        latent = {'samples': torch.zeros(1, 128, 4, 8, 8)}
        alat = {'samples': torch.zeros(1, 8, 26, 16)}
        for mode in placement.REPLICA_MODES:
            try:
                node.LTXPipelineDecode().apply(None, None, latent, alat, mode, 900500, 2, 'refuse-' + mode)
                raise AssertionError('replica mode ran without a probe')
            except node.ReplicaNotQualified as error:
                assert 'cross-card decode probe' in str(error)
            receipt = json.loads((run / ('pipeline-decode-refuse-' + mode + '.json')).read_text())
            assert receipt['passed'] is False and 'probe' in receipt['refused'], receipt
        assert node._failed is False, 'a refusal must not latch the decode node'
        assert p.pending('decode') == [], 'a refusal must not submit work'
        assert p.STAGE_WORKERS['decode'] in (1, 2)
        os.environ.pop('LTX_ENCODER_IDENTITY_SHA256', None)


case('replica modes refused before a passed probe: receipt, no submit, no latch', refusal_case)


# --- 4. probe comparison --------------------------------------------------------
def probe_case():
    import ltx_decode_replica as placement
    v = torch.randn(1, 128, 4, 8, 8)
    a = torch.randn(1, 8, 26, 16)
    img = torch.rand(25, 8, 8, 3)
    wav = torch.randn(1, 2, 64)
    sha = placement.tensor_sha256
    fx = {'fixture': 'bird', 'source': '/x', 'expected': {
        'video_latent': sha(v), 'audio_latent': sha(a), 'images': sha(img), 'waveform': sha(wav)}}
    load = lambda row: {'video_latent': v, 'audio_latent': a}
    good = lambda vl, al: (img.clone(), {'waveform': wav.clone()})
    passed, rows = placement.probe_rows([fx], load, good, good)
    assert passed and rows[0]['cards_bytewise_equal'] and rows[0]['replica_matches_reference'], rows

    def off_by_one_byte(vl, al):
        bad = img.clone()
        bad.view(torch.uint8).view(-1)[7] ^= 1
        return bad, {'waveform': wav.clone()}
    passed, rows = placement.probe_rows([fx], load, good, off_by_one_byte)
    assert not passed and not rows[0]['cards_bytewise_equal'] and rows[0]['native_matches_reference'] \
        and not rows[0]['replica_matches_reference'], rows
    neg_zero = lambda vl, al: (img.clone(), {'waveform': torch.where(wav == 0, -0.0 * wav, wav)})
    passed, _ = placement.probe_rows([fx], load, good, neg_zero)
    assert passed  # no zeros in randn: identical bytes
    fx_bad = dict(fx, expected=dict(fx['expected'], video_latent='0' * 64))
    passed, rows = placement.probe_rows([fx_bad], load, good, good)
    assert not passed and rows[0]['inputs_certified'] is False and 'native' not in rows[0], rows
    assert placement.probe_rows([], load, good, good)[0] is False, 'an empty probe must not pass'


case('probe: byte comparison across cards and to references', probe_case)


# --- 5. placement allowlist and module clone --------------------------------------
def placement_case():
    import ltx_decode_replica as placement
    assert placement.slot_for('pipeline-save', 7) == 'native'
    assert [placement.slot_for('pipeline-replica', i) for i in range(4)] == ['native', 'replica'] * 2
    assert placement.slot_for('pipeline-moved', 4) == 'replica'
    for bad in (('graph', 1), ('pipeline-replica', -1)):
        try:
            placement.slot_for(*bad)
            raise AssertionError('slot_for admitted %r' % (bad,))
        except RuntimeError:
            pass

    class Leaf(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lin = torch.nn.Linear(4, 4)
            self.register_buffer('steps', torch.tensor([1.0]))
            self.register_buffer('timesteps', torch.tensor([0.5, 0.25]), persistent=False)
            self.window = torch.hann_window(8)          # plain tensor attribute
            self.dev = torch.device('cpu')
            self.empty = torch.empty(0)

    src = Leaf()
    assert placement.placement_offenders(src, 'cpu') == []
    for slot in ('replica', 'native', 'elsewhere'):
        try:
            placement.check_placement(src, slot)
            raise AssertionError('check_placement admitted a CPU module for ' + slot)
        except RuntimeError:
            pass
    clone, rewritten = placement.clone_module(src, 'cpu', 'cpu', stage=lambda t, d: t.detach().clone())
    assert clone is not src and clone.lin.weight is not src.lin.weight
    assert clone.lin.weight.data_ptr() != src.lin.weight.data_ptr()
    assert clone.window.data_ptr() != src.window.data_ptr() and torch.equal(clone.window, src.window)
    assert torch.equal(clone.lin.weight, src.lin.weight) and not clone.lin.weight.requires_grad
    assert rewritten == ['Leaf.dev'], rewritten
    try:
        placement.clone_module(src, 'cpu', 'cpu', stage=lambda t, d: t.detach().clone().add_(1)
                               if t.numel() else t.detach().clone())
        raise AssertionError('an inexact copy was admitted')
    except RuntimeError as error:
        assert 'not exact' in str(error)
    assert 'timesteps' not in src.state_dict(), 'test needs a non-persistent buffer'
    only_np = lambda t, d: t.detach().clone().mul_(2) if t.shape == (2,) else t.detach().clone()
    try:
        placement.clone_module(src, 'cpu', 'cpu', stage=only_np)
        raise AssertionError('a wrong non-persistent buffer was admitted')
    except RuntimeError as error:
        assert 'buffer:timesteps' in str(error), error
    count, _nbytes = placement.verified_tensors(clone)
    assert count == len(list(src.parameters())) + 2 + 2, count   # 2 params, 2 buffers, window + empty
    try:
        placement.clone_module(src, 'cpu', 'cpu', stage=lambda t, d: t.detach())
        raise AssertionError('a storage-sharing copy was admitted')
    except RuntimeError as error:
        assert 'shares storage' in str(error)


case('placement: slot parity, allowlist refusals, exact unshared clone', placement_case)


# --- 6. mirror tripwire -----------------------------------------------------------
def mirror_case():
    sources = sorted(ROOT.glob('prepared-encoder-host-residency-13/source'))
    assert sources, 'packet13 source not found'
    src = sources[0]
    sd = (src / 'comfy/sd.py').read_text()
    for line in ('if self.latent_dim == 2 and samples_in.ndim == 5:',
                 "if getattr(self.first_stage_model, 'comfy_has_chunked_io', False):",
                 'samples = samples_in[x:x + batch_number].to(device=self.device, dtype=self.vae_dtype)',
                 'self.first_stage_model.decode(samples, output_buffer=pixel_samples[x:x+batch_number], **vae_options)',
                 'out = self.first_stage_model.decode(samples, **vae_options).to(device=self.output_device, dtype=self.vae_output_dtype(), copy=True)',
                 'self.process_output(pixel_samples[x:x+batch_number])',
                 'pixel_samples = pixel_samples.to(self.output_device).movedim(1,-1)'):
        assert line in sd, 'ComfyUI VAE.decode changed; the replica mirror is stale: ' + line
    nodes_src = (src / 'nodes.py').read_text()
    assert 'images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])' in nodes_src
    audio = (src / 'comfy_extras/nodes_lt_audio.py').read_text()
    assert 'audio = audio_vae.decode(audio_latent).movedim(-1, 1).to(audio_latent.device)' in audio
    assert 'audio_latent = audio_latent.unbind()[-1]' in audio


case('mirror tripwire: mirrored ComfyUI decode lines unchanged', mirror_case)

# --- 7. end-to-end node path (decoders stubbed) ------------------------------------
def node_path_case():
    node = import_decode_node()
    import ltx_pipeline as p
    import ltx_decode_replica as placement
    p.clear()
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        os.environ['LTX_ENCODER_RUN_DIR'] = tmp
        os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64
        identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
        shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                for n, m in (('ltx_pipeline.py', p), ('ltx_decode_replica.py', placement),
                             ('ltx_gil_probe.py', sys.modules['ltx_gil_probe']),
                             ('ltx_decode_child.py', sys.modules['ltx_decode_child']),
                             ('pipeline_decode_node.py', node))}
        (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas}))
        node._context = lambda: (run, identity)
        torch.use_deterministic_algorithms(True)
        used = []

        def fake(slot, delay):
            def fn(vae, audio_vae, v, a):
                time.sleep(delay)
                idx = int(v['samples'].flatten()[0])
                used.append((slot, idx))
                return (torch.full((2, 4, 4, 3), float(idx)), {'waveform': torch.full((1, 2, 8), float(idx)),
                                                              'sample_rate': 48000}, {'wait_s': 0.0, 'vae_s': delay})
            return fn
        saved_native, saved_replica, saved_check = node.decode_native, node.decode_replica, placement.check_placement
        saved_save = node._WRITER.save_fn
        node.decode_native, node.decode_replica = fake('native', 0.25), fake('replica', 0.02)
        placement.check_placement = lambda module, slot: True
        node._WRITER.save_fn = lambda images, audio, prefix: prefix + '/fake.mp4'
        node._PROBE.update(passed=True, outcome='replica-exact', sources=(id(None), id(None)))
        node._REPLICAS.update({'video': types.SimpleNamespace(module=None), 'audio': types.SimpleNamespace(module=None)})
        try:
            base = 901000
            emitted = []
            for k in range(8):
                idx = base + k
                v = {'samples': torch.full((1, 128, 4, 8, 8), float(idx))}
                a = {'samples': torch.full((1, 8, 26, 16), float(idx))}
                sentry = {'video_finite': True, 'audio_finite': True,
                          'video_sha256': hashlib.sha256(v['samples'].view(torch.uint8).numpy().tobytes()).hexdigest(),
                          'audio_sha256': hashlib.sha256(a['samples'].view(torch.uint8).numpy().tobytes()).hexdigest()}
                p.record_fingerprint(('sample-output', idx), sentry)
                out = node.LTXPipelineDecode().apply(None, None, v, a, 'pipeline-replica', idx, 2, 'e2e-%02d' % k)
                r = json.loads((run / ('pipeline-decode-e2e-%02d.json' % k)).read_text())
                emitted.append(r['detail']['emitted_index'])
                if r['detail']['emitted_index'] >= 0:
                    e = r['detail']['emitted_index']
                    assert float(out[0].flatten()[0]) == float(e), 'emitted images belong to another clip'
                    assert r['detail']['decode_split']['slot'] == placement.slot_for('pipeline-replica', e)
                    assert r['detail']['saved_file'] == 'queued:e2e-%02d/preview' % (e - base)
            assert emitted == [-1, -1] + [base + k for k in range(6)], emitted
            assert r['stage_workers'] == 2 and r['placement'] == ['native', 'replica'], r
            node._WRITER.queue.join()
            p.collect('decode', base + 6), p.collect('decode', base + 7)
            node._WRITER.queue.join()
            for k in range(8):
                assert (run / ('pipeline-done-decode-%d.json' % (base + k))).is_file()
                assert (run / ('pipeline-done-save-%d.json' % (base + k))).is_file()
            assert sorted(i - base for s_, i in used if s_ == 'replica') == [1, 3, 5, 7], used
            assert node._failed is False
        finally:
            node.decode_native, node.decode_replica, placement.check_placement = saved_native, saved_replica, saved_check
            node._WRITER.save_fn = saved_save
            node._PROBE.update(passed=False, outcome='not run')
            node._REPLICAS.clear()
            os.environ.pop('LTX_ENCODER_RUN_DIR', None)
            os.environ.pop('LTX_ENCODER_IDENTITY_SHA256', None)
            p.clear()


case('node path: replica mode alternates cards, emits in order, saves and markers', node_path_case)

# --- 8. capture lock: a capture excludes replica work and vice versa ----------------
def load_capture_lock():
    text = (HERE / 'ltx_graph_capture.py').read_text()
    start, end = text.index('class CaptureReplayLock:'), text.index('CAPTURE_LOCK = CaptureReplayLock()')
    ns = {'threading': threading}
    exec(compile(text[start:end], 'ltx_graph_capture.py[lock]', 'exec'), ns)
    return ns['CaptureReplayLock']()


def capture_lock_case():
    node = import_decode_node()
    import ltx_decode_replica as placement
    lock = load_capture_lock()
    events = []
    saved = (node._capture_lock, placement.decode_clip_replica, node._busy_begin, node._busy_end)
    node._capture_lock = lambda: lock
    node._busy_begin = lambda *a, **k: (None, None)
    node._busy_end = lambda *a, **k: None

    def fake_decode(*args):
        assert lock.readers >= 1 and not lock.writer, 'replica decode ran without the shared capture lock'
        events.append('decode-start')
        time.sleep(0.3)
        events.append('decode-end')
        return torch.zeros(1), {'waveform': torch.zeros(1)}
    placement.decode_clip_replica = fake_decode
    node._PROBE.update(passed=True, sources=(id(None), id(None)))
    node._REPLICAS.update({'video': types.SimpleNamespace(stream=None, device='xpu:1'),
                           'audio': types.SimpleNamespace(stream=None, device='xpu:1')})
    try:
        # (a) a held capture (exclusive) blocks a replica decode
        lock.acquire_exclusive()
        t = threading.Thread(target=lambda: node.decode_replica(None, None, {}, {}))
        t.start()
        time.sleep(0.3)
        assert events == [], 'replica decode started during a capture'
        events.append('capture-end')
        lock.release_exclusive()
        t.join(5)
        assert events == ['capture-end', 'decode-start', 'decode-end'], events
        # (b) a running replica decode blocks a capture
        events.clear()
        t = threading.Thread(target=lambda: node.decode_replica(None, None, {}, {}))
        t.start()
        time.sleep(0.1)
        lock.acquire_exclusive()
        events.append('capture-start')
        lock.release_exclusive()
        t.join(5)
        assert events == ['decode-start', 'decode-end', 'capture-start'], events
        # (c) a capture blocks the construction copy too
        events.clear()
        lock.acquire_exclusive()
        src = types.SimpleNamespace(first_stage_model=torch.nn.Linear(2, 2), device='cpu')
        saved_clone, saved_dev = placement.clone_module, dict(placement.ALLOWED_DEVICES)
        placement.clone_module = lambda *a, **k: (events.append('copy') or (torch.nn.Linear(2, 2), []))
        placement.ALLOWED_DEVICES['replica'] = 'meta'
        placement_check = placement.check_placement
        placement.check_placement = lambda m, slot: True
        t = threading.Thread(target=lambda: placement.build_replica(src, 'meta', threading.Lock(), lock,
                                                                     make_stream=lambda d: None))
        t.start()
        time.sleep(0.3)
        assert events == [], 'replica construction copied during a capture'
        lock.release_exclusive()
        t.join(5)
        assert events == ['copy'], events
        placement.clone_module, placement.check_placement = saved_clone, placement_check
        placement.ALLOWED_DEVICES.clear()
        placement.ALLOWED_DEVICES.update(saved_dev)
    finally:
        node._capture_lock, placement.decode_clip_replica, node._busy_begin, node._busy_end = saved
        node._PROBE.update(passed=False, outcome='not run')
        node._PROBE.pop('sources', None)
        node._REPLICAS.clear()


case('capture lock: capture blocks replica decode/copy, replica decode blocks capture', capture_lock_case)


# --- 9. probe releases replicas on every non-pass verdict ---------------------------
class FakeXpu:
    def __init__(self):
        self.reserved = 10 << 30
        self.emptied = []

    def memory_reserved(self, index):
        return self.reserved

    def mem_get_info(self, index):
        return (32 << 30) - self.reserved, 32 << 30

    def device(self, device):
        import contextlib
        return contextlib.nullcontext()

    def empty_cache(self):
        self.emptied.append(True)
        self.reserved -= 2 << 30


def probe_release_case():
    node = import_decode_node()
    import ltx_decode_replica as placement
    lock = load_capture_lock()
    fx = FakeXpu()
    mm = types.ModuleType('comfy.model_management')
    ns = {'_LOAD_LOCK': threading.Lock()}
    exec('def fast_load_models_gpu(*a, **k):\n    return None', ns)
    mm.load_models_gpu = ns['fast_load_models_gpu']
    comfy_pkg = sys.modules.get('comfy') or types.ModuleType('comfy')
    saved_mods = {k: sys.modules.get(k) for k in ('comfy', 'comfy.model_management')}
    sys.modules['comfy'], sys.modules['comfy.model_management'] = comfy_pkg, mm
    real_release = placement.release_replicas
    patched = {
        (node, '_capture_lock'): lambda: lock, (node, '_xpu_memory'): lambda i: {'allocated': 0, 'reserved': 0},
        (node, '_new_stream'): lambda d: None, (node, '_load_probe_fixtures'): lambda packet: ['fx'],
        (node, 'decode_native'): lambda *a: (torch.zeros(1), {'waveform': torch.zeros(1)}, {}),
        (placement, 'build_replica'): lambda src, dev, ll, cl, make_stream=None:
            types.SimpleNamespace(module=None, report={'bytes': 1}),
        (placement, 'check_placement'): lambda m, slot: True,
        (placement, 'free_bytes'): lambda device, xpu=None: (20 << 30, 'fake'),
        (placement, 'release_replicas'): lambda r, d, cl, xpu=None: real_release(r, d, cl, xpu=fx),
    }
    saved = {k: getattr(*k) for k in patched}
    for (obj, name), value in patched.items():
        setattr(obj, name, value)
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
        os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64
        shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                for n, m in (('ltx_decode_replica.py', placement), ('pipeline_decode_node.py', node))}
        (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas,
                                                               'source_packet_path': tmp}))
        node._context = lambda: (run, identity)
        torch.use_deterministic_algorithms(True)
        try:
            verdicts = [('mismatch', lambda *a: (False, [{'passed': False}]), 'replica-not-exact', False),
                        ('raises', lambda *a: (_ for _ in ()).throw(RuntimeError('decode exploded')), 'error', False),
                        ('pass', lambda *a: (True, [{'passed': True}]), 'replica-exact', True)]
            for name, rows_fn, outcome, resident in verdicts:
                placement_rows = placement.probe_rows
                placement.probe_rows = rows_fn
                node.LTXDecodeReplicaProbe().apply('vae', 'audio_vae', 'probe-' + name)
                placement.probe_rows = placement_rows
                r = json.loads((run / ('decode-probe-probe-%s.json' % name)).read_text())
                assert r['outcome'] == outcome, r
                if resident:
                    assert r['replicas_resident'] == ['audio', 'video'] and node._PROBE['passed'], r
                    assert 'released' not in r
                else:
                    assert r['replicas_resident'] == [] and not node._PROBE['passed'], r
                    assert r['released']['released'] == ['audio', 'video'], r
                    assert r['released']['reserved_freed_bytes'] == 2 << 30, r['released']
                    assert not node._REPLICAS
            # post-probe low memory is also a non-pass verdict
            node._REPLICAS.clear()
            node._PROBE.update(passed=False)
            placement.free_bytes = lambda device, xpu=None: (6 << 30, 'fake') if not node._PROBE.get('rows_done') \
                else (0, 'fake')
            placement_rows = placement.probe_rows

            def rows_then_low(*a):
                node._PROBE['rows_done'] = True
                return True, [{'passed': True}]
            placement.probe_rows = rows_then_low
            node.LTXDecodeReplicaProbe().apply('vae', 'audio_vae', 'probe-lowmem')
            placement.probe_rows = placement_rows
            r = json.loads((run / 'decode-probe-probe-lowmem.json').read_text())
            assert r['outcome'] == 'insufficient-memory' and r['replicas_resident'] == [] and 'released' in r, r
        finally:
            for (obj, name), value in saved.items():
                setattr(obj, name, value)
            for k, v in saved_mods.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
            node._PROBE.clear()
            node._PROBE.update(passed=False, outcome='not run', receipt=None)
            node._REPLICAS.clear()
            os.environ.pop('LTX_ENCODER_IDENTITY_SHA256', None)


case('probe: replicas released (memory recorded) on mismatch/error/low memory; kept only on pass',
     probe_release_case)


# --- 10. save record and placement-change refusal ------------------------------------
def save_record_case():
    node = import_decode_node()
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        node._context = lambda: (run, {})
        out = node.LTXPipelineSaveRecord().apply('queued:f91b-rep-07/preview', 'f91b-rep-08')
        assert out == {'ui': {'text': ['preview queued to the writer: f91b-rep-07/preview']}}, out
        r = json.loads((run / 'pipeline-save-f91b-rep-08.json').read_text())
        assert r['status'] == 'queued-to-writer' and r['saved_file'] is None, r
        out = node.LTXPipelineSaveRecord().apply('f91b-rep-07/preview_00001_.mp4', 'f91b-rep-09')
        assert out['ui']['images'][0]['filename'] == 'preview_00001_.mp4'


case('save record: a queued preview is reported as status text, never as a file path', save_record_case)


def placement_change_case():
    node = import_decode_node()
    import ltx_pipeline as p
    import ltx_decode_replica as placement
    conflicts = node.placement_change_conflicts
    assert conflicts(None, 'pipeline-replica', 100, [99]) == []
    assert conflicts('pipeline-save', 'pipeline-save', 100, [99]) == []
    assert conflicts('pipeline-replica', 'pipeline-save', 100, [98, 99]) == [98, 99]
    assert conflicts('pipeline-save', 'pipeline-replica', 208689, [208216, 208587]) == [], 'fresh base must pass'
    p.clear()
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        os.environ['LTX_ENCODER_RUN_DIR'] = tmp
        os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64
        identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
        shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                for n, m in (('ltx_pipeline.py', p), ('ltx_decode_replica.py', placement),
                             ('ltx_gil_probe.py', sys.modules['ltx_gil_probe']),
                             ('ltx_decode_child.py', sys.modules['ltx_decode_child']),
                             ('pipeline_decode_node.py', node))}
        (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas}))
        node._context = lambda: (run, identity)
        saved = (node.decode_native, node.decode_replica, placement.check_placement, node._WRITER.save_fn)
        slow = lambda *a: (time.sleep(1.0), (torch.zeros(1, 2, 2, 3), {'waveform': torch.zeros(1, 2, 4),
                                                                      'sample_rate': 48000}, {'wait_s': 0, 'vae_s': 1}))[1]
        node.decode_native = node.decode_replica = slow
        placement.check_placement = lambda m, s_: True
        node._WRITER.save_fn = lambda *a: 'x.mp4'
        node._PROBE.update(passed=True, sources=(id(None), id(None)))
        node._REPLICAS.update({'video': types.SimpleNamespace(module=None), 'audio': types.SimpleNamespace(module=None)})
        node._LAST_PLACEMENT['mode'] = None
        try:
            def prompt(idx, mode, name):
                v = {'samples': torch.full((1, 4), float(idx))}
                a = {'samples': torch.full((1, 2), float(idx))}
                p.record_fingerprint(('sample-output', idx), {
                    'video_finite': True, 'audio_finite': True,
                    'video_sha256': hashlib.sha256(v['samples'].view(torch.uint8).numpy().tobytes()).hexdigest(),
                    'audio_sha256': hashlib.sha256(a['samples'].view(torch.uint8).numpy().tobytes()).hexdigest()})
                return node.LTXPipelineDecode().apply(None, None, v, a, mode, idx, 2 if mode == 'pipeline-replica' else 1, name)
            prompt(902000, 'pipeline-replica', 'pc-0')
            prompt(902001, 'pipeline-replica', 'pc-1')
            try:
                prompt(902002, 'pipeline-save', 'pc-2')
                raise AssertionError('placement change with pending same-stream jobs was admitted')
            except node.PlacementChangeRefused as error:
                assert 'pending' in str(error)
            r = json.loads((run / 'pipeline-decode-pc-2.json').read_text())
            assert r['passed'] is False and 'placement change' in r['refused'], r
            assert node._failed is False and 902002 not in p.pending('decode')
            prompt(902100, 'pipeline-save', 'pc-3')      # fresh base: admitted
        finally:
            node.decode_native, node.decode_replica, placement.check_placement, node._WRITER.save_fn = saved
            node._PROBE.update(passed=False, outcome='not run')
            node._PROBE.pop('sources', None)
            node._REPLICAS.clear()
            node._LAST_PLACEMENT['mode'] = None
            os.environ.pop('LTX_ENCODER_RUN_DIR', None)
            os.environ.pop('LTX_ENCODER_IDENTITY_SHA256', None)
            time.sleep(1.2)
            p.clear()


case('placement change refused while same-stream decode jobs pend; fresh base admitted', placement_change_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
