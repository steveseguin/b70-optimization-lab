#!/usr/bin/env python3
"""One persistent, pinned two-card FP8 server (Qwen3.8 27B, two Intel Arc Pro B70). No restart or recovery policy."""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

PACKAGE = Path(__file__).resolve().parents[1]
IMAGE_ID = 'sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
IMAGE = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@' + IMAGE_ID
MODEL = 'qwen38-27b-fp8'
SHORTLIST = '/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)

# Both profiles: two cards, one user, 33,024 total tokens (a 32,768-token input plus 256 for the answer).
# Measured 2026-09-16/17 on the R310 image; every profile's outputs are identical to no-MTP decoding.
PROFILES = {
    'recommended': dict(depth=5, shortlist=True),   # MTP depth 5, draft-only INT4 shortlist head
    'depth-1': dict(depth=1, shortlist=False),      # the September 14 recipe (MTP depth 1, full-vocabulary draft head)
}
MAX_MODEL_LEN = 33024

# Qualified runtime environment (two cards, official FP8, deterministic W8A16/GDN paths); identical to the qualified
# R304 two-card container of 2026-09-15 apart from two decode-identical overlays: verifier rows, and the two-rank
# allreduce as one allgather plus a fixed-order add (comm-2 campaign, 2026-09-17: same outputs, +2.3%).
BASE_ENV = {
    'B70_ALLGATHER_ALLREDUCE': '1',
    'B70_FA_VERIFY_ROWS': '1',
    'CCL_ATL_TRANSPORT': 'ofi',
    'CCL_RECV': 'direct',
    'CCL_SEND': 'direct',
    'CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD': '4294967296',
    'CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD': '4294967296',
    'CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD': '4294967296',
    'CCL_TOPO_P2P_ACCESS': '1',
    'CCL_ZE_IPC_EXCHANGE': 'pidfd',
    'FI_PROVIDER': 'tcp',
    'FI_TCP_IFACE': 'lo',
    'ONEAPI_DEVICE_SELECTOR': 'level_zero:0,1',
    'PYTHONHASHSEED': '0',
    'PYTHONPATH': '/overlay',
    'PYTORCH_ALLOC_CONF': 'expandable_segments:True',
    'TORCHINDUCTOR_DETERMINISTIC': '1',
    'VLLM_BATCH_INVARIANT': '0',
    'VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING': '0',
    'VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE': '0',
    'VLLM_USE_BREAKABLE_CUDAGRAPH': '0',
    'VLLM_TARGET_DEVICE': 'xpu',
    'VLLM_USE_V2_MODEL_RUNNER': '0',
    'VLLM_WORKER_MULTIPROC_METHOD': 'spawn',
    'VLLM_XPU_ALLREDUCE_HOST_WAIT': '1',
    'VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP': '0',
    'VLLM_XPU_DECODER_BOUNDARY_TRACE_FILE': '',
    'VLLM_XPU_DRAFT_LM_HEAD_INT4': '1',
    'VLLM_XPU_DRAFT_LM_HEAD_INT4_APPLY_ROWS': '0',
    'VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS': '2048',
    'VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE': '128',
    'VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE': 'bf16',
    'VLLM_XPU_ENABLE_XPU_GRAPH': '0',
    'VLLM_XPU_FA_SERIAL_SPEC_DECODE': '0',
    'VLLM_XPU_FA_SERIAL_SPEC_NO_CAUSAL': '0',
    'VLLM_XPU_FP16_LINEAR_CLASSPAD': '0',
    'VLLM_XPU_FP16_LINEAR_CLASSPAD_MAXM': '512',
    'VLLM_XPU_FP16_LINEAR_ROWCHUNK': '32',
    'VLLM_XPU_FP8_BLOCK_W8A16': '1',
    'VLLM_XPU_FP8_PACKED_SERIAL_EXACT': '0',
    'VLLM_XPU_GDN_DETERMINISTIC_QKVZ_PREFILL': '0',
    'VLLM_XPU_GDN_ISOLATE_NORM_PREFILL_REQUESTS': '0',
    'VLLM_XPU_GDN_ISOLATE_OUTPUT_PREFILL_REQUESTS': '0',
    'VLLM_XPU_GDN_ISOLATE_PREFILL_REQUESTS': '0',
    'VLLM_XPU_GDN_ISOLATE_PROJECTION_PREFILL_REQUESTS': '0',
    'VLLM_XPU_GDN_ISOLATE_QKVZ_PREFILL_REQUESTS': '0',
    'VLLM_XPU_GDN_NATIVE_FALLBACK': '1',
    'VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT': '0',
    'VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT': '0',
    'VLLM_XPU_GDN_NATIVE_SPEC_EVOLVING_METADATA_TRACE': '0',
    'VLLM_XPU_GDN_NATIVE_SPEC_METADATA_TRACE': '0',
    'VLLM_XPU_GDN_NATIVE_SPEC_MULTI_REQUEST_SPLIT': '0',
    'VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT': '0',
    'VLLM_XPU_GDN_PREFILL_GROUP': '1',
    'VLLM_XPU_GDN_PREFILL_INPUT_TRACE_FILE': '',
    'VLLM_XPU_GDN_PREFILL_OUTPUT_TRACE_FILE': '',
    'VLLM_XPU_GDN_PROJECTION_TRACE_FILE': '',
    'VLLM_XPU_GDN_ROW_STABLE_RMSNORM': '0',
    'VLLM_XPU_GDN_SPEC_GROUP': '16',
    'VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH': '1',
    'VLLM_XPU_GDN_SPLIT_MIXED': '1',
    'VLLM_XPU_GDN_STATE_INPUT_TRACE_FILE': '',
    'VLLM_XPU_GEMMA_RMSNORM_TRITON': '0',
    'VLLM_XPU_ISOLATE_LAYER0_MLP_PREFILL_REQUESTS': '0',
    'VLLM_XPU_LM_HEAD_BATCH_INVARIANT': '0',
    'VLLM_XPU_LM_HEAD_BATCH_REPAIR_MARGIN': '0.25',
    'VLLM_XPU_LM_HEAD_BATCH_REPAIR_ROWS': '0',
    'VLLM_XPU_LM_HEAD_CHUNK_ROWS': '0',
    'VLLM_XPU_LM_HEAD_GLOBAL_BATCH_REPAIR_MARGIN': '0',
    'VLLM_XPU_MTP_DRAFT_EAGER': '0',
    'VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN': '0',
    'VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT': '0',
    'VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT': '1',
    'VLLM_XPU_RMSNORM_TRITON': '0',
    'VLLM_XPU_W4A16_DETERMINISM_PAD': '0',
    'VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH': '0',
    'VLLM_XPU_W8A16_DECODE_PAD_ROWS': '0',
    'VLLM_XPU_W8A16_PAD_N_SET': '',
    'ZE_AFFINITY_MASK': '0,1',
}
COMPILATION = ('{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,'
               '"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,'
               '"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}')
