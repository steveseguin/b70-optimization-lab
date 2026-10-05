#!/usr/bin/env python3
"""CPU-only tests for packet 97 (decode replica placement, third decode worker, failed-job
receipts, runner). No XPU, no ComfyUI server, nothing written outside temporary directories.

Cases that depend on LTX_DECODE_REPLICA_DEVICE / LTX_DECODE_REPLICAS (read once at import) run
in a child process of this file (`--child <case>`) with that environment.

1. allowlists and defaults (read_replica_config; a bad value refuses the import)
2. default-off equivalence with packet 96: every graph byte-identical, manifest sections, the
   placement tables, the headroom figures, the packet copies equal the lane sources
3. replica plumbing end to end with stand-ins, for xpu:1, xpu:2 and xpu:1,xpu:2 (and xpu:2,xpu:1):
   decode jobs use the slot's VAE pair, lock, stream and busy-window card; round-robin by clip
   index mod the number of slots; emission in clip order; decode receipts and decode-split
   devices follow the option
4. the probe runs against the chosen card(s): every replica card decodes every fixture, a
   one-byte difference on any card refuses and releases every replica on its own card, and
   run-decode-probe-97's placement check accepts only the requested cards
5. headroom accounting charges the chosen card(s)
6. failed jobs in every stage write pipeline-failed-*.json and one log line; the writer never raises
7. the runner finds a failed-job file and stops (capture-pass loop and quiescence), exit 20
8. generator / gate / runner / helpers agree on names, specs and index bases
"""
import ast
import contextlib
import hashlib
import importlib.util
import io
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
sys.path.insert(0, str(HERE))
R = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
P96 = R / 'prepared-encoder-batch-96'
P97 = R / 'prepared-encoder-place-97'
PY = sys.executable
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error)[:600] + ' | ' + ' / '.join(traceback.format_exc().splitlines()[-4:])))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def child(name, env_extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith('LTX_DECODE_')}
    env.update(env_extra)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    r = subprocess.run([PY, '-B', str(Path(__file__)), '--child', name], env=env, capture_output=True,
                       text=True, timeout=600)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith('RESULT ')]
    if r.returncode != 0 or not lines:
        raise AssertionError('child %s %s failed rc=%d: %s' % (name, env_extra, r.returncode,
                                                               (r.stdout + r.stderr)[-2500:]))
    return json.loads(lines[-1][len('RESULT '):])


SPECS = {'xpu:1': {}, 'xpu:2': {'LTX_DECODE_REPLICA_DEVICE': 'xpu:2'},
         'xpu:1,xpu:2': {'LTX_DECODE_REPLICA_DEVICE': 'xpu:1,xpu:2', 'LTX_DECODE_REPLICAS': '2'},
         'xpu:2,xpu:1': {'LTX_DECODE_REPLICA_DEVICE': 'xpu:2,xpu:1', 'LTX_DECODE_REPLICAS': '2'}}


# =============================================================================================
# child-process helpers (run with a given replica environment)
# =============================================================================================
def import_node():
    if 'encoder_diagnostics' not in sys.modules:
        stub = types.ModuleType('encoder_diagnostics')
        stub._context = lambda: (_ for _ in ()).throw(RuntimeError('stub context'))
        sys.modules['encoder_diagnostics'] = stub
    import pipeline_decode_node as node
    return node


def capture_lock():
    text = (HERE / 'ltx_graph_capture.py').read_text()
    start, end = text.index('class CaptureReplayLock:'), text.index('CAPTURE_LOCK = CaptureReplayLock()')
    ns = {'threading': threading}
    exec(compile(text[start:end], 'ltx_graph_capture.py[lock]', 'exec'), ns)
    return ns['CaptureReplayLock']()


def server_files(run, node, p, placement):
    identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
    shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
            for n, m in (('ltx_pipeline.py', p), ('ltx_decode_replica.py', placement),
                         ('ltx_gil_probe.py', sys.modules['ltx_gil_probe']),
                         ('ltx_decode_child.py', sys.modules['ltx_decode_child']),
                         ('pipeline_decode_node.py', node))}
    (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas, 'source_packet_path': str(run)}))
    node._context = lambda: (run, identity)
    os.environ['LTX_ENCODER_RUN_DIR'] = str(run)
    os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64


def child_config():
    import ltx_decode_replica as placement
    return {'record': placement.replica_record(), 'allowed': placement.ALLOWED_DEVICES,
            'placements': {k: list(v) for k, v in placement.PLACEMENTS.items()},
            'replica_device': placement.REPLICA_DEVICE}


