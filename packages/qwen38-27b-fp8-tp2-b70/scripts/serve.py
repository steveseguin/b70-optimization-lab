#!/usr/bin/env python3
"""One persistent, pinned FP8 server. No restart or recovery policy."""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh'
IMAGE_ID = 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2'
IMAGE = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@' + IMAGE_ID
KERNEL = '6d92b1bfbf32767ecda8e819613eb151e70030ad'
MODEL = 'qwen38-27b-fp8'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def clean_env():
    env = {k: os.environ[k] for k in ('HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL') if k in os.environ}
    env.update(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
               DOCKER_HOST='unix:///var/run/docker.sock')
    return env


def run(args, check=True, timeout=30):
    return subprocess.run(args, env=clean_env(), text=True, capture_output=True,
                          check=check, timeout=timeout)


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def inspect_container(identity):
    result = run(['docker', 'container', 'inspect', identity], check=False)
    if result.returncode:
        if 'No such' in result.stderr:
            return None
        raise RuntimeError('Docker inspection failed: ' + result.stderr.strip())
    return json.loads(result.stdout)[0]


def owned(record, container):
    """Never substitute a same-named replacement for the stored container."""
    if (container['Id'] != record['container_id'] or
            container['Name'].lstrip('/') != record['container_name'] or
            container['Image'] != IMAGE_ID):
        raise RuntimeError('Container ownership or image does not match the saved receipt; refusing action.')


def capture_owned(state, record):
    if record['container_id']:
        return
    container = inspect_container(record['container_name'])
    if container is not None:
        record['container_id'] = container['Id']
        owned(record, container)
        write_json(state / 'container-inspect.json', container)
        write_json(state / 'state.json', record)


def read_record(state):
    record = json.loads((state / 'state.json').read_text())
    if record.get('schema') != 'neural.download.fp8-serving-state.v1' or record.get('image_id') != IMAGE_ID:
        raise RuntimeError('Unrecognized state receipt.')
    return record


def stop_owned(state, record):
    """Serialize stop requests and issue at most one graceful stop."""
    with (state / 'stop.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = state / 'stop-request.json'
        if receipt.exists():
            return
        identity = record.get('container_id')
        if not identity:
            raise RuntimeError('Container identity is not yet recorded; use Ctrl+C in the start terminal.')
        container = inspect_container(identity)
        if container is None:
            write_json(receipt, {'at': now(), 'container_id': identity, 'already_absent': True})
            return
        owned(record, container)
        write_json(receipt, {'at': now(), 'container_id': identity, 'requested': True})
        result = run(['docker', 'stop', '--time', '30', identity], check=False, timeout=45)
        (state / 'stop.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('Graceful stop failed; see stop.log. No retry was attempted.')


def runtime_env(model, state, port, name):
    env = clean_env()
    env.update(IMAGE=IMAGE, EXPECTED_IMAGE_ID=IMAGE_ID, EXPECTED_KERNEL_HEAD=KERNEL,
               EXPECTED_XPU_EXTENSION_SHA256='bbce7295fb8a58bad456675cfac7cdf3d1e29fe7a9dd5c0970741b130616c932',
               EXPECTED_XPU_OPS_SHA256='6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3',
               MODEL_DIR=str(model), VLLM_CACHE_DIR=str(state / 'cache'), PORT=str(port),
               CONTAINER_NAME=name, SERVED_MODEL_NAME=MODEL, TENSOR_PARALLEL_SIZE='2',
               XPU_DEVICE_MASK='0,1', MAX_MODEL_LEN='33024', MAX_NUM_SEQS='1',
               MAX_NUM_BATCHED_TOKENS='4096', GPU_MEMORY_UTILIZATION='0.95',
               CONTAINER_MEMORY='12g', CONTAINER_MEMORY_SWAP='16g',
               VLLM_USE_V2_MODEL_RUNNER='0', VLLM_XPU_FP16_LINEAR_CLASSPAD='0',
               VLLM_XPU_FP16_LINEAR_ROWCHUNK='32', VLLM_XPU_ENABLE_XPU_GRAPH='0')
    return env


def check_available(port, name):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))
    if inspect_container(name) is not None:
        raise RuntimeError('Selected container name already exists.')
    nodes = sorted(Path('/dev/dri').glob('renderD*'))
    if len(nodes) != 2:
        raise RuntimeError('This profile requires exactly two exposed render devices; device remapping is outside this guide.')
    result = run(['fuser', *map(str, nodes)], check=False)
    if result.returncode != 1 or result.stdout.strip():
        raise RuntimeError('A render device is in use or ownership could not be checked; preserve the active GPU work.')
    # A just-starting container may not have opened the device yet.
    ids = run(['docker', 'ps', '-q']).stdout.split()
    if ids:
        containers = json.loads(run(['docker', 'inspect', *ids]).stdout)
        for container in containers:
            host = container.get('HostConfig', {})
            devices = host.get('Devices') or []
            if host.get('Privileged') or host.get('DeviceRequests') or any('/dev/dri' in d.get('PathOnHost', '') for d in devices):
                raise RuntimeError('Another running container has GPU access; preserve the active lane.')


def journal(since):
    result = run(['journalctl', '-k', '--since', since, '--no-pager', '-o', 'short-iso'], check=False)
    if result.returncode or re.search(r'permission|not seeing messages|No journal files', result.stderr, re.I):
        raise RuntimeError('Cannot read the kernel journal for fault monitoring; configure read access before starting.')
    return result.stdout