WARMUP_PROMPT = 'Warm-up request sent before readiness. List the numbers from one to twenty.'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def clean_env():
    env = {k: os.environ[k] for k in ('HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL') if k in os.environ}
    env.update(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
               DOCKER_HOST='unix:///var/run/docker.sock')
    return env


def run(args, check=True, timeout=30):
    return subprocess.run(args, env=clean_env(), text=True, capture_output=True, check=check, timeout=timeout)


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
    if (container['Id'] != record['container_id'] or container['Name'].lstrip('/') != record['container_name']
            or container['Image'] != record.get('local_image_id', IMAGE_ID)):
        raise RuntimeError('Container ownership or image does not match the saved receipt; refusing action.')


def local_image_id():
    """The pulled image's local ID. Docker's containerd store names it by the registry digest; the classic store names
    it by the config digest and lists the registry digest under RepoDigests. Both are the same pinned image."""
    result = run(['docker', 'image', 'inspect', IMAGE], check=False)
    if result.returncode:
        raise RuntimeError(f'Pull the pinned runtime first: docker pull {IMAGE}')
    image = json.loads(result.stdout)[0]
    if image['Id'] == IMAGE_ID or any(str(digest).endswith('@' + IMAGE_ID) for digest in image.get('RepoDigests') or []):
        return image['Id']
    raise RuntimeError(f'The local image is not the pinned runtime; pull it again: docker pull {IMAGE}')


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
    if record.get('schema') != 'neural.download.fp8-serving-state.v2' or record.get('image_id') != IMAGE_ID:
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