def child_node():
    """The real decode node and the real decode_replica (slot, lock, pair, busy card), with only the
    VAE arithmetic stood in: decode_native and placement.decode_clip_replica."""
    import torch
    node = import_node()
    import ltx_pipeline as p
    import ltx_decode_replica as placement
    lock = capture_lock()
    calls, busy, held = [], [], []
    p.clear()
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        server_files(run, node, p, placement)
        torch.use_deterministic_algorithms(True)

        def fake_native(vae, audio_vae, v, a):
            idx = int(v['samples'].flatten()[0])
            calls.append(('native', 'xpu:3', idx))
            time.sleep(0.05 if idx % 2 else 0.15)
            return (torch.full((2, 4, 4, 3), float(idx)), {'waveform': torch.full((1, 2, 8), float(idx)),
                                                          'sample_rate': 48000}, {'wait_s': 0.0, 'vae_s': 0.1})

        def fake_replica(video, audio_rep, vae, audio_vae, v, a):
            assert lock.readers >= 1 and not lock.writer, 'replica decode without the shared capture lock'
            assert video.device == audio_rep.device, 'video and audio replicas on different cards'
            locked = [s for s, lk in node._REPLICA_LOCKS.items() if lk.locked()]
            held.append(locked)
            idx = int(v['samples'].flatten()[0])
            calls.append((video.slot, video.device, idx))
            time.sleep(0.02)
            return torch.full((2, 4, 4, 3), float(idx)), {'waveform': torch.full((1, 2, 8), float(idx)),
                                                          'sample_rate': 48000}
        saved = (node.decode_native, placement.decode_clip_replica, placement.check_placement, node._capture_lock,
                 node._busy_begin, node._busy_end, node._WRITER.save_fn)
        node.decode_native = fake_native
        placement.decode_clip_replica = fake_replica
        node._capture_lock = lambda: lock
        node._busy_begin = lambda device, stream=None: (busy.append((device, stream)) or (None, None))
        node._busy_end = lambda *a, **k: None
        node._WRITER.save_fn = lambda images, audio, prefix: prefix + '/fake.mp4'
        checked = []
        real_check = saved[2]

        def check(module, slot):
            checked.append((slot, module.device))
            return real_check(module, slot)
        placement.check_placement = check
        node._PROBE.update(passed=True, outcome='replica-exact', sources=(id(None), id(None)))

        class Mod(torch.nn.Module):
            def __init__(self, dev):
                super().__init__()
                self.device = dev
        for slot in placement.REPLICA_SLOTS:
            dev = placement.ALLOWED_DEVICES[slot]
            # placement_offenders compares torch devices of tensors; a module with no tensors passes for its slot
            for key in ('video', 'audio'):
                node._REPLICA_SETS[slot][key] = types.SimpleNamespace(module=Mod(dev), device=dev, slot=slot,
                                                                      stream='stream-' + dev)
        try:
            base = 902000
            n = 12
            emitted, receipts = [], []
            for k in range(n):
                idx = base + k
                v = {'samples': torch.full((1, 4, 2, 2, 2), float(idx))}
                a = {'samples': torch.full((1, 2, 3, 4), float(idx))}
                p.record_fingerprint(('sample-output', idx), {
                    'video_finite': True, 'audio_finite': True,
                    'video_sha256': hashlib.sha256(v['samples'].view(torch.uint8).numpy().tobytes()).hexdigest(),
                    'audio_sha256': hashlib.sha256(a['samples'].view(torch.uint8).numpy().tobytes()).hexdigest()})
                out = node.LTXPipelineDecode().apply(None, None, v, a, 'pipeline-replica', idx, 2, 'pl-%02d' % k)
                r = json.loads((run / ('pipeline-decode-pl-%02d.json' % k)).read_text())
                receipts.append(r)
                e = r['detail']['emitted_index']
                emitted.append(e)
                if e >= 0:
                    assert float(out[0].flatten()[0]) == float(e), 'emitted images belong to another clip'
            node._WRITER.queue.join()
            p.collect('decode', base + n - 2), p.collect('decode', base + n - 1)
            node._WRITER.queue.join()
            last = receipts[-1]
            splits = {r['detail']['emitted_index']: r['detail']['decode_split'] for r in receipts
                      if r['detail']['emitted_index'] >= 0}
            # the check-decode-placement-97 helper over these very receipts
            req = run / 'requests'
            for k in range(n):
                (req / ('pl-%02d' % k)).mkdir(parents=True)
                (req / ('pl-%02d' % k) / 'submission.json').write_text('{}')
                (req / ('pl-%02d' % k) / 'prompt.json').write_text(json.dumps({
                    '426': {'inputs': {'mode': 'pipeline-replica', 'depth': 2}},
                    '428': {'inputs': {'depth': 0, 'clip_index': base + k}}}))   # decode fed directly: SD 0
            spec = ','.join(placement.REPLICA_DEVICES)
            chk = load('cdp97', HERE / 'check-decode-placement-97.py')
            ok_checked, ok_bad, _per = chk.check(run, run, spec, ['pl'])
            other = 'xpu:2' if spec == 'xpu:1' else 'xpu:1'
            bad_checked, bad_bad, _per = chk.check(run, run, other, ['pl'])
            return {'emitted': emitted, 'calls': calls, 'busy': busy, 'held': held,
                    'splits': {str(k): [v['slot'], v['device']] for k, v in splits.items()},
                    'stage_workers': last['stage_workers'], 'placement': last['placement'],
                    'decode_replica': last['decode_replica'], 'checked': sorted(set(map(tuple, checked))),
                    'failed': node._failed, 'markers': sorted(int(f.name.split('-')[-1][:-5]) for f in
                                                              run.glob('pipeline-done-decode-*.json')),
                    'helper_ok': [ok_checked, ok_bad], 'helper_other': [bad_checked, len(bad_bad)]}
        finally:
            (node.decode_native, placement.decode_clip_replica, placement.check_placement, node._capture_lock,
             node._busy_begin, node._busy_end, node._WRITER.save_fn) = saved
            p.clear()


class FakeXpu:
    def __init__(self):
        self.reserved = {}
        self.emptied = []
        self.current = None

    def memory_reserved(self, index):
        return self.reserved.setdefault(index, 10 << 30)

    def mem_get_info(self, index):
        return (32 << 30) - self.memory_reserved(index), 32 << 30

    def device(self, device):
        xpu = self

        @contextlib.contextmanager
        def ctx():
            prev, xpu.current = xpu.current, str(device)
            try:
                yield
            finally:
                xpu.current = prev
        return ctx()

    def empty_cache(self):
        idx = int(self.current.split(':')[1])
        self.emptied.append(self.current)
        self.reserved[idx] = self.memory_reserved(idx) - (2 << 30)

    def get_device_properties(self, index):
        return types.SimpleNamespace(total_memory=32 << 30)


def child_probe():
    """The real LTXDecodeReplicaProbe and the real probe_rows, with stand-in VAEs: every replica card
    must decode every fixture; a one-byte difference on the LAST replica card refuses and releases
    every replica on its own card."""
    import torch
    node = import_node()
    import ltx_pipeline as p
    import ltx_decode_replica as placement
    lock = capture_lock()
    fx = FakeXpu()
    mm = types.ModuleType('comfy.model_management')
    ns = {'_LOAD_LOCK': threading.Lock()}
    exec('def fast_load_models_gpu(*a, **k):\n    return None', ns)
    mm.load_models_gpu = ns['fast_load_models_gpu']
    sys.modules['comfy'] = sys.modules.get('comfy') or types.ModuleType('comfy')
    sys.modules['comfy.model_management'] = mm
    fixtures = []
    tensors = {}
    for i in range(10):
        vl, al = torch.full((1, 3), float(i)), torch.full((1, 2), float(i) + 0.5)
        img, wav = torch.full((2, 2), float(i) * 2), torch.full((1, 4), float(i) * 3)
        tensors['f%d' % i] = {'video_latent': vl, 'audio_latent': al}
        fixtures.append({'fixture': 'f%d' % i, 'source': 'src-%d' % i, 'source_sha256': 'x',
                         'expected': {'video_latent': placement.tensor_sha256(vl),
                                      'audio_latent': placement.tensor_sha256(al),
                                      'images': placement.tensor_sha256(img), 'waveform': placement.tensor_sha256(wav)}})
    built, decoded, released = [], [], []
    corrupt = {'on': False}

    def decode(v, a):
        i = int(v['samples'].flatten()[0])
        return torch.full((2, 2), float(i) * 2), {'waveform': torch.full((1, 4), float(i) * 3)}

    def fake_build(src, dev, ll, cl, make_stream=None):
        stream = make_stream(dev)
        built.append((src, dev, stream))
        return types.SimpleNamespace(module=types.SimpleNamespace(device=dev), device=dev, stream=stream,
                                     report={'device': dev, 'bytes': 1})

    def fake_replica_decode(video, audio_rep, vae, audio_vae, v, a):
        assert lock.readers >= 1, 'probe replica decode without the shared capture lock'
        decoded.append((video.device, int(v['samples'].flatten()[0])))
        images, audio = decode(v, a)
        if corrupt['on'] and video.device == placement.REPLICA_DEVICES[-1]:
            images = images.clone()
            images.view(torch.uint8)[0] ^= 1
        return images, audio
    real_release = placement.release_replicas
    patched = {
        (node, '_capture_lock'): lambda: lock, (node, '_xpu_memory'): lambda i: {'allocated': i, 'reserved': 0},
        (node, '_new_stream'): lambda d: 'stream-' + d, (node, '_load_probe_fixtures'): lambda packet: fixtures,
        (node, '_load_fixture_tensors'): lambda row: tensors[row['fixture']],
        (node, 'decode_native'): lambda vae, avae, v, a: decode(v, a) + ({},),
        (placement, 'build_replica'): fake_build,
        (placement, 'check_placement'): lambda m, slot: m.device == placement.ALLOWED_DEVICES[slot] or
        (_ for _ in ()).throw(RuntimeError('slot %s module on %s' % (slot, m.device))),
        (placement, 'ensure_vaes_resident'): lambda *a, **k: {'step': 'stubbed'},
        (placement, 'decode_clip_replica'): fake_replica_decode,
        (placement, 'free_bytes'): lambda device, xpu=None: (20 << 30, 'fake'),
        (placement, 'release_replicas'): lambda r, d, cl, xpu=None: (released.append((d, sorted(r))) or
                                                                     real_release(r, d, cl, xpu=fx)),
    }
    for (obj, name), value in patched.items():
        setattr(obj, name, value)
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        server_files(run, node, p, placement)
        torch.use_deterministic_algorithms(True)
        node.LTXDecodeReplicaProbe().apply('vae', 'audio_vae', 'probe-pass')
        rpass = json.loads((run / 'decode-probe-probe-pass.json').read_text())
        out['pass'] = {'outcome': rpass['outcome'], 'built': [(s, d, st) for s, d, st in built],
                       'decoded_cards': sorted({d for d, _ in decoded}),
                       'per_card': {d: sorted(i for dd, i in decoded if dd == d) for d in {d for d, _ in decoded}},
                       'resident': {s: sorted(node._REPLICA_SETS[s]) for s in placement.REPLICA_SLOTS},
                       'keys': sorted(k for k in rpass if k.endswith(('_free_after_build', '_free_after_probe'))),
                       'memory_before': sorted(rpass['memory_before']),
                       'row_keys': sorted(rpass['rows'][0])}
        probe_client = (HERE / 'run-decode-probe-97.py').read_text()
        src = probe_client[probe_client.index('def placement_problems'):probe_client.index('problems = placement_problems')]
        cns = {'rows': rpass['rows']}
        exec(src, cns)
        spec = ','.join(placement.REPLICA_DEVICES)
        out['client_ok'] = cns['placement_problems'](rpass, spec)
        others = [s for s in SPECS if s != spec]
        out['client_other'] = {s: len(cns['placement_problems'](rpass, s)) for s in others}
        # second server state: a one-byte difference on the last replica card
        node._PROBE.update(passed=False)
        for s in placement.REPLICA_SLOTS:
            node._REPLICA_SETS[s].clear()
        node._PROBE.pop('sources', None)
        built.clear(), decoded.clear()
        corrupt['on'] = True
        node.LTXDecodeReplicaProbe().apply('vae', 'audio_vae', 'probe-bad')
        rbad = json.loads((run / 'decode-probe-probe-bad.json').read_text())
        out['bad'] = {'outcome': rbad['outcome'], 'passed': node._PROBE['passed'], 'released': released,
                      'emptied': fx.emptied, 'resident': {s: sorted(node._REPLICA_SETS[s]) for s in placement.REPLICA_SLOTS},
                      'refused_mode': None}
        # a replica-mode decode request after the failed probe is refused without latching
        try:
            node.LTXPipelineDecode().apply(None, None, {'samples': torch.zeros(1)}, {'samples': torch.zeros(1)},
                                           'pipeline-replica', 5, 2, 'after-bad')
        except node.ReplicaNotQualified as error:
            out['bad']['refused_mode'] = str(error)[:80]
        out['bad']['latched'] = node._failed
        out['bad']['client'] = cns['placement_problems'](rbad, spec)
    return out