def healthy(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def status(state, record):
    identity = record.get('container_id')
    container = inspect_container(identity) if identity else None
    if container is not None:
        owned(record, container)
    running = bool(container and container['State']['Running'])
    return {'status': record['status'], 'container_present': container is not None,
            'container_running': running, 'api_healthy': healthy(record['port']) if running else False,
            'endpoint': f'http://127.0.0.1:{record["port"]}/v1',
            'model': MODEL, 'error': record.get('error'), 'state_dir': str(state)}


def start(args):
    model, state = args.model_dir.resolve(), args.state_dir.resolve()
    if not model.is_dir():
        raise RuntimeError('Model directory does not exist.')
    if model == state or model in state.parents or state in model.parents:
        raise RuntimeError('Model and serving state must be separate directories.')
    name = 'neural-fp8-' + uuid.uuid4().hex
    with open('/tmp/qwen-short-prefill-stage.lock', 'a') as global_lock:
        fcntl.flock(global_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check_available(args.port, name)
        since = now()
        journal(since)  # Fail before launch if fault monitoring is unavailable.
        state.mkdir(parents=True, exist_ok=False)
        (state / 'cache').mkdir()
        with (state / 'owner.lock').open('x') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record = {'schema': 'neural.download.fp8-serving-state.v1', 'started_at': since,
                      'owner_pid': os.getpid(), 'container_name': name, 'container_id': None,
                      'image_id': IMAGE_ID, 'model': MODEL, 'model_dir': str(model),
                      'state_dir': str(state), 'port': args.port, 'status': 'starting'}
            write_json(state / 'state.json', record)
            env = runtime_env(model, state, args.port, name)
            write_json(state / 'launch.json', {'argv': ['bash', str(LAUNCHER)],
                                              'environment': {k: v for k, v in env.items() if k not in clean_env()}})
            shutdown = []
            previous = {s: signal.signal(s, lambda signum, frame: shutdown.append(signum))
                        for s in (signal.SIGINT, signal.SIGTERM)}
            child = None
            failed = None
            print(f'Starting one server. Logs: {state / "server.log"}', flush=True)
            try:
                with (state / 'server.log').open('x') as log:
                    child = subprocess.Popen(['bash', str(LAUNCHER)], cwd=ROOT, env=env,
                                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    deadline = time.monotonic() + args.startup_timeout
                    while True:
                        capture_owned(state, record)
                        if shutdown:
                            break
                        kernel = journal(since)
                        (state / 'kernel.log').write_text(kernel)
                        if FAULT.search(kernel):
                            raise RuntimeError('New GPU fault detected. Halting this server; evidence retained in kernel.log.')
                        if child.poll() is not None:
                            if not (state / 'stop-request.json').exists():
                                raise RuntimeError(f'Server process exited ({child.returncode}); see server.log. No restart attempted.')
                            break
                        if record['status'] == 'starting':
                            if record['container_id'] and healthy(args.port):
                                record.update(status='ready', ready_at=now())
                                write_json(state / 'state.json', record)
                                print(f'Ready: http://127.0.0.1:{args.port}/v1\nModel: {MODEL}\nLeave this terminal open. Ctrl+C stops this owned server.', flush=True)
                            elif time.monotonic() > deadline:
                                raise RuntimeError('Startup deadline reached; see server.log. No restart attempted.')
                        time.sleep(2)
            except Exception as exc:
                failed = str(exc)
            finally:
                try:
                    if child is not None:
                        capture_owned(state, record)
                        if record['container_id']:
                            stop_owned(state, record)
                        elif child.poll() is None:
                            # Before docker creates the named server, terminate only our launcher group.
                            os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=45)
                        except subprocess.TimeoutExpired:
                            failed = failed or 'Owned launcher did not exit after graceful stop; no kill or retry attempted.'
                        # Cover a Ctrl+C arriving while docker was creating its container.
                        if not record['container_id']:
                            capture_owned(state, record)
                            if record['container_id']:
                                stop_owned(state, record)
                except Exception as exc:
                    failed = failed or str(exc)
                record.update(status='failed' if failed else 'stopped', finished_at=now(), error=failed)
                write_json(state / 'state.json', record)
                for s, handler in previous.items():
                    signal.signal(s, handler)
            if failed:
                raise RuntimeError(failed)
            print(f'Stopped. Logs and receipts preserved in {state}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('start', 'status', 'stop'):
        item = sub.add_parser(command)
        item.add_argument('--state-dir', type=Path, required=True)
        if command == 'start':
            item.add_argument('--model-dir', type=Path, required=True)
            item.add_argument('--port', type=int, default=18124)
            item.add_argument('--startup-timeout', type=int, default=1800)
    args = parser.parse_args()
    try:
        if args.command == 'start':
            if not 1024 <= args.port <= 65535 or args.startup_timeout < 1:
                raise RuntimeError('Use a port from 1024–65535 and a positive startup timeout.')
            start(args)
        else:
            state = args.state_dir.resolve()
            record = read_record(state)
            if args.command == 'stop':
                stop_owned(state, record)
                print('Graceful stop requested for the saved container only. No restart is scheduled.')
            else:
                print(json.dumps(status(state, record), indent=2))
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