def docker_argv(profile, model, state, port, name):
    """The complete `docker run` command. Nothing from the caller's environment reaches it."""
    settings = PROFILES[profile]
    env = dict(BASE_ENV)
    if settings['shortlist']:
        env['VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST'] = SHORTLIST
    # `--memory-swap` equals `--memory`, which in Docker means the container gets NO swap at all
    # (`--memory-swap` is memory PLUS swap; equal values put cgroup v2 `memory.swap.max` at 0). It
    # was '16g' -- a 4 GiB allowance -- until 2026-09-19. Why it changed: the 29 GB of safetensors
    # stream through this container's own page cache, so the cgroup runs flat against `memory.max`
    # and reclaims 2,000-16,000 times per start. With a swap allowance it spends that allowance to
    # the byte, pushing 3.94 GiB of its own *anonymous* pages out during the weight load -- and
    # those include the host staging buffers the card's copy engine reads through userptr mappings,
    # which is the leading explanation for the `bcs` copy-engine faults that strike at weight load.
    # With no allowance the same reclaim has only one option left: drop clean file pages, which are
    # the weight file's cache and are re-readable from NVMe. Validated over three service starts
    # (container `pswpout` 0, `oom_kill` 0, 12/12 exact, no fault lines, weight load no slower):
    # experiments/qwen38-27b-b70/notes/2026-09-19-container-memory-cap-swap.md
    argv = ['docker', 'run', '--name', name, '--restart', 'no', '--network', 'bridge', '--device', '/dev/dri',
            '--group-add', 'render', '--ipc', 'host', '--cap-add', 'SYS_PTRACE', '--shm-size', '8g',
            '--memory', '12g', '--memory-swap', '12g', '--ulimit', 'core=0', '--security-opt', 'label=disable',
            '-p', f'127.0.0.1:{port}:8000', '--workdir', '/',
            '--mount', f'type=bind,source={model},target=/model,readonly',
            '--mount', f'type=bind,source={state / "cache"},target=/root/.cache/vllm',
            '--mount', f'type=bind,source={state / "overlay"},target=/overlay,readonly']
    for key, value in sorted(env.items()):
        argv += ['--env', f'{key}={value}']
    argv += [IMAGE, '--model', '/model', '--served-model-name', MODEL, '--host', '0.0.0.0', '--port', '8000',
             '--tensor-parallel-size', '2', '--dtype', 'float16', '--quantization', 'fp8', '--kv-cache-dtype', 'auto',
             '--gpu-memory-utilization', '0.95', '--max-model-len', str(MAX_MODEL_LEN),
             '--block-size', '64', '--max-num-seqs', '1', '--max-num-batched-tokens', '4096',
             '--no-enable-prefix-caching', '--enable-prompt-tokens-details', '--language-model-only',
             '--speculative-config', json.dumps({'method': 'qwen3_next_mtp', 'num_speculative_tokens': settings['depth']}),
             '--compilation-config', COMPILATION]
    return argv


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


def warm_up(port):
    """One untimed greedy completion before readiness; compiles the MTP draft kernels outside real requests."""
    body = json.dumps({'model': MODEL, 'prompt': WARMUP_PROMPT, 'max_tokens': 64, 'temperature': 0}).encode()
    request = urllib.request.Request(f'http://127.0.0.1:{port}/v1/completions', data=body,
                                     headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=300) as response:
        usage = json.loads(response.read()).get('usage', {})
    if not usage.get('completion_tokens'):
        raise RuntimeError('Warm-up request returned no tokens; see server.log. No restart attempted.')
    return {'completion_tokens': usage['completion_tokens'], 'seconds': round(time.monotonic() - started, 3)}


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
    return {'status': record['status'], 'profile': record.get('profile'), 'container_present': container is not None,
            'container_running': running, 'api_healthy': healthy(record['port']) if running else False,
            'endpoint': f'http://127.0.0.1:{record["port"]}/v1', 'model': MODEL, 'max_model_len': MAX_MODEL_LEN,
            'error': record.get('error'), 'state_dir': str(state)}