def child_failed():
    """Real ltx_pipeline: a raising job in every stage writes its receipt before done is set."""
    import ltx_pipeline as p
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['LTX_ENCODER_RUN_DIR'] = tmp
        os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'f' * 64
        p.clear()
        p.set_stage_workers('decode', 2)

        def boom(msg):
            def fn():
                raise ValueError(msg)
            return fn
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            # encode: through run_ahead (inline job, collected by the caller)
            try:
                p.run_ahead('encode', 903000, 1, boom('encode broke'))
            except RuntimeError:
                pass
            # sample: a pinned capture-pass style job nobody waits for
            p.submit('sample', 903100, boom('sample broke'), target='ltx-sample-0')
            # decode: through run_behind
            p.run_behind('decode', 903200, 2, boom('decode broke'))
            deadline = time.time() + 10
            while time.time() < deadline and len(list(Path(tmp).glob('pipeline-failed-*.json'))) < 3:
                time.sleep(0.05)
            # done is set only after the receipt exists
            job = p._state('sample')['jobs'][903100]
            job.done.wait(5)
        files = sorted(f.name for f in Path(tmp).glob('pipeline-failed-*.json'))
        recs = [json.loads((Path(tmp) / f).read_text()) for f in files]
        out['files'] = files
        out['recs'] = [{k: r[k] for k in ('schema', 'stage', 'index', 'clip', 'worker', 'target', 'exception_type',
                                           'exception_message', 'server_identity_sha256')} for r in recs]
        out['tracebacks_full'] = all('Traceback (most recent call last)' in r['traceback'] and
                                     'raise ValueError' in r['traceback'] for r in recs)
        out['log'] = [ln for ln in err.getvalue().splitlines() if 'FAILED JOB' in ln]
        chk = load('cfj97', HERE / 'check-failed-jobs-97.py')
        out['checker_all'] = len(chk.find(tmp))
        out['checker_sample'] = [r.get('index') for _p, r in chk.find(tmp, stage='sample', index=903100)]
        out['checker_future'] = len(chk.find(tmp, since=time.time() + 60))
        with contextlib.redirect_stdout(io.StringIO()) as so:
            out['checker_rc'] = chk.main(['--run', tmp])
        out['checker_text'] = so.getvalue()
        # the writer never raises: unwritable run dir, a job with a strange index, an exception whose str raises
        os.environ['LTX_ENCODER_RUN_DIR'] = '/proc/definitely/not/writable'

        class Evil(Exception):
            def __str__(self):
                raise RuntimeError('str exploded')
        j = p._Job(('weird', object()), lambda: None)
        j.error = None
        with contextlib.redirect_stderr(io.StringIO()):
            out['unwritable'] = p.record_failure('sample', j, 'ltx-sample-9', Evil())
        os.environ.pop('LTX_ENCODER_RUN_DIR')
        with contextlib.redirect_stderr(io.StringIO()):
            out['no_run_dir'] = p.record_failure('decode', j, 'x', ValueError('v'))
        # the worker loop survives a failure and keeps serving
        p.submit('sample', 903101, lambda: 'still alive')
        out['after'] = p.collect('sample', 903101)[0]
        p.clear()
    return out


CHILDREN = {'config': child_config, 'node': child_node, 'probe': child_probe, 'failed': child_failed}

if len(sys.argv) == 3 and sys.argv[1] == '--child':
    print('RESULT ' + json.dumps(CHILDREN[sys.argv[2]](), default=str))
    sys.exit(0)


