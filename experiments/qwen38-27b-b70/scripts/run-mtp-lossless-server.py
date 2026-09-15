#!/usr/bin/env python3
"""Own one MTP-only research server; monitor faults; no retries or successors."""
from __future__ import annotations
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[3]
CONTROL_IMAGE = 'sha256:506fcc26897b12915cb9e27c28e0adc256d278666fa745602a1ae5e1dd8ea066'
ORIGINAL = Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/control-identity.json')
MODEL_DIR = Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
# Every qualified FP8 service container sets these; ORIGINAL's recorded env
# omits them. The 2026-09-14 launch without them exhausted host RAM while the
# model was constructed (notes/2026-09-15-research-load-host-oom.md).
QUALIFIED_ENV = {'PYTORCH_ALLOC_CONF': 'expandable_segments:True', 'FI_PROVIDER': 'tcp',
                 'FI_TCP_IFACE': 'lo', 'PYTHONHASHSEED': '0', 'TORCHINDUCTOR_DETERMINISTIC': '1'}
GUARD = Path(__file__).with_name('host_memory_guard.py')
PASSWORD_FILE = Path('/home/steve/SUDO_PASSWORD.txt')


def qualified_env(control):
    env = dict(e.split('=', 1) for e in control['env'])
    conflicts = sorted(key for key, value in QUALIFIED_ENV.items() if key in env and env[key] != value)
    if conflicts:
        raise RuntimeError('Recorded contract conflicts with the qualified environment: ' + ', '.join(conflicts))
    return {**env, **QUALIFIED_ENV}


def load_guard():
    spec = importlib.util.spec_from_file_location('host_memory_guard', GUARD)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def start_guard(container_id, out, baseline):
    """Root guard kills the container cgroup on driver-held RAM growth; no Docker calls."""
    proc = subprocess.Popen(['sudo', '-S', '-p', '', 'python3', str(GUARD), '--container-id', container_id,
                             '--out', str(out), '--baseline-unaccounted', str(baseline)],
                            stdin=subprocess.PIPE, text=True, start_new_session=True)
    proc.stdin.write(PASSWORD_FILE.read_text().strip() + '\n'); proc.stdin.close()
    return proc


def write(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)


def snapshot_extensions(directory, out):
    """Freeze only reviewed Python inputs; never mount the mutable repository."""
    snapshot = out / 'research-extension'
    snapshot.mkdir(exist_ok=False)
    hashes = {}
    for filename in ('mtp_transfer_worker.py', 'mtp_native_metadata_gate.py'):
        data = (directory / filename).read_bytes()
        compile(data, filename, 'exec')  # Syntax check only; no imports executed.
        target = snapshot / filename
        with target.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        target.chmod(0o444)
        hashes[filename] = hashlib.sha256(data).hexdigest()
    snapshot.chmod(0o555)
    return snapshot, hashes


def verify_owned(info, state):
    if (info['Name'].lstrip('/') != state['container_name']
            or info['Image'] != state['image_id']
            or (state.get('container_id') and info['Id'] != state['container_id'])):
        raise RuntimeError('Container ownership differs; refusing action')
    state['container_id'] = info['Id']


