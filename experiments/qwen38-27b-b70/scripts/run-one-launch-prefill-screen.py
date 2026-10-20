#!/usr/bin/env python3
"""Persistent FP8 service adapter and separate guarded diagnostic client.

Default/--plan is CPU-only and writes nothing. --run refuses: host-controlled
benchmark lifecycle orchestration is prohibited. --serve-adapter owns one
persistent package server; --client-adapter only sends guarded requests.
Numerical runtime and client code are unchanged; stop is TERM-only.
"""
import argparse
from contextlib import ExitStack
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
SELF = Path(__file__).resolve()
PREREG = ROOT / 'experiments/qwen38-27b-b70/data/2026-10-20-one-launch-prefill-prereg.json'
SERVE = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
BENCH = SELF.with_name('bench-short-prefill.py')
MODEL = Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8').resolve()
OUT = Path('/mnt/usb-models/bench-results/fp8-one-launch-prefill-20261020')
LOCKS = ('/tmp/b70-benchmark.lock', '/tmp/b70-gpu0.lock', '/tmp/b70-gpu1.lock')
DEVICES = {'renderD130': '0000:23:00.0', 'renderD131': '0000:27:00.0'}
PORT = 18124


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def load_serve():
    spec = importlib.util.spec_from_file_location('fp8_package_serve', SERVE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_pins():
    prereg = json.loads(PREREG.read_text())
    for item in prereg['source_files']:
        actual = hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest()
        if actual != item['sha256']:
            raise RuntimeError('Preregistered source changed: ' + item['path'])
    overlays = sorted(str(p.relative_to(ROOT)) for p in (SERVE.parent.parent / 'overlays').rglob('*')
                      if p.is_file() and '__pycache__' not in p.parts)
    if overlays != prereg['overlay_files']:
        raise RuntimeError('Overlay inventory changed; refusing unpinned runtime input')
    return prereg


def client_argv(out):
    return [sys.executable, str(BENCH), '--base-url', f'http://127.0.0.1:{PORT}',
            '--model', 'qwen38-27b-fp8', '--out', str(out / 'screen'),
            '--lengths', '512', '--repeats', '2', '--max-tokens', '128',
            '--max-model-len', '33024', '--timeout', '120']


def guarded_client(out):
    """Original client and requests; a passive fault check before every fetch."""
    verify_pins()
    verify_ready_server(out)
    spec = importlib.util.spec_from_file_location('prefill_client', BENCH)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    module = load_serve()
    original_fetch = client.fetch
    since = json.loads((out / 'server/state.json').read_text())['started_at']

    def fetch(*args, **kwargs):
        disk_floors(out)
        kernel = module.journal(since)
        (out / 'client-guard-kernel.log').write_text(kernel)
        bad = [line for line in kernel.splitlines() if module.FAULT.search(line)]
        if bad:
            fault = out / 'FAULT.json'
            if not fault.exists():
                dump(fault, {'at': now(), 'lines': bad, 'new_requests_halted': True,
                             'detector': 'per-request-client-guard'})
            raise RuntimeError('Kernel fault; client admission halted')
        return original_fetch(*args, **kwargs)

    client.fetch = fetch
    client.run(argparse.Namespace(base_url=f'http://127.0.0.1:{PORT}', model='qwen38-27b-fp8',
        out=out / 'screen', baseline=None, lengths='512', repeats=2, max_tokens=128,
        max_model_len=33024, timeout=120))


def plan(out):
    module = load_serve()
    prereg = verify_pins()
    state = out / 'server'
    return {'scope': prereg['scope'], 'preregistration': str(PREREG),
            'preregistration_sha256': hashlib.sha256(PREREG.read_bytes()).hexdigest(),
            'source_files': prereg['source_files'], 'host': 'steve-b70s',
            'device_pci_mapping': DEVICES, 'locks': list(LOCKS), 'out': str(out),
            'launch_argv_template': module.docker_argv('recommended', MODEL, state, PORT, 'OWNED-UUID'),
            'client_argv': client_argv(out),
            'guarded_client_argv': [sys.executable, str(SELF), '--client-adapter', '--out', str(out)],
            'client_adapter': 'Passive journal check before every HTTP admission; adds overhead to HTTP proxy only',
            'lifecycle_adapter': 'TERM only; owned container; no timed KILL',
            'bounds_seconds': {'model_verification': 1200, 'startup': 1800, 'graceful_container_wait': 180},
            'disk_free_floors_gib': {'root': 5, 'output': 30},
            'image_policy': 'verify cached pinned image before serving; no pull/build',
            'lifecycle': 'manual coordinator: one persistent service, separate client, one owned graceful stop',
            'active_health': 'none; passive journal/endpoint checks only',
            'no_quality_loss_gate': False, 'strict_headline_eligible': False}


def disk_floors(out):
    # Run-only floors: cached image already exists; no build or pull. New
    # vLLM cache and all output use the separately mounted output filesystem.
    if shutil.disk_usage(ROOT).free < 5 * 1024**3:
        raise RuntimeError('Root filesystem below run-only 5 GiB floor; halt without deleting artifacts')
    if shutil.disk_usage(out if out.exists() else out.parent).free < 30 * 1024**3:
        raise RuntimeError('Output filesystem below 30 GiB floor; halt without deleting artifacts')


def term_only_stop(module, state, record, *, clock=time.monotonic, sleep=time.sleep):
    """Same ownership receipt protocol, but TERM plus passive inspection only."""
    with (state / 'stop.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = state / 'stop-request.json'
        if receipt.exists():
            return
        identity = record.get('container_id')
        if not identity:
            raise RuntimeError('No captured container identity; refusing any container signal')
        container = module.inspect_container(identity)
        if container is None:
            dump(receipt, {'at': now(), 'container_id': identity, 'already_absent': True})
            return
        module.owned(record, container)
        dump(receipt, {'at': now(), 'container_id': identity, 'requested': True,
                       'signal': 'SIGTERM', 'escalation': 'none', 'wait_seconds': 180})
        if container['State']['Running']:
            result = module.run(['docker', 'kill', '--signal=TERM', identity], check=False, timeout=30)
            (state / 'stop.log').write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError('Owned TERM request failed; no signal retry')
        deadline = clock() + 180
        while clock() < deadline:
            container = module.inspect_container(identity)
            if container is None or not container['State']['Running']:
                dump(state / 'graceful-stop.json', {'at': now(), 'stopped': True, 'escalation': False})
                return
            module.owned(record, container)
            sleep(2)
        dump(state / 'graceful-stop.json', {'at': now(), 'stopped': False, 'escalation': False,
                                          'operator_action_required': True})
        raise RuntimeError('Owned container still running after TERM; halted without KILL or restart')



def host_guard():
    if socket.gethostname() != 'steve-b70s' or not os.environ.get('INVOCATION_ID'):
        raise RuntimeError('Use a systemd user unit on steve-b70s; foreground SSH is not supported')
    for node, pci in DEVICES.items():
        if (Path('/sys/class/drm') / node / 'device').resolve().name != pci:
            raise RuntimeError('Render-node mapping changed; aborting')


def passive_journal(module, out, label, since):
    text = module.journal(since)
    (out / f'{label}-kernel.log').write_text(text)
    bad = [line for line in text.splitlines() if module.FAULT.search(line)]
    if bad:
        if not (out / 'FAULT.json').exists():
            dump(out / 'FAULT.json', {'at': now(), 'lines': bad, 'new_requests_halted': True})
        raise RuntimeError('Kernel fault; no new requests or launches')
    disk_floors(out)


def verify_ready_server(out):
    """Client admission checks receipts and endpoint, without lifecycle actions."""
    module = load_serve()
    record = module.read_record(out / 'server')
    if record.get('status') != 'ready' or record.get('profile') != 'recommended' or record.get('port') != PORT:
        raise RuntimeError('Expected persistent recommended-profile server is not ready')
    identity = json.loads((out / 'identity.json').read_text())
    if identity['source_files'] != verify_pins()['source_files']:
        raise RuntimeError('Serving source identity differs from client preregistration')
    actual = json.loads((out / 'server/launch.json').read_text())['argv']
    expected = module.docker_argv('recommended', MODEL, out / 'server', PORT, record['container_name'])
    if actual != expected:
        raise RuntimeError('Persistent server argv differs from package identity')
    container = module.inspect_container(record['container_id'])
    if container is None or not container['State']['Running']:
        raise RuntimeError('Owned server container is not running')
    module.owned(record, container)
    passive_journal(module, out, 'client-admission', record['started_at'])
    if not module.healthy(PORT):
        raise RuntimeError('Persistent server passive HTTP health failed')


def adapter(out):
    """One persistent service; no benchmark clients, active probes or retries."""
    host_guard()
    os.environ['B70_FP8_RENDER_NODES'] = ','.join(DEVICES)
    prereg = verify_pins()
    module = load_serve()
    with ExitStack() as stack:
        locks = [stack.enter_context(open(p, 'a')) for p in LOCKS]
        for lock in locks:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        disk_floors(out)
        out.mkdir(parents=True, exist_ok=False)
        identity = plan(out)
        identity['started_at'] = now()
        dump(out / 'identity.json', identity)
        dump(out / 'before-host.json', {'at': now(), 'hostname': socket.gethostname(),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'uname': list(os.uname()), 'meminfo': Path('/proc/meminfo').read_text(),
            'swaps': Path('/proc/swaps').read_text(),
            'disk_free_bytes': {'root': shutil.disk_usage(ROOT).free, 'output': shutil.disk_usage(out).free}})
        passive_journal(module, out, 'before-recent', '10 minutes ago')
        os.environ['B70_FP8_RENDER_NODES'] = ','.join(DEVICES)
        module.check_available(PORT, 'prefill-passive-ownership-check')
        dump(out / 'local-image.json', {'local_image_id': module.local_image_id(),
                                       'registry_image': module.IMAGE, 'pull_attempted': False})
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        if int(mem['MemAvailable'].split()[0]) < 16 * 1024 * 1024:
            raise RuntimeError('Less than16 GiB available host RAM; no launch')
        verifier = [sys.executable, str(ROOT / 'repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py'),
                    str(ROOT / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json'), str(MODEL),
                    '--json', str(out / 'model-verification.json')]
        dump(out / 'model-verification-command.json', {'argv': verifier})
        with (out / 'model-verification.log').open('x') as log:
            subprocess.run(verifier, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1200)
        passive_journal(module, out, 'before-start', identity['started_at'])
        verify_pins()
        module.stop_owned = lambda state, record: term_only_stop(module, state, record)
        original_docker_argv = module.docker_argv
        def checked_docker_argv(profile, model, state, port, name):
            actual = original_docker_argv(profile, model, state, port, name)
            expected = identity['launch_argv_template'].copy()
            expected[expected.index('--name') + 1] = name
            if actual != expected:
                raise RuntimeError('Runtime argv differs from the preregistered package plan')
            dump(out / 'launch-identity-check.json', {'matched': True, 'argv': actual})
            return actual
        module.docker_argv = checked_docker_argv
        original_journal = module.journal
        def monitored_journal(since):
            text = original_journal(since)
            disk_floors(out)
            return text
        module.journal = monitored_journal
        original_warmup = module.warm_up
        def guarded_warmup(port):
            passive_journal(module, out, 'before-warmup', identity['started_at'])
            return original_warmup(port)
        module.warm_up = guarded_warmup
        error = None
        try:
            module.start(argparse.Namespace(model_dir=MODEL, state_dir=out / 'server',
                profile='recommended', port=PORT, startup_timeout=1800))
        except Exception as exc:
            error = str(exc)
        finally:
            drained = False
            state = out / 'server/state.json'
            try:
                if state.exists():
                    record = json.loads(state.read_text())
                    container = module.inspect_container(record.get('container_id') or record['container_name'])
                    drained = container is None or not container['State']['Running']
                    if container is not None and record.get('container_id'):
                        module.owned(record, container)
                else:
                    drained = True
                (out / 'after-kernel.log').write_text(original_journal(identity['started_at']))
            except Exception as exc:
                error = error or str(exc)
            dump(out / 'server-lifecycle.json', {'at': now(), 'error': error, 'drained': drained,
                'server_attempts': 1, 'no_retry': True, 'no_sigkill': True,
                'client_automatically_started': False, 'active_probes': False,
                'holding_locks_for_operator': not drained})
            if not drained:
                dump(out / 'HALTED.json', {'at': now(), 'locks_held': True,
                    'new_work_admission_stopped': True,
                    'release': 'operator signal to controller; does not kill remaining container'})
                released = []
                for sig in (signal.SIGTERM, signal.SIGINT):
                    signal.signal(sig, lambda signum, frame: released.append(signum))
                print('HALTED: owned work did not drain; holding locks until operator signal', flush=True)
                while not released:
                    signal.pause()
        if error:
            raise RuntimeError(error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--run', action='store_true', help='Refused: host-controlled benchmark orchestration is prohibited')
    mode.add_argument('--serve-adapter', action='store_true', help='One persistent server service; holds host/GPU locks')
    mode.add_argument('--client-adapter', action='store_true', help='Client only; never starts or stops the server')
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.run:
        raise RuntimeError('Host-controlled benchmark wrappers are prohibited: --run refuses; use separately reviewed persistent service and client modes')
    if args.serve_adapter:
        adapter(out)
    elif args.client_adapter:
        host_guard()
        guarded_client(out)
    else:
        print(json.dumps(plan(out), indent=2))


if __name__ == '__main__':
    main()