# =============================================================================================
# 1. allowlists and defaults
# =============================================================================================
def allowlist_case():
    import ltx_decode_replica as placement
    rc = placement.read_replica_config
    assert rc({}) == (1, ('xpu:1',))
    assert rc({'LTX_DECODE_REPLICA_DEVICE': ''}) == (1, ('xpu:1',))
    assert rc({'LTX_DECODE_REPLICA_DEVICE': 'xpu:2'}) == (1, ('xpu:2',))
    assert rc({'LTX_DECODE_REPLICAS': '1', 'LTX_DECODE_REPLICA_DEVICE': 'xpu:1'}) == (1, ('xpu:1',))
    assert rc({'LTX_DECODE_REPLICAS': '2', 'LTX_DECODE_REPLICA_DEVICE': 'xpu:1,xpu:2'}) == (2, ('xpu:1', 'xpu:2'))
    assert rc({'LTX_DECODE_REPLICAS': '2', 'LTX_DECODE_REPLICA_DEVICE': 'xpu:2,xpu:1'}) == (2, ('xpu:2', 'xpu:1'))
    bad = [{'LTX_DECODE_REPLICA_DEVICE': 'xpu:0'}, {'LTX_DECODE_REPLICA_DEVICE': 'xpu:3'},
           {'LTX_DECODE_REPLICA_DEVICE': 'xpu:2 '}, {'LTX_DECODE_REPLICA_DEVICE': 'xpu:1,xpu:2'},
           {'LTX_DECODE_REPLICAS': '3'}, {'LTX_DECODE_REPLICAS': '0'}, {'LTX_DECODE_REPLICAS': ' 2'},
           {'LTX_DECODE_REPLICAS': '2'}, {'LTX_DECODE_REPLICAS': '2', 'LTX_DECODE_REPLICA_DEVICE': 'xpu:2'},
           {'LTX_DECODE_REPLICAS': '2', 'LTX_DECODE_REPLICA_DEVICE': 'xpu:2,xpu:2'},
           {'LTX_DECODE_REPLICAS': '2', 'LTX_DECODE_REPLICA_DEVICE': 'xpu:0,xpu:2'},
           {'LTX_DECODE_REPLICAS': '2', 'LTX_DECODE_REPLICA_DEVICE': 'xpu:1,xpu:2,'}]
    for env in bad:
        try:
            rc(env)
        except RuntimeError:
            continue
        raise AssertionError('admitted %r' % env)
    # a bad value refuses the import itself (subprocess; this process keeps the default)
    env = dict(os.environ, LTX_DECODE_REPLICA_DEVICE='xpu:0', PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run([PY, '-B', '-c', 'import sys; sys.path.insert(0, %r); import ltx_decode_replica' % str(HERE)],
                       env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode != 0 and 'LTX_DECODE_REPLICA_DEVICE must be one of' in r.stderr, r.stderr[-500:]
    want = {'xpu:1': ({'native': 'xpu:3', 'replica': 'xpu:1'}, ['native', 'replica']),
            'xpu:2': ({'native': 'xpu:3', 'replica': 'xpu:2'}, ['native', 'replica']),
            'xpu:1,xpu:2': ({'native': 'xpu:3', 'replica': 'xpu:1', 'replica2': 'xpu:2'}, ['native', 'replica', 'replica2']),
            'xpu:2,xpu:1': ({'native': 'xpu:3', 'replica': 'xpu:2', 'replica2': 'xpu:1'}, ['native', 'replica', 'replica2'])}
    for spec, env in SPECS.items():
        c = child('config', env)
        assert c['allowed'] == want[spec][0] and c['placements']['pipeline-replica'] == want[spec][1], (spec, c)
        assert c['placements']['pipeline-moved'] == ['replica'] and c['replica_device'] == spec.split(',')[0]
        assert c['record']['replica_devices'] == spec.split(',') and c['record']['decode_replicas'] == len(spec.split(','))


case('allowlists and defaults: env parsing, refusals, import refuses a bad value, tables per spec', allowlist_case)


# =============================================================================================
# 2. default-off equivalence with packet 96
# =============================================================================================
def equivalence_case():
    import ltx_decode_replica as placement
    old = load('replica96', P96 / 'source/scripts/ltx_decode_replica.py')
    assert placement.ALLOWED_DEVICES == old.ALLOWED_DEVICES and placement.PLACEMENTS == old.PLACEMENTS
    assert placement.REPLICA_DEVICE == old.REPLICA_DEVICE and placement.NATIVE_DEVICE == old.NATIVE_DEVICE
    for mode in old.PLACEMENTS:
        for i in range(12):
            assert placement.slot_for(mode, i) == old.slot_for(mode, i)
    assert P97.is_dir(), 'packet 97 not built'
    g96 = sorted(p.name for p in (P96 / 'graphs').glob('*.json'))
    g97 = sorted(p.name for p in (P97 / 'graphs').glob('*.json'))
    assert g96 == g97 and len(g96) > 40
    for name in g96:
        assert (P96 / 'graphs' / name).read_bytes() == (P97 / 'graphs' / name).read_bytes(), name
    m96 = json.loads((P96 / 'manifest.json').read_text())
    m97 = json.loads((P97 / 'manifest.json').read_text())
    changed = sorted(k for k in set(m96) | set(m97) if m96.get(k) != m97.get(k))
    assert changed == ['clip_index_max', 'decode_placement', 'decode_replicas', 'extension_sha256s', 'files',
                       'graph_capture', 'pipeline_failures', 'preparer_sha256', 'startup_tools'], changed
    hash_keys = ('replica_module_sha256', 'pipe_adapter_sha256', 'pipe_node_sha256', 'pipe_decode_node_sha256',
                 'pipe_sampler_node_sha256')
    for sec in ('decode_placement', 'graph_capture'):
        a = {k: v for k, v in m96[sec].items() if k not in hash_keys}
        b = {k: v for k, v in m97[sec].items() if k not in hash_keys}
        assert a == b, sec
    assert m97['decode_placement']['replica_device'] == 'xpu:1' and m97['decode_placement']['native_device'] == 'xpu:3'
    files_changed = sorted(k for k in m96['files'] if m96['files'][k] != m97['files'][k])
    assert set(m96['files']) == set(m97['files'])
    assert files_changed == ['launch/encoder_runtime_common.py',
                             'source/custom_nodes/ltx_pipeline_decode_lab/__init__.py',
                             'source/custom_nodes/ltx_pipeline_lab/__init__.py',
                             'source/custom_nodes/ltx_pipeline_sampler_lab/__init__.py',
                             'source/scripts/ltx_decode_replica.py', 'source/scripts/ltx_pipeline.py',
                             'source/scripts/pipeline_decode_node.py', 'source/scripts/pipeline_node.py',
                             'source/scripts/pipeline_sampler_node.py'], files_changed
    # the capture adapter, batch, lean, text encoder, shard and model files are packet 96's bytes
    for f in ('ltx_graph_capture.py', 'ltx_sampler_batch.py', 'ltx_lean_conditioning.py', 'ltx_graph_text_encoder.py',
              'ltx_text_window.py', 'ltx_layer_shard.py', 'av_model.py', 'graph_capture_node.py'):
        assert m96['extension_sha256s'][f] == m97['extension_sha256s'][f], f
    for f in ('ltx_decode_replica.py', 'ltx_pipeline.py', 'pipeline_decode_node.py', 'pipeline_node.py',
              'pipeline_sampler_node.py'):
        assert (P97 / 'source/scripts' / f).read_bytes() == (HERE / f).read_bytes(), f
    # pipeline_sampler_node: packet 96's text plus the receipt field and the clip-index ceiling, nothing else
    def norm(text):
        tree = ast.parse(text)
        tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name == '_decode_replica_record')]
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                keep = [(k, v) for k, v in zip(node.keys, node.values)
                        if not (isinstance(k, ast.Constant) and k.value == 'decode_replica')]
                node.keys, node.values = [k for k, _ in keep], [v for _, v in keep]
                for i, (k, v) in enumerate(keep):
                    if isinstance(k, ast.Constant) and k.value == 'max':
                        if isinstance(v, ast.Attribute) and v.attr == 'CLIP_INDEX_MAX':
                            node.values[i] = ast.Constant(1000000)
        return ast.dump(tree)
    for f in ('pipeline_sampler_node.py', 'pipeline_node.py'):
        assert norm((HERE / f).read_text()) == norm((P96 / 'source/scripts' / f).read_text()), f
    # ltx_pipeline: packet 96's functions unchanged except the worker loop (one added call) and new helpers
    def funcs(text):
        return {n.name: ast.dump(n) for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    f96, f97 = funcs((P96 / 'source/scripts/ltx_pipeline.py').read_text()), funcs((HERE / 'ltx_pipeline.py').read_text())
    assert set(f97) - set(f96) == {'record_failure', '_index_label'}
    assert [k for k in f96 if f96[k] != f97[k]] == ['_worker_loop'], [k for k in f96 if f96[k] != f97[k]]
    # the default decode call is the packet 96 call (test-packet91's node-path case patches decode_replica
    # with a four-argument stand-in and still passes)
    src = (HERE / 'pipeline_decode_node.py').read_text()
    assert "elif slot == 'replica':\n                        # The packet 96 call, unchanged" in src
    assert 'images, audio, timing = decode_replica(vae, audio_vae, *latents)\n' in src
    # the headroom tool's default spec is packet 96's arithmetic
    h96, h97 = load('wh96', HERE / 'worker-headroom-96.py'), load('wh97', HERE / 'worker-headroom-97.py')
    for layout in h96.LAYOUTS:
        assert h97.zero_worker_free(layout) == h96.ZERO_WORKER_FREE_GIB[layout]
        for batch in (1, 2, 4):
            for pool in (0, 1):
                assert h97.needed(layout, batch, pool=pool) == h96.needed(layout, batch, pool=pool)
                free = {c: 7 << 30 for c in h96.CARDS}
                assert h97.live(free, layout, batch, pool=pool) == h96.live(free, layout, batch, pool=pool)
    assert h97.pre_decode('xpu:1') == h96.PRE_DECODE


case('default off: graphs, manifest sections, tables, call path, sampler node and headroom equal packet 96',
     equivalence_case)


# =============================================================================================
# 3. replica plumbing end to end
# =============================================================================================
def plumbing_case():
    for spec, env in SPECS.items():
        out = child('node', env)
        cards = spec.split(',')
        slots = ['native', 'replica'] + (['replica2'] if len(cards) == 2 else [])
        devices = dict(zip(slots, ['xpu:3'] + cards))
        base, n = 902000, 12
        assert out['emitted'] == [-1, -1] + [base + k for k in range(n - 2)], (spec, out['emitted'])
        assert out['stage_workers'] == len(slots) and out['placement'] == slots, (spec, out)
        assert out['decode_replica']['replica_devices'] == cards and out['decode_replica']['rotation'] == slots
        # every clip decoded once, on the slot of clip index mod the number of slots, on that slot's card
        got = sorted((i, s, d) for s, d, i in out['calls'])
        want = sorted((base + k, slots[(base + k) % len(slots)], devices[slots[(base + k) % len(slots)]])
                      for k in range(n))
        assert got == want, (spec, got, want)
        for e, (slot, dev) in out['splits'].items():
            assert slot == slots[int(e) % len(slots)] and dev == devices[slot], (spec, e, slot, dev)
        # busy windows of replica decodes name the replica's card and its own stream (decode_native is stood in)
        assert sorted(set(d for d, _ in out['busy'])) == sorted(cards), (spec, out['busy'])
        for d, stream in out['busy']:
            assert stream == 'stream-' + d, (spec, d, stream)
        # every replica decode held its own slot's lock, never another slot's... unless concurrently busy
        assert all(h for h in out['held']), out['held']
        assert sorted(map(tuple, out['checked'])) == sorted({(s, devices[s]) for s in slots[1:]}), out['checked']
        assert out['markers'] == [base + k for k in range(n)] and out['failed'] is False
        assert out['helper_ok'] == [n - 2, []] and out['helper_other'][1] > 0, (spec, out['helper_ok'], out['helper_other'])


case('plumbing: slot pair, lock, stream, busy card, rotation mod 2/3, ordered emission, receipts, placement helper',
     plumbing_case)


# =============================================================================================
# 4. the probe runs against the chosen card(s)
# =============================================================================================
def probe_case():
    for spec, env in SPECS.items():
        out = child('probe', env)
        cards = spec.split(',')
        slots = ['replica'] + (['replica2'] if len(cards) == 2 else [])
        ps = out['pass']
        assert ps['outcome'] == 'replica-exact', (spec, ps)
        assert [(s, d) for s, d, _st in ps['built']] == [(src, d) for d in cards for src in ('vae', 'audio_vae')], ps['built']
        assert all(st == 'stream-' + d for _s, d, st in ps['built'])
        assert ps['decoded_cards'] == sorted(cards) and all(len(v) == 10 for v in ps['per_card'].values()), ps
        assert ps['resident'] == {s: ['audio', 'video'] for s in slots}
        assert ps['keys'] == sorted([d + '_free_after_build' for d in cards] + [d + '_free_after_probe' for d in cards])
        assert ps['memory_before'] == sorted(cards + [d + '_free' for d in cards])
        for s in slots:
            assert s in ps['row_keys'] and s + '_matches_reference' in ps['row_keys']
        assert out['client_ok'] == [], (spec, out['client_ok'])
        assert all(v > 0 for v in out['client_other'].values()), (spec, out['client_other'])
        bad = out['bad']
        assert bad['outcome'] == 'replica-not-exact' and bad['passed'] is False, (spec, bad)
        assert sorted(d for d, _names in bad['released']) == sorted(cards), bad['released']
        assert all(names == ['audio', 'video'] for _d, names in bad['released'])
        assert sorted(bad['emptied']) == sorted(cards), bad['emptied']      # empty_cache on each replica's own card
        assert bad['resident'] == {s: [] for s in slots}
        assert bad['refused_mode'] and bad['latched'] is False
        assert bad['client'] == [], bad['client']    # a negative outcome on the right cards is still the right cards


case('probe: builds and checks every replica card, refuses a one-byte difference, releases per card, client checks cards',
     probe_case)


# =============================================================================================
# 5. headroom charges the chosen card(s)
# =============================================================================================
def headroom_case():
    h = load('wh97b', HERE / 'worker-headroom-97.py')
    G = 2**30
    assert h.pre_decode('xpu:2') == {'xpu:3': 1.9, 'xpu:2': 1.8}
    assert h.pre_decode('xpu:1,xpu:2') == {'xpu:3': 1.9, 'xpu:1': 1.8, 'xpu:2': 1.8}
    z = h.zero_worker_free('two-way', 'xpu:2')
    assert z['xpu:2'] == round(11.84 - 2.2, 3) and z['xpu:1'] == 10.78       # xpu:1 not credited (conservative)
    assert h.zero_worker_free('two-way', 'xpu:1,xpu:2') == z
    # live: xpu:2 short by a hair under spec xpu:2, fine under xpu:1; xpu:1 relieved of the replica room
    need2 = h.needed('two-way', 2, pool=0, spec='xpu:2')
    need1 = h.needed('two-way', 2, pool=0, spec='xpu:1')
    assert need2['xpu:2'] == need1['xpu:2'] + 1.8 and need2['xpu:1'] == need1['xpu:1'] - 1.8
    free = {c: int((max(need1[c], need2[c]) + 0.01) * G) for c in h.CARDS}
    free['xpu:2'] = int((need2['xpu:2'] - 0.01) * G)
    ok, short = h.live(free, 'two-way', 2, pool=0, spec='xpu:2')
    assert not ok and set(short) == {'xpu:2'}, short
    assert h.live(free, 'two-way', 2, pool=0, spec='xpu:1')[0] is True
    # plan: replica card room (4.51 GiB at the freeze) refuses xpu:2 on shard4-a, admits it on two-way
    assert h.plan('two-way', 2, 2, 1, None, 'xpu:2')[0] is True
    ok, d = h.plan('shard4-a', 3, 2, 1, None, 'xpu:2')
    assert not ok and set(d['replica_cards_short_of_probe_room']) == {'xpu:2'}, d
    assert h.REPLICA_MIN_FREE_GIB == 4.51
    try:
        h.replica_cards('xpu:0')
        raise AssertionError('xpu:0 admitted')
    except SystemExit:
        pass
    # packet 96 calibrations are not accepted (other manifest, other directory pattern)
    found = h.find_calibration(str(HERE.parent / 'data' / 'batch-96'), '6e232f72a9835727323c383bc9baaa167844b58dc6400a5de43a3b9eb4e44b9f',
                               'two-way', 2)
    assert found[0] is None, found
    with tempfile.TemporaryDirectory() as tmp:
        d1 = Path(tmp) / 'two-way-w2-b1-p1-dxpu2'
        d1.mkdir()
        rec = h.calibrate({c: 10 * G for c in h.CARDS}, {'xpu:0': 9.7 * G, 'xpu:1': 9.8 * G, 'xpu:2': 10 * G,
                                                          'xpu:3': 10 * G}, 'two-way', 1, 1, 'M97')
        rec.update(source_identity_sha256='s', source_identity_match=True)
        (d1 / 'pool-calibration.json').write_text(json.dumps(rec))
        got, path = h.find_calibration(tmp, 'M97', 'two-way', 2)
        assert got is not None and path.endswith('two-way-w2-b1-p1-dxpu2/pool-calibration.json')
        assert h.find_calibration(tmp, 'M96', 'two-way', 2)[0] is None
    # the CLI end to end
    r = subprocess.run([PY, '-B', str(HERE / 'worker-headroom-97.py'), 'plan', 'shard4-a', '3', '2', '1', '--replicas',
                        'xpu:2', '--manifest', 'x'], capture_output=True, text=True, timeout=120)
    assert r.returncode == 10 and json.loads(r.stdout)['replica_cards'] == ['xpu:2'], r.stdout[-400:]


case('headroom: replica room and freeze cost charged to the chosen card(s); 96 calibrations refused', headroom_case)


# =============================================================================================
# 6. failed-job receipts in every stage
# =============================================================================================
def failed_case():
    out = child('failed', {})
    stages = sorted(r['stage'] for r in out['recs'])
    assert stages == ['decode', 'encode', 'sample'], out['files']
    for r in out['recs']:
        assert r['schema'] == 'ltx.pipeline-failed-job.v1' and r['server_identity_sha256'] == 'f' * 64
        assert r['exception_type'] == 'ValueError' and r['exception_message'] == r['stage'] + ' broke'
        assert r['worker'].startswith('ltx-%s-' % r['stage']) and r['clip'] == r['index']
    samp = [r for r in out['recs'] if r['stage'] == 'sample'][0]
    assert samp['index'] == 903100 and samp['target'] == 'ltx-sample-0' and samp['worker'] == 'ltx-sample-0'
    assert all(f.startswith('pipeline-failed-%s-%d-' % (s, i)) for f, (s, i) in
               zip(out['files'], sorted((r['stage'], r['index']) for r in out['recs'])))
    assert out['tracebacks_full'] and len(out['log']) == 3, out['log']
    assert all('ValueError' in ln and 'receipt: ' in ln for ln in out['log'])
    assert out['checker_all'] == 3 and out['checker_sample'] == [903100] and out['checker_future'] == 0
    assert out['checker_rc'] == 3 and 'raise ValueError' in out['checker_text'] and 'FAILED JOB' in out['checker_text']
    assert out['unwritable'] is None and out['no_run_dir'] is None and out['after'] == 'still alive'


case('failed jobs: receipt and log line in every stage, before done; writer never raises; checker reads them',
     failed_case)


# =============================================================================================
# 7. the runner finds a failed-job file and stops
# =============================================================================================
def runner_case():
    sh = (HERE / 'run-campaign-97.sh').read_text()
    step = sh[sh.index('step() {'):sh.index('\n', sh.index('step() {')) + 1]
    fj = sh[sh.index('FAILED_SEEN=0\nMONITOR_FAILED=0\nfailed_jobs()'):sh.index('IDLE_N=0')]
    loop_start = sh.index('  for i in $(seq 1 180); do\n    [ -f $RUN/pipeline-done-sample-$IDX_K.json ] && break')
    loop = sh[loop_start:sh.index('\n  done\n', loop_start) + len('\n  done\n')].replace('seq 1 180', 'seq 1 3')
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        rec = {'schema': 'ltx.pipeline-failed-job.v1', 'stage': 'sample', 'index': 10010000, 'worker': 'ltx-sample-0',
               'exception_type': 'RuntimeError', 'exception_message': 'out of memory in capture',
               'traceback': 'Traceback (most recent call last):\n  File "x.py", line 1, in f\nRuntimeError: out of memory in capture\n'}
        script = ('set -u\nMODE=t\nPY=%s\nLANE=%s\nRUN=%s\nIDX_K=10010000\nk=0\n%s%s'
                  'finish() { echo "FINISH $1"; exit $1; }\nsleep() { :; }\n%s'
                  'echo "NO STOP"\n') % (PY, HERE.parent, run, step, fj, loop)
        (run / 'loop.sh').write_text(script)
        r0 = subprocess.run(['bash', str(run / 'loop.sh')], capture_output=True, text=True, timeout=300,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        assert 'NO STOP' in r0.stdout and r0.returncode == 0, r0.stdout[-500:]     # nothing failed: waits it out
        (run / 'pipeline-failed-sample-10010000-1791160000000.json').write_text(json.dumps(rec))
        t0 = time.time()
        r1 = subprocess.run(['bash', str(run / 'loop.sh')], capture_output=True, text=True, timeout=300,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        assert r1.returncode == 20 and 'FINISH 20' in r1.stdout, (r1.returncode, r1.stdout[-800:], r1.stderr[-500:])
        assert 'RuntimeError: out of memory in capture' in r1.stdout and 'FAILED JOB' in r1.stdout, r1.stdout
        assert time.time() - t0 < 60
    # the quiescence wait looks for receipts, and a failed job turns a clean finish into exit 20
    q = sh[sh.index('stop_when_proven() {'):sh.index('SUMMARY_RC=0')]
    assert '[ $fj -eq 0 ] && { step "failed pipeline job receipts found: not waiting for their done markers"; break; }' in q
    assert q.index('failed_jobs; fj=$?') < q.index('pipeline_idle_stable')    # idleness is still proven before the stop
    assert '[ $rc -eq 0 ] && [ $FAILED_SEEN = 1 ] && rc=20' in sh and '[ $rc -eq 0 ] && [ $MONITOR_FAILED = 1 ] && rc=22' in sh
    assert 'failed_jobs && step "$1: the failed pipeline job(s) above explain rc=$ARM_RC"' in sh
    # a broken monitor (helper crash or timeout) stops the capture pass with 22, through finish (graceful stop)
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        fake_lane = run / 'lane'
        (fake_lane / 'scripts').mkdir(parents=True)
        (fake_lane / 'scripts' / 'check-failed-jobs-97.py').write_text('import sys\nprint("Traceback: helper crashed")\nsys.exit(1)\n')
        script = ('set -u\nMODE=t\nPY=%s\nLANE=%s\nRUN=%s\nIDX_K=10010000\nk=0\n%s%s'
                  'finish() { echo "FINISH $1 MONITOR=$MONITOR_FAILED"; exit $1; }\nsleep() { :; }\n%s'
                  'echo "NO STOP"\n') % (PY, fake_lane, run, step, fj, loop)
        (run / 'loop.sh').write_text(script)
        r2 = subprocess.run(['bash', str(run / 'loop.sh')], capture_output=True, text=True, timeout=120,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        assert r2.returncode == 22 and 'FINISH 22 MONITOR=1' in r2.stdout and 'MONITOR BROKE' in r2.stdout, r2.stdout[-600:]
    assert '[ $fj -eq 2 ] && finish 22' in sh
    # timeouts derive from the prompt count for every arm; an expired arm widens the drain before the stop
    at = sh[sh.index('arm_timeouts() {'):sh.index('}\n', sh.index('arm_timeouts() {')) + 2]
    for n, want in ((1, '1803 2103'), (13, '1833 2133'), (120, '2100 2400'), (9000, '24300 24600')):
        r = subprocess.run(['bash', '-c', at + 'arm_timeouts %d' % n], capture_output=True, text=True)
        assert r.stdout.strip() == want, (n, r.stdout)
    assert 'timeout $ot $PY -B $LANE/scripts/run-throughput-fixtures-96.py' in sh and '--timeout $ct "${extra[@]}"' in sh
    assert 'if [ $ARM_RC -ne 0 ] && [ $ct -gt $DRAIN_S ]; then DRAIN_S=$ct; fi' in sh
    assert 'for i in $(seq 1 $(( (DRAIN_S + 9) / 10 ))); do' in q
    import re as _re
    calls = _re.findall(r'\n\s*arm f97-\S+ \S+ \S+ \S+ (\S+) ', sh)
    assert calls and set(calls) == {'auto'}, calls


case('runner: capture-pass wait stops at once with exit 20 and the traceback; quiescence and arms check receipts',
     runner_case)


def placement_check_case():
    chk = load('cdp97c', HERE / 'check-decode-placement-97.py')
    spec = 'xpu:2'
    rot = {'decode_replicas': 1, 'replica_devices': ['xpu:2'], 'replica_slots': ['replica'], 'native_device': 'xpu:3',
           'rotation': ['native', 'replica']}

    def arm(root, prefix, n, base, mode='pipeline-replica', sd=3, dd=2, slots=('native', 'replica')):
        devs = {'native': 'xpu:3', 'replica': 'xpu:2'}
        for i in range(n):
            name = '%s-%02d' % (prefix, i)
            d = root / 'requests' / name
            d.mkdir(parents=True)
            (d / 'submission.json').write_text('{}')
            (d / 'prompt.json').write_text(json.dumps({'426': {'inputs': {'mode': mode, 'depth': dd}},
                                                       '428': {'inputs': {'depth': sd, 'clip_index': base + i}}}))
            e = base + i - sd - dd if i >= sd + dd else -1
            det = {'emitted_index': e}
            if e < 0:
                det['fill'] = True
            else:
                s = slots[e % len(slots)] if mode == 'pipeline-replica' else 'native'
                det['decode_split'] = {'slot': s, 'device': devs[s]}
            (root / ('pipeline-decode-%s.json' % name)).write_text(json.dumps(
                {'passed': True, 'mode': mode, 'decode_replica': rot, 'detail': det}))

    def run(mutate=None, prefixes=('s', 'p', 't')):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arm(root, 's', 9, 10000100)
            arm(root, 'p', 13, 10000200, mode='pipeline-save', sd=2, dd=1)
            arm(root, 't', 30, 20000000)
            if mutate:
                mutate(root)
            c, bad, _per = chk.check(root, root, spec, list(prefixes))
            with contextlib.redirect_stdout(io.StringIO()):
                rc = chk.main(['--root', tmp, '--run', tmp, '--replicas', spec] + list(prefixes))
            return c, bad, rc
    c, bad, rc = run()
    assert bad == [] and rc == 0 and c == 4 + 10 + 25, (c, bad)
    # a missing timed receipt (valid self-check and probe receipts must not carry the check)
    c, bad, rc = run(lambda r: (r / 'pipeline-decode-t-17.json').unlink())
    assert rc == 4 and any('t-17: decode receipt missing' in b for b in bad), bad
    # a missing timed request in the middle
    import shutil
    c, bad, rc = run(lambda r: shutil.rmtree(r / 'requests' / 't-05'))
    assert rc == 4 and any('request numbers' in b for b in bad), bad

    def edit(name, fn):
        def m(root):
            f = root / ('pipeline-decode-%s.json' % name)
            d = json.loads(f.read_text())
            fn(d)
            f.write_text(json.dumps(d))
        return m
    for name, fn, why in (
            ('t-10', lambda d: d['detail'].update(emitted_index='20000005'), 'malformed emitted_index'),
            ('t-10', lambda d: d['detail'].update(emitted_index=True), 'malformed emitted_index'),
            ('t-10', lambda d: d['detail'].update(emitted_index=20000006), 'expected 20000005'),
            ('t-10', lambda d: d.update(mode='pipeline-moved'), 'receipt mode'),
            ('p-07', lambda d: d.update(mode='pipeline-replica'), 'receipt mode'),
            ('t-10', lambda d: d.update(passed=False), 'did not pass'),
            ('t-02', lambda d: d['detail'].pop('fill'), 'explicit fill'),
            ('t-10', lambda d: d['detail'].update(decode_split='not recorded (fill)'), 'expected on'),
            ('t-11', lambda d: d['detail'].update(decode_split={'slot': 'replica', 'device': 'xpu:1'}), 'expected on'),
            ('p-07', lambda d: d['detail'].update(decode_split={'slot': 'replica', 'device': 'xpu:2'}), 'expected on'),
            ('s-08', lambda d: d.update(decode_replica=dict(rot, replica_devices=['xpu:1'])), 'receipt placement')):
        c, bad, rc = run(edit(name, fn))
        assert rc == 4 and any(name in b and why in b for b in bad), (name, why, bad)
    # unreadable receipt, malformed graph, a mode outside the two admitted ones in the submitted graph
    c, bad, rc = run(lambda r: (r / 'pipeline-decode-t-12.json').write_text('{not json'))
    assert rc == 4 and any('t-12: decode receipt missing or unreadable' in b for b in bad), bad
    c, bad, rc = run(lambda r: (r / 'requests' / 't-12' / 'prompt.json').write_text('{}'))
    assert rc == 4 and any('t-12: submitted graph unreadable' in b for b in bad), bad
    def graph_mode(root):
        f = root / 'requests' / 't-12' / 'prompt.json'
        g = json.loads(f.read_text())
        g['426']['inputs']['mode'] = 'pipeline-child'
        f.write_text(json.dumps(g))
    c, bad, rc = run(graph_mode)
    assert rc == 4 and any('t-12: submitted graph mode' in b for b in bad), bad
    # an empty arm, and an arm of fills only
    c, bad, rc = run(prefixes=('s', 'p', 't', 'nothing'))
    assert rc == 4 and any('nothing: no submitted request' in b for b in bad), bad
    def fills_only(root):
        arm(root, 'f', 4, 10000300)
    c, bad, rc = run(fills_only, prefixes=('f',))
    assert rc == 4 and any('f: no emitted clip' in b for b in bad), bad


case('placement check: complete coverage per arm, passed flags, fills, modes vs graph, malformed and missing receipts',
     placement_check_case)


# =============================================================================================
# 8. agreement: generator, gate, runner, helpers
# =============================================================================================
def agreement_case():
    gen = (HERE / 'prepare-graph-capture-runtime.py').read_text()
    assert "OUTPUT = ROOT / 'prepared-encoder-place-97'" in gen
    man = json.loads((P97 / 'manifest.json').read_text())
    sha = hashlib.sha256((P97 / 'manifest.json').read_bytes()).hexdigest()
    sh = (HERE / 'run-campaign-97.sh').read_text()
    assert 'MANIFEST=%s' % sha in sh and 'P=$R/prepared-encoder-place-97' in sh
    import ltx_decode_replica as placement
    import ltx_pipeline as p
    dr = man['decode_replicas']
    assert dr['device_choices'] == list(placement.REPLICA_DEVICE_CHOICES) and dr['count_choices'] == list(placement.REPLICA_COUNT_CHOICES)
    assert dr['device_default'] == placement.DEFAULT_REPLICA_DEVICE and man['clip_index_max'] == p.CLIP_INDEX_MAX
    gate = gen[gen.index("    dr = manifest['decode_replicas']"):gen.index("    return manifest\n'''")]
    assert "dr['device_choices'] == ['xpu:1', 'xpu:2']" in gate and "manifest['clip_index_max'] == 100000000" in gate
    assert "pf['schema'] == 'ltx.pipeline-failed-job.v1'" in gate and p.FAILED_JOB_SCHEMA == 'ltx.pipeline-failed-job.v1'
    checker = (P97 / 'launch/encoder_runtime_common.py').read_text()
    assert gate.strip() in checker
    # the four specs everywhere
    specs = sorted(SPECS)
    h = load('wh97c', HERE / 'worker-headroom-97.py')
    assert sorted(h.REPLICA_SPECS) == specs
    assert sorted(load('cdp97b', HERE / 'check-decode-placement-97.py').SPECS) == specs
    assert "choices=('xpu:1', 'xpu:2', 'xpu:1,xpu:2', 'xpu:2,xpu:1')" in (HERE / 'run-decode-probe-97.py').read_text()
    assert 'case "$SPEC" in xpu:1) SI=0; NREP=1 ;; xpu:2) SI=1; NREP=1 ;; xpu:1,xpu:2) SI=2; NREP=2 ;; xpu:2,xpu:1) SI=3; NREP=2 ;;' in sh
    # run names, modes, tags and index bases from the runner's own parsing block
    parse = sh[sh.index('LAYOUT=${1:-}'):sh.index('TIMED_N=$TIMED_ARG')]
    rows = []
    script = 'set -u\n'
    combos = []
    for layout in ('two-way', 'shard4-a', 'shard3-c'):
        for w in (1, 2, 3, 4):
            for b in (1, 2, 4):
                for pool in (0, 1):
                    for spec in specs:
                        for rep in range(1, 10):
                            combos.append((layout, w, b, pool, spec, rep))
    body = 'f() {\n' + parse.replace('exit 8', 'return 8') + \
        'echo "$MODE $TAG $BASE $TIMED_BASE"\n}\n'
    script += body + ''.join('f %s %d %d %d %s %d 9000\n' % c for c in combos)
    r = subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-500:]
    rows = [ln.split() for ln in r.stdout.splitlines()]
    assert len(rows) == len(combos) == 2592
    shorts = sorted((int(x[2]), int(x[2]) + 999) for x in rows)
    timed = sorted((int(x[3]), int(x[3]) + 9999) for x in rows)
    assert all(a[1] < b[0] for a, b in zip(shorts, shorts[1:])) and all(a[1] < b[0] for a, b in zip(timed, timed[1:]))
    assert shorts[0][0] == 10000000 and shorts[-1][1] < 12592000 and timed[0][0] == 20000000
    assert timed[-1][1] < 45920000 <= p.CLIP_INDEX_MAX and shorts[-1][1] < timed[0][0]
    assert shorts[0][0] > 9190000 + 9000          # above every packet 96 / 96r index, even the >1M ones it planned
    assert len({x[0] for x in rows}) == 2592 and len({x[1] for x in rows}) == 2592
    named = {tuple(c): x for c, x in zip(combos, rows)}
    assert named[('two-way', 2, 1, 1, 'xpu:2', 1)][0] == 'two-way-w2-b1-p1-dxpu2'
    assert named[('two-way', 3, 2, 1, 'xpu:1,xpu:2', 3)][0] == 'two-way-w3-b2-p1-dxpu1xpu2-r3'
    assert named[('two-way', 2, 2, 1, 'xpu:2', 1)][1] == 'twowayw2b2p1dxpu2'
    for c, x in named.items():
        assert len('encoder-server-place-97-' + x[0]) <= 120 and len('f97-%s-timed' % x[1]) <= 90
    # the bash parser refuses what the allowlists refuse
    bad = 'f two-way 2 2 1 xpu:0\nf two-way 2 2 1 xpu:2 10\nf two-way 2 2 2 xpu:2\nf two-way 2 3 1 xpu:2\n'
    r = subprocess.run(['bash', '-c', 'set -u\n' + body + bad.replace('\n', ' || echo REFUSED\n')],
                       capture_output=True, text=True, timeout=60)
    assert r.stdout.count('REFUSED') == 4, r.stdout
    # the runner's helpers and env names
    for frag in ('worker-headroom-97.py plan $LAYOUT $WORKERS $BATCH $POOL --replicas $SPEC',
                 '"${PREV[@]}" --replicas $SPEC --manifest $MANIFEST', 'run-decode-probe-97.py f97-$TAG-dprobe',
                 '--expect-replicas $SPEC', 'check-decode-placement-97.py --root $R --run $RUN --replicas $SPEC',
                 'envval LTX_DECODE_REPLICA_DEVICE', 'envval LTX_DECODE_REPLICAS', 'LTX_DECODE_[A-Z_]+',
                 'NEOReadDebugKeys=1 EnableDeferBacking=0', 'RUN_NAME=encoder-server-place-97-$MODE',
                 'BASE_OUT=$LANE/data/place-97', 'missing-markers-96.py', 'summarize-campaign-96.py',
                 'run-throughput-fixtures-96.py', 'W93C=$LANE/data/stability-01-window-prereg.json',
                 'BPREREG=$LANE/data/stability-01-batch$BATCH-prereg.json'):
        assert frag in sh, frag
    assert 'make-batch-oracle-96.py' not in sh and 'git commit -q -m "LTX packet 97' in sh
    assert '-- "${OUT#$REPO/}" "$@"' in sh       # receipts committed by explicit path only
    r = subprocess.run(['bash', '-n', str(HERE / 'run-campaign-97.sh')], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


case('agreement: generator, gate, runner, helpers on specs, names, index bases, manifest and ceiling', agreement_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