def stop_owned_server(helper, child, out, state, failure):
    """One owned-container stop; preserve uncertainty instead of claiming stopped."""
    receipt = {'at': helper.now(), 'stop_attempted': False, 'errors': []}
    confirmed = False
    try:
        before = helper.inspect_container(state.get('container_id') or state['container_name'])
        if before is not None:
            verify_owned(before, state)
            write(out / 'container-before-stop.json', before)
            if before['State']['Running']:
                receipt['stop_attempted'] = True
                try:
                    result = helper.run(['docker', 'stop', '--time', '120', before['Id']], check=False, timeout=150)
                    receipt.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
                except Exception as exc:
                    receipt['errors'].append(f'{type(exc).__name__}: {exc}')
            after = helper.inspect_container(before['Id'])
            if after is not None:
                verify_owned(after, state)
                write(out / 'container-inspect.json', after)
                confirmed = not after['State']['Running']
            else:
                confirmed = True  # Docker positively reported that this ID is absent.
        else:
            confirmed = child.poll() is not None
        try:
            receipt['client_returncode'] = child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            confirmed = False
            receipt['errors'].append('Docker client exit unconfirmed after 10 seconds')
    except Exception as exc:
        confirmed = False
        receipt['errors'].append(f'{type(exc).__name__}: {exc}')
    receipt['stop_confirmed'] = confirmed
    write(out / 'stop.json', receipt)
    if not confirmed:
        (out / 'STOP_UNCONFIRMED').write_text('Owned container or client exit unconfirmed; do not start a successor\n')
        state.update(status='stop_unconfirmed', stop_error=receipt['errors'])
    elif failure is None:
        state.update(status='stopped', stopped_at=helper.now())
    else:
        state.update(status='failed', stop_confirmed=True, stopped_at=helper.now())
    write(out / 'state.json', state)
    return confirmed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=18129)
    ap.add_argument('--startup-timeout', type=int, default=1200)
    ap.add_argument('--research-extension', action='store_true')
    a = ap.parse_args()
    out = a.out.resolve()
    if (out.parent/'FAULT.json').exists():
        raise RuntimeError('Campaign fault latch: no new server allowed')
    qualified_env(json.loads(ORIGINAL.read_text()))  # Refuse a conflicting contract before any side effect.
    spec = importlib.util.spec_from_file_location('qualified_serve_helpers', ROOT/'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    lock = open('/tmp/qwen-short-prefill-stage.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    name = 'mtp-lossless-' + uuid.uuid4().hex
    helper.check_available(a.port, name)
    started = helper.now(); helper.journal(started)
    out.mkdir(parents=True, exist_ok=False); (out/'cache').mkdir()
    control = json.loads(ORIGINAL.read_text())
    env = qualified_env(control)
    if env.get('VLLM_USE_V2_MODEL_RUNNER') != '0' or env.get('VLLM_XPU_DRAFT_LM_HEAD_INT4') != '1':
        raise RuntimeError('Original native MTP arithmetic settings changed')
    args = list(control['command'])
    draft = json.loads(args[args.index('--speculative-config') + 1])
    if draft != {'method': 'qwen3_next_mtp', 'num_speculative_tokens': 1}:
        raise RuntimeError('Only unchanged native MTP1 is admitted')
    cmd = ['docker', 'run', '--name', name, '--restart', 'no', '--network', 'bridge',
           '--device', '/dev/dri', '--group-add', 'render', '--ipc', 'host',
           '--cap-add', 'SYS_PTRACE',  # Preserved qualified pidfd IPC capability.
           '--shm-size', '8g', '--memory', '12g', '--memory-swap', '16g',
           '--ulimit', 'core=0', '--security-opt', 'label=disable',
           '-p', f'127.0.0.1:{a.port}:8000', '--workdir', '/',
           '--mount', f'type=bind,source={MODEL_DIR},target=/model,readonly',
           '--mount', f'type=bind,source={out}/cache,target=/root/.cache/vllm']
    extensions = {}
    if a.research_extension:
        directory = ROOT/'experiments/qwen38-27b-b70/probes/mtp-metadata-20260914'
        snapshot, extensions = snapshot_extensions(directory, out)
        cmd += ['--mount', f'type=bind,source={snapshot},target=/research,readonly']
        env.update(PYTHONPATH='/research', VLLM_SERVER_DEV_MODE='1')
        args += ['--worker-extension-cls', 'mtp_transfer_worker.MtpTransferWorkerExtension']
    for key, value in sorted(env.items()):
        cmd += ['--env', f'{key}={value}']
    cmd += [CONTROL_IMAGE] + args
    image = helper.run(['docker', 'image', 'inspect', CONTROL_IMAGE])
    write(out/'image.json', json.loads(image.stdout))
    write(out/'launch.json', {'argv': cmd, 'started': started, 'extensions': extensions,
         'scope': 'new upstream native-MTP control; optional localhost-only research RPC; starts unwrapped control',
         'original_control_sha256': hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
         'qualified_env_added': sorted(QUALIFIED_ENV),
         'memory_guard_sha256': hashlib.sha256(GUARD.read_bytes()).hexdigest()})
    state = {'status': 'starting', 'owner_pid': os.getpid(), 'container_name': name,
             'image_id': CONTROL_IMAGE, 'port': a.port, 'started_at': started,
             'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    write(out/'state.json', state)
    stopped = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: stopped.append(signum))
    child = None; failure = None; ready = False; guard_proc = None
    memory_guard = load_guard()
    baseline = memory_guard.unaccounted_bytes(memory_guard.parse_meminfo(Path('/proc/meminfo').read_text()))
    try:
        with (out/'server.log').open('x') as log, (out/'memory.jsonl').open('x') as memory:
            child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=helper.clean_env())
            deadline = time.monotonic() + a.startup_timeout
            last_memory = 0
            while not stopped and not (out/'STOP').exists():
                journal = helper.journal(started)
                (out/'kernel.log').write_text(journal)
                bad = [line for line in journal.splitlines() if helper.FAULT.search(line)]
                if bad:
                    write(out.parent/'FAULT.json', {'at': helper.now(), 'lines': bad})
                    raise RuntimeError('Kernel fault; no new requests or successor')
                if child.poll() is not None:
                    raise RuntimeError(f'Server exited {child.returncode}; no retry')
                if time.monotonic()-last_memory >= 10:
                    info = helper.inspect_container(name)
                    entry = {'at': helper.now(), 'host_meminfo': Path('/proc/meminfo').read_text()}
                    if info:
                        verify_owned(info, state)
                        pid = info['State']['Pid']
                        try:
                            group = next(s.split(':', 2)[2] for s in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if s.startswith('0::'))
                            cg = Path('/sys/fs/cgroup')/group.lstrip('/')
                            entry['cgroup'] = {n:(cg/n).read_text().strip() for n in ('memory.current','memory.peak','memory.events','memory.swap.current') if (cg/n).exists()}
                        except (OSError, StopIteration):
                            entry['cgroup'] = 'unavailable'
                    memory.write(json.dumps(entry)+'\n'); memory.flush(); os.fsync(memory.fileno())
                    last_memory = time.monotonic()
                if guard_proc is None and state.get('container_id'):
                    guard_proc = start_guard(state['container_id'], out, baseline)
                if guard_proc is not None and guard_proc.poll() not in (None, 0):
                    raise RuntimeError(f'Host memory guard exited {guard_proc.returncode}; see MEMORY-GUARD.json; no retry')
                if not ready:
                    if state.get('container_id') and helper.healthy(a.port):
                        ready = True; state.update(status='ready', ready_at=helper.now())
                        write(out/'state.json', state); print(f'Ready: http://127.0.0.1:{a.port}/v1', flush=True)
                    elif time.monotonic() > deadline:
                        raise TimeoutError('Startup deadline exceeded; no retry')
                time.sleep(2)
    except BaseException as exc:
        failure = f'{type(exc).__name__}: {exc}'
        state.update(status='failed', error=failure); write(out/'state.json', state)
        raise
    finally:
        confirmed = True
        try:
            if child is not None:
                confirmed = stop_owned_server(helper, child, out, state, failure)
        finally:
            lock.close()
        if not confirmed and failure is None:
            raise RuntimeError('Owned server shutdown unconfirmed; no successor allowed')



if __name__ == '__main__':
    main()
