#!/usr/bin/env python3
"""One persistent, pinned one-card FP8 server (Qwen3.8 27B, one Intel Arc Pro B70). No restart or recovery policy."""
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
IMAGE = os.environ.get('B70_FP8_TP1_IMAGE', 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@' + IMAGE_ID)
MODEL = 'qwen38-27b-fp8'
SHORTLIST = '/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)

# Profiles measured on 2026-09-15: every profile's outputs are identical to no-MTP decoding.
PROFILES = {
    'recommended': dict(max_model_len=16384, memory=0.975, draft='int4-shortlist'),
    'no-quantization': dict(max_model_len=12544, memory=0.975, draft='fp16-shortlist'),
}

# Qualified runtime environment (one card, official FP8, deterministic W8A16/GDN paths).
BASE_ENV = {
    'B70_CPU_EMBED': '1',
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
    'ONEAPI_DEVICE_SELECTOR': 'level_zero:0',
    'PYTHONHASHSEED': '0',
    'PYTHONPATH': '/overlay',
    'PYTORCH_ALLOC_CONF': 'expandable_segments:True',
    'TORCHINDUCTOR_DETERMINISTIC': '1',
    'VLLM_BATCH_INVARIANT': '0',
    'VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING': '0',
    'VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE': '0',
    'VLLM_USE_BREAKABLE_CUDAGRAPH': '0',
    'VLLM_USE_V2_MODEL_RUNNER': '0',
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
    if (container['Id'] != record['container_id'] or container['Name'].lstrip('/') != record['container_name']
            or container['Image'] != IMAGE_ID):
        raise RuntimeError('Container ownership or image does not match the saved receipt; refusing action.')


def read_record(state):
    record = json.loads((state / 'state.json').read_text())
    if record.get('schema') != 'neural.download.fp8-tp1-serving-state.v1' or record.get('image_id') != IMAGE_ID:
        raise RuntimeError('Unrecognized state receipt.')
    return record


def stop_owned(state, record):
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


def docker_argv(profile, model, state, port, name, gpu):
    settings = PROFILES[profile]
    env = dict(BASE_ENV, ZE_AFFINITY_MASK=str(gpu))
    if settings['draft'] == 'int4-shortlist':
        env['VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST'] = SHORTLIST
    else:
        # The draft-copy hook runs when VLLM_XPU_DRAFT_LM_HEAD_INT4=1; the overlay builds an FP16 copy, no INT4.
        env['B70_DRAFT_FP16_SHORTLIST'] = SHORTLIST
    argv = ['docker', 'run', '--name', name, '--restart', 'no', '--device', '/dev/dri', '--group-add', 'render', '--ipc', 'host',
            '--shm-size', '8g', '--memory', '12g', '--memory-swap', '16g', '--ulimit', 'core=0',
            '--security-opt', 'label=disable', '-p', f'127.0.0.1:{port}:8000', '--workdir', '/',
            '--mount', f'type=bind,source={model},target=/model,readonly',
            '--mount', f'type=bind,source={state / "cache"},target=/root/.cache/vllm',
            '--mount', f'type=bind,source={state / "overlay"},target=/overlay,readonly']
    for key, value in sorted(env.items()):
        argv += ['--env', f'{key}={value}']
    argv += [IMAGE, '--model', '/model', '--served-model-name', MODEL, '--host', '0.0.0.0', '--port', '8000',
             '--tensor-parallel-size', '1', '--dtype', 'float16', '--quantization', 'fp8', '--kv-cache-dtype', 'auto',
             '--gpu-memory-utilization', str(settings['memory']), '--max-model-len', str(settings['max_model_len']),
             '--block-size', '64', '--max-num-seqs', '1', '--max-num-batched-tokens', '4096',
             '--no-enable-prefix-caching', '--enable-prompt-tokens-details', '--language-model-only',
             '--speculative-config', json.dumps({'method': 'qwen3_next_mtp', 'num_speculative_tokens': 5}),
             '--compilation-config', COMPILATION]
    return argv


def check_available(port, name, gpu):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))
    if inspect_container(name) is not None:
        raise RuntimeError('Selected container name already exists.')
    nodes = sorted(Path('/dev/dri').glob('renderD*'))
    if gpu >= len(nodes):
        raise RuntimeError(f'GPU index {gpu} is not available ({len(nodes)} render devices found).')
    result = run(['fuser', str(nodes[gpu])], check=False)
    if result.returncode != 1 or result.stdout.strip():
        raise RuntimeError('The selected GPU is in use or ownership could not be checked; stop the other GPU work first.')


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
    with urllib.request.urlopen(request, timeout=300) as response:
        usage = json.loads(response.read()).get('usage', {})
    if not usage.get('completion_tokens'):
        raise RuntimeError('Warm-up request returned no tokens; see server.log. No restart attempted.')


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
    return {'status': record['status'], 'profile': record['profile'], 'container_running': running,
            'api_healthy': healthy(record['port']) if running else False,
            'endpoint': f'http://127.0.0.1:{record["port"]}/v1', 'model': MODEL,
            'max_model_len': PROFILES[record['profile']]['max_model_len'], 'error': record.get('error')}


