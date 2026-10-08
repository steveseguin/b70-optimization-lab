#!/usr/bin/env python3
"""Bounded Screen 1 controller. Default is a no-network, no-GPU dry run.

prepare --execute pulls only after admission; run --execute starts one server.
No automatic retry, restart, hard kill, settings changes, or installations.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PLAN = json.loads((HERE / 'image-plan.json').read_text())
OVERLAY = json.loads((HERE / 'overlay-manifest.json').read_text())
MODEL = Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|devcoredump|device coredump|timed.?out job|job[^\n]*timed\s*out|GPU HANG', re.I)
GIB = 2**30


def call(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, text=True, **kwargs)


def show(args):
    print(shlex.join([str(x) for x in args]), flush=True)


def journal(since=None):
    args = ['journalctl', '-k', '-b', '--no-pager', '-o', 'short-iso']
    if since:
        args += ['--since', since]
    p = call(args, capture_output=True)
    if 'permission' in p.stderr.lower() or 'not seeing messages' in p.stderr.lower():
        raise RuntimeError('Cannot verify the complete kernel journal without existing read access')
    if not p.stdout.strip():
        raise RuntimeError('Kernel journal unavailable/empty; no clean-log inference')
    return p.stdout


def overlay_check():
    root = Path(OVERLAY['source'])
    for rel, digest in OVERLAY['files'].items():
        path = root / rel
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Overlay drift: {path}')


SCAN_SNIPPET = r'''
import json, os, sys
from pathlib import Path
targets = set(sys.argv[1:])
held, unreadable = [], []
for proc in Path('/proc').glob('[0-9]*'):
    try:
        fds = list((proc / 'fd').iterdir())
    except FileNotFoundError:
        continue
    except PermissionError:
        unreadable.append(proc.name)
        continue
    for fd in fds:
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        except PermissionError:
            unreadable.append(proc.name)
            break
        if target in targets:
            held.append({'pid': proc.name, 'node': target})
print(json.dumps({'held': held, 'unreadable': sorted(set(unreadable))}))
'''


def privileged_scan(targets):
    """Run the same fd scan as root so every PID is visible. The sudo password is read from the
    owner's local file (outside Git) and passed on stdin only; it is never logged or echoed."""
    pw_file = os.environ.get('SCREEN_SUDO_PASSWORD_FILE', '/home/steve/SUDOPASSWORD.txt')
    with open(pw_file, 'rb') as fh:
        pw = fh.read()
    p = subprocess.run(['sudo', '-S', '-p', '', '/usr/bin/python3', '-c', SCAN_SNIPPET, *sorted(targets)],
                       input=pw, capture_output=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError('privileged render-node scan failed (rc=%d)' % p.returncode)
    out = json.loads(p.stdout.decode().strip().splitlines()[-1])
    return out['held'], out['unreadable']


def idle():
    nodes = sorted(Path('/dev/dri').glob('renderD*'))
    if len(nodes) != 4:
        raise RuntimeError(f'Expected four render nodes, found {len(nodes)}')
    targets = {str(n) for n in nodes}
    if os.environ.get('SCREEN_PRIVILEGED_FD_SCAN') == '1':
        held, unreadable = privileged_scan(targets)
        if held or unreadable:
            raise RuntimeError(f'Render-node idle check failed (privileged scan): holders={held}, inaccessible PIDs={unreadable}.')
        return
    # fuser may silently miss inaccessible PIDs. Refuse incomplete /proc visibility.
    held, unreadable = [], []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            fds = list((proc / 'fd').iterdir())
        except FileNotFoundError:
            continue
        except PermissionError:
            unreadable.append(proc.name)
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except FileNotFoundError:
                continue
            except PermissionError:
                unreadable.append(proc.name)
                break
            if target in targets:
                held.append({'pid': proc.name, 'node': target})
    if held or unreadable:
        raise RuntimeError(f'Render-node idle check failed: holders={held}, inaccessible PIDs={sorted(set(unreadable))}. No sudo fallback.')


def storage(required):
    # Both destinations must pass, even if Docker is later moved to another disk.
    for path in (Path('/var/lib/docker'), HERE):
        free = shutil.disk_usage(path).free / GIB
        print(f'{path}: {free:.2f} GiB free; require {required} GiB', flush=True)
        if free < required:
            raise RuntimeError('Disk admission refused; no files are deleted automatically')


def preflight(args, image_present=False):
    if socket.gethostname() != 'steve-b70s':
        raise RuntimeError('Wrong host')
    if call(['git', '-C', REPO, 'branch', '--show-current'], capture_output=True).stdout.strip() != 'main':
        raise RuntimeError('Must remain on main')
    storage(PLAN['required_when_present_gib'] if image_present else PLAN['required_before_pull_gib'])
    overlay_check()
    idle()
    with socket.socket() as s:
        s.bind(('127.0.0.1', args.port))
    text = journal()
    if FAULT.search(text):
        raise RuntimeError('Fault signature in this boot; evidence/recovery review required, no launch')
    mem = dict(re.findall(r'^(\w+):\s+(\d+) kB', Path('/proc/meminfo').read_text(), re.M))
    if int(mem['MemAvailable']) * 1024 < 100 * GIB:
        raise RuntimeError('Require 100 GiB available RAM for 65+ GiB offload, runtime and loading headroom')
    print('Passive admission passed. Full 185.6 GB model hashing remains required before launch.')


def launch(args, run):
    cmd = ['docker', 'run', '--name', 'flashnext-screen1-' + run.name,
           '--pull=never', '--restart=no', '--network=host', '--device=/dev/dri',
           '--ipc=host', '--security-opt=seccomp=unconfined', '--stop-signal=SIGINT',
           '--entrypoint=/bin/bash', '-w', '/opt/venv']
    env = {
        'ZE_AFFINITY_MASK': '0,1,2,3', 'ZE_FLAT_DEVICE_HIERARCHY': 'FLAT',
        'CCL_ZE_IPC_EXCHANGE': 'sockets', 'CCL_SYCL_ALLGATHERV_TMP_BUF': '1',
        'CCL_SYCL_ALLREDUCE_TMP_BUF': '1', 'VLLM_TARGET_DEVICE': 'xpu',
        'VLLM_WORKER_MULTIPROC_METHOD': 'spawn', 'VLLM_USE_V2_MODEL_RUNNER': '1',
        'VLLM_XPU_ENABLE_XPU_GRAPH': '1', 'B70_GDN_MODE': 'official',
        'B70_PLE_FP8': '0', 'B70_PLE_INT8': '0', 'B70_PLE_DIRECT_PINNED': '0',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'HF_DATASETS_OFFLINE': '1', 'HF_HOME': '/screen/cache/hf',
        'TRITON_CACHE_DIR': '/screen/cache/triton', 'VLLM_CACHE_ROOT': '/screen/cache/vllm',
        'XDG_CACHE_HOME': '/screen/cache/xdg', 'TMPDIR': '/screen/cache/tmp',
        'PYTHONDONTWRITEBYTECODE': '1',
    }
    for key, value in env.items():
        cmd += ['-e', f'{key}={value}']
    cmd += ['-v', f'{MODEL}:/model:ro', '-v', f'{run}:/screen',
            '-v', f'{HERE / "container-entrypoint.sh"}:/screen-entrypoint.sh:ro']
    # File mounts retain the image's installed native/Rust artifacts and metadata.
    for rel in OVERLAY['files']:
        cmd += ['-v', f'{OVERLAY["source"]}/{rel}:/opt/venv/lib/python3.12/site-packages/{rel}:ro']
    cmd += [PLAN['image'], '/screen-entrypoint.sh', '--execute', 'serve', '/model',
            '--host', '127.0.0.1', '--port', str(args.port),
            '--served-model-name', 'qwen38-flash-next-fp8-tp4',
            '--tensor-parallel-size', '4', '--enable-expert-parallel',
            '--all2all-backend', 'allgather_reducescatter',
            '--dtype', 'bfloat16', '--quantization', 'fp8',
            '--kv-cache-dtype', 'auto', '--max-model-len', '4352',
            '--max-num-seqs', '1', '--max-num-batched-tokens', '64',
            '--enable-chunked-prefill', '--no-enable-prefix-caching',
            '--no-async-scheduling', '--generation-config', 'vllm',
            '--gpu-memory-utilization', '0.95', '--kv-cache-memory-bytes', '376569856',
            '--offload-backend', 'uva', '--cpu-offload-gb', '16.25',
            '--cpu-offload-params', 'ple_embedding.ngram_embedding.weight',
            'mlp.experts.w13_weight', 'mlp.experts.w2_weight',
            '--moe-backend', 'triton', '--enable-prompt-tokens-details',
            '--limit-mm-per-prompt', '{"image":0,"video":0}',
            '--compilation-config', json.dumps({'cudagraph_mode': 'FULL_DECODE_ONLY', 'cudagraph_capture_sizes': {'mtp0': [1], 'mtp1': [1, 2], 'mtp3': [1, 4]}[args.mode]}),
            '--cudagraph-metrics']
    if args.mode != 'mtp0':
        cmd += ['--speculative-config', json.dumps({'method': 'mtp', 'num_speculative_tokens': int(args.mode[-1]), 'rejection_sample_method': 'standard'})]
    return cmd


def supervise(args, run):
    # A systemd unit owns this controller and its attached docker client.
    # kill-mode=process + SendSIGKILL=no prevents cgroup hard kills on busy GPUs.
    with open('/tmp/flashnext-screen1.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return supervise_locked(args, run)


def supervise_locked(args, run):
    preflight(args, image_present=True)
    with open(run / 'image-inspect.json', 'w') as receipt:
        call(['docker', 'image', 'inspect', PLAN['image']], stdout=receipt)
    call([sys.executable, REPO / 'scripts/verify-qwen38-flash-next-fp8-tree.py',
          '--model-root', MODEL, '--receipt', run / 'model-verification.json'])
    # Model hashing takes time. Recheck ground truth immediately before launch.
    preflight(args, image_present=True)
    cmd = launch(args, run)
    (run / 'launch.json').write_text(json.dumps(cmd, indent=2) + '\n')
    since = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    (run / 'started-utc.txt').write_text(since + '\n')
    stopping = False
    def stop_signal(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)
    server = None
    client = None
    name = 'flashnext-screen1-' + run.name
    base = f'http://127.0.0.1:{args.port}'
    start = time.monotonic()
    try:
        with open(run / 'server.log', 'w') as log, open(run / 'client.log', 'w') as client_log:
            server = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            ready = False
            while time.monotonic() - start < 1800:
                if stopping or server.poll() is not None:
                    raise RuntimeError('Startup stopped/exited; no retry')
                check_live(run, since)
                try:
                    with urllib.request.urlopen(base + '/health', timeout=2) as res:
                        ready = res.status == 200
                except OSError:
                    pass
                if ready:
                    with urllib.request.urlopen(base + '/v1/models', timeout=5) as res:
                        models = json.load(res)
                    (run / 'models.json').write_text(json.dumps(models, indent=2))
                    if not any(m['id'] == 'qwen38-flash-next-fp8-tp4' for m in models['data']):
                        raise RuntimeError('Wrong served model')
                    with urllib.request.urlopen(base + '/metrics', timeout=5) as res:
                        (run / 'metrics-before.txt').write_bytes(res.read())
                    break
                time.sleep(2)
            if not ready:
                raise RuntimeError('30 minute readiness bound exceeded')
            client_cmd = [sys.executable, str(HERE / 'protocol.py'), '--mode', args.mode,
                          '--base-url', base, '--output-dir', str(run / 'client'), '--execute']
            client = subprocess.Popen(client_cmd, stdout=client_log, stderr=subprocess.STDOUT)
            while client.poll() is None:
                if stopping or server.poll() is not None or time.monotonic() - start > 5400:
                    raise RuntimeError('Stop/server exit/90 minute experiment bound; no retry')
                check_live(run, since)
                time.sleep(2)
            if client.returncode:
                raise RuntimeError(f'Client failed: {client.returncode}')
            with urllib.request.urlopen(base + '/metrics', timeout=5) as res:
                (run / 'metrics-after.txt').write_bytes(res.read())
    finally:
        if client and client.poll() is None:
            try:
                client.terminate()  # client owns no GPU; never kill server by pattern
                client.wait(timeout=30)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                (run / 'client-stop-timeout.txt').write_text('Client did not drain in 30s; continue mandatory GPU shutdown.\n')
        if server:
            # docker stop with a timeout escalates to SIGKILL: deliberately avoid it.
            p = subprocess.run(['docker', 'kill', '--signal=SIGINT', name], capture_output=True, text=True)
            (run / 'graceful-stop.json').write_text(json.dumps({'signal': 'SIGINT', 'rc': p.returncode, 'stderr': p.stderr}))
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                state = subprocess.run(['docker', 'inspect', '--format', '{{.State.Running}}', name], capture_output=True, text=True)
                if state.returncode == 0 and state.stdout.strip() == 'false':
                    break
                time.sleep(2)
            else:
                raise RuntimeError('Graceful shutdown did not finish within 300s. Preserve container, do not relaunch; owner must review.')
            if server.poll() is None:
                server.wait(timeout=15)
        end = journal()
        (run / 'kernel-postflight.log').write_text(end)
        idle()
        if FAULT.search(end):
            raise RuntimeError('Fault recorded; no recovery or second launch is automated')


def check_live(run, since):
    text = journal()  # whole current boot avoids empty --since false negatives
    (run / 'kernel-latest.log').write_text(text)
    if FAULT.search(text):
        raise RuntimeError('GPU fault: stop new requests and preserve evidence')
    if shutil.disk_usage(run).free < 50 * GIB:
        raise RuntimeError('50 GiB reserve breached; gracefully stop')
    mem = re.search(r'^MemAvailable:\s+(\d+) kB', Path('/proc/meminfo').read_text(), re.M)
    if int(mem[1]) * 1024 < 8 * GIB:
        raise RuntimeError('Available RAM below 8 GiB; gracefully stop')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['preflight', 'prepare', 'run', '_worker'])
    p.add_argument('--mode', choices=['mtp0', 'mtp1', 'mtp3'], default='mtp1')
    p.add_argument('--port', type=int, default=19988)
    p.add_argument('--run-dir', type=Path, default=HERE / 'runs' / 'screen1-mtp1')
    x = p.add_mutually_exclusive_group()
    x.add_argument('--execute', action='store_true')
    x.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    run = args.run_dir.resolve()
    if args.port == 8188 or not 1024 <= args.port <= 65535:
        p.error('Choose an unused non-LTX unprivileged port')
    overlay_check()
    print(json.dumps({'mode': args.mode, 'image': PLAN['image'], 'disk_before_pull_gib': 89,
                      'requests': 16, 'launches': 1, 'promotion_eligible': False}, indent=2))
    if not args.execute:
        print('DRY RUN: no GPU, network, process inspection, pull, model hashing or writes.')
        show(['docker', 'pull', PLAN['image']])
        show([sys.executable, REPO / 'scripts/verify-qwen38-flash-next-fp8-tree.py', '--model-root', MODEL, '--receipt', run / 'model-verification.json'])
        show(launch(args, run))
        show([sys.executable, HERE / 'protocol.py', '--mode', args.mode, '--base-url', f'http://127.0.0.1:{args.port}', '--output-dir', run / 'client', '--execute'])
        return
    if args.action == 'preflight':
        preflight(args)
        run.mkdir(parents=True, exist_ok=False)
        call([sys.executable, REPO / 'scripts/verify-qwen38-flash-next-fp8-tree.py',
              '--model-root', MODEL, '--receipt', run / 'model-verification.json'])
    elif args.action == 'prepare':
        preflight(args)
        call(['docker', 'pull', PLAN['image']])
        storage(60)
    elif args.action == 'run':
        preflight(args, image_present=True)
        call(['docker', 'image', 'inspect', PLAN['image']], stdout=subprocess.DEVNULL)
        run.mkdir(parents=True, exist_ok=False)
        for d in ['tmp', 'hf', 'triton', 'vllm', 'xdg']:
            (run / 'cache' / d).mkdir(parents=True)
        unit = 'flashnext-screen1-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        command = ['systemd-run', '--user', '--unit', unit, '--collect',
                   '--property=Restart=no', '--property=KillMode=process', '--property=SendSIGKILL=no',
                   '--property=TimeoutStopSec=360', sys.executable, str(HERE / 'screen.py'), '_worker',
                   '--mode', args.mode, '--port', str(args.port), '--run-dir', str(run), '--execute']
        (run / 'unit.txt').write_text(unit + '\n')
        call(command)
        print(f'Follow: journalctl --user -fu {unit}; stop gracefully: systemctl --user stop {unit}')
    else:
        supervise(args, run)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f'REFUSED/STOPPED: {exc}', file=sys.stderr)
        sys.exit(2)