def start(args):
    model, state = args.model_dir.resolve(), args.state_dir.resolve()
    profile = getattr(args, 'profile', 'recommended')
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
        image_id = local_image_id()
        state.mkdir(parents=True, exist_ok=False)
        (state / 'cache').mkdir()
        shutil.copytree(PACKAGE / 'overlays', state / 'overlay', ignore=shutil.ignore_patterns('__pycache__'))
        with (state / 'owner.lock').open('x') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record = {'schema': 'neural.download.fp8-serving-state.v2', 'started_at': since, 'owner_pid': os.getpid(),
                      'container_name': name, 'container_id': None, 'image_id': IMAGE_ID, 'local_image_id': image_id,
                      'model': MODEL, 'profile': profile, 'model_dir': str(model), 'state_dir': str(state),
                      'port': args.port, 'status': 'starting'}
            write_json(state / 'state.json', record)
            argv = docker_argv(profile, model, state, args.port, name)
            write_json(state / 'launch.json', {'argv': argv})
            shutdown = []
            previous = {s: signal.signal(s, lambda signum, frame: shutdown.append(signum)) for s in (signal.SIGINT, signal.SIGTERM)}
            child, failed = None, None
            print(f'Starting one server ({profile}, {MAX_MODEL_LEN} tokens). Logs: {state / "server.log"}', flush=True)
            try:
                with (state / 'server.log').open('x') as log:
                    child = subprocess.Popen(argv, env=clean_env(), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
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
                                raise RuntimeError(f'Server exited ({child.returncode}); see server.log. No restart attempted.')
                            break
                        if record['status'] == 'starting':
                            if record['container_id'] and healthy(args.port):
                                record.update(status='ready', warmup=warm_up(args.port), ready_at=now())
                                write_json(state / 'state.json', record)
                                print(f'Ready: http://127.0.0.1:{args.port}/v1\nModel: {MODEL}\n'
                                      'Leave this terminal open. Ctrl+C stops this owned server.', flush=True)
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
                            os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=45)
                        except subprocess.TimeoutExpired:
                            failed = failed or 'Server process did not exit after graceful stop; no kill or retry attempted.'
                        if record['container_id']:
                            final = inspect_container(record['container_id'])
                            if final is not None:
                                write_json(state / 'container-final.json', final)
                                if not final['State']['Running']:
                                    run(['docker', 'rm', record['container_id']], check=False)
                except Exception as exc:
                    failed = failed or str(exc)
                record.update(status='failed' if failed else 'stopped', finished_at=now(), error=failed)
                write_json(state / 'state.json', record)
                for s, handler in previous.items():
                    signal.signal(s, handler)
    if failed:
        raise RuntimeError(failed)
    print(f'Stopped. Logs and receipts preserved in {state}', flush=True)


def render(args):
    """Write the exact `docker run` argv (NUL-separated) for a profile, for compose generation. Starts nothing."""
    argv = docker_argv(args.profile, Path('/path/model'), Path('/path/state'), 18124, 'render')
    args.out.write_bytes(b''.join(a.encode() + b'\0' for a in argv))
    print(f'wrote {args.out} ({len(argv)} arguments)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('start', 'status', 'stop', 'render'):
        item = sub.add_parser(command)
        if command == 'render':
            item.add_argument('--profile', choices=sorted(PROFILES), default='recommended')
            item.add_argument('--out', type=Path, required=True)
            continue
        item.add_argument('--state-dir', type=Path, required=True)
        if command == 'start':
            item.add_argument('--model-dir', type=Path, required=True)
            item.add_argument('--profile', choices=sorted(PROFILES), default='recommended')
            item.add_argument('--port', type=int, default=18124)
            item.add_argument('--startup-timeout', type=int, default=1800)
    args = parser.parse_args()
    try:
        if args.command == 'render':
            render(args)
        elif args.command == 'start':
            if not 1024 <= args.port <= 65535 or args.startup_timeout < 1:
                raise RuntimeError('Use a port from 1024-65535 and a positive timeout.')
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