def start(args):
    model, state = args.model_dir.resolve(), args.state_dir.resolve()
    if not model.is_dir():
        raise RuntimeError('Model directory does not exist.')
    if model == state or model in state.parents or state in model.parents:
        raise RuntimeError('Model and serving state must be separate directories.')
    name = 'neural-fp8-tp1-' + uuid.uuid4().hex[:16]
    check_available(args.port, name, args.gpu)
    since = now()
    journal(since)
    image = run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], check=False)
    if image.returncode or image.stdout.strip() != IMAGE_ID:
        raise RuntimeError(f'Pull the pinned runtime first: docker pull {IMAGE}')
    state.mkdir(parents=True, exist_ok=False)
    (state / 'cache').mkdir()
    shutil.copytree(PACKAGE / 'overlays', state / 'overlay', ignore=shutil.ignore_patterns('__pycache__'))
    record = {'schema': 'neural.download.fp8-tp1-serving-state.v1', 'started_at': since, 'owner_pid': os.getpid(),
              'container_name': name, 'container_id': None, 'image_id': IMAGE_ID, 'model': MODEL,
              'profile': args.profile, 'model_dir': str(model), 'state_dir': str(state), 'port': args.port,
              'status': 'starting'}
    write_json(state / 'state.json', record)
    argv = docker_argv(args.profile, model, state, args.port, name, args.gpu)
    write_json(state / 'launch.json', {'argv': argv})
    shutdown = []
    previous = {s: signal.signal(s, lambda signum, frame: shutdown.append(signum)) for s in (signal.SIGINT, signal.SIGTERM)}
    child, failed = None, None
    print(f'Starting ({args.profile}, {PROFILES[args.profile]["max_model_len"]} tokens). Logs: {state / "server.log"}',
          flush=True)
    try:
        with (state / 'server.log').open('x') as log:
            child = subprocess.Popen(argv, env=clean_env(), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + args.startup_timeout
            while not shutdown:
                if not record['container_id']:
                    container = inspect_container(name)
                    if container is not None:
                        record['container_id'] = container['Id']
                        owned(record, container)
                        write_json(state / 'state.json', record)
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
                        warm_up(args.port)
                        record.update(status='ready', ready_at=now())
                        write_json(state / 'state.json', record)
                        print(f'Ready: http://127.0.0.1:{args.port}/v1\nModel: {MODEL}\n'
                              'Leave this terminal open. Ctrl+C stops this server.', flush=True)
                    elif time.monotonic() > deadline:
                        raise RuntimeError('Startup deadline reached; see server.log. No restart attempted.')
                time.sleep(2)
    except Exception as exc:
        failed = str(exc)
    finally:
        try:
            if child is not None:
                if not record['container_id']:
                    container = inspect_container(name)
                    if container is not None:
                        record['container_id'] = container['Id']
                if record['container_id']:
                    stop_owned(state, record)
                elif child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    failed = failed or 'Server process did not exit after graceful stop; no kill or retry attempted.'
                if record['container_id'] and inspect_container(record['container_id']) is not None:
                    run(['docker', 'rm', record['container_id']], check=False)
        except Exception as exc:
            failed = failed or str(exc)
        record.update(status='failed' if failed else 'stopped', finished_at=now(), error=failed)
        write_json(state / 'state.json', record)
        for s, handler in previous.items():
            signal.signal(s, handler)
    if failed:
        raise RuntimeError(failed)
    print(f'Stopped. Logs preserved in {state}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('start', 'status', 'stop'):
        item = sub.add_parser(command)
        item.add_argument('--state-dir', type=Path, required=True)
        if command == 'start':
            item.add_argument('--model-dir', type=Path, required=True)
            item.add_argument('--profile', choices=sorted(PROFILES), default='recommended')
            item.add_argument('--port', type=int, default=18130)
            item.add_argument('--gpu', type=int, default=0, help='Level Zero index of the B70 to use (default 0)')
            item.add_argument('--startup-timeout', type=int, default=1800)
    args = parser.parse_args()
    try:
        if args.command == 'start':
            if not 1024 <= args.port <= 65535 or args.startup_timeout < 1 or args.gpu < 0:
                raise RuntimeError('Use a port from 1024-65535, a positive timeout and a GPU index >= 0.')
            start(args)
        else:
            state = args.state_dir.resolve()
            record = read_record(state)
            if args.command == 'stop':
                stop_owned(state, record)
                print('Graceful stop requested. No restart is scheduled.')
            else:
                print(json.dumps(status(state, record), indent=2))
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
