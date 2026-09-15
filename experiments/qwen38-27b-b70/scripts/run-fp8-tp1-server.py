#!/usr/bin/env python3
"""Own one single-B70 official-FP8 research server; fault and host-memory monitored; no retries.

Environment and command come from the qualified R304 TP2 container recorded on
2026-09-15 (restored-service/container-inspect.json). Only these change: one
GPU, memory/context/batch limits, MTP depth, eager mode, the draft-only INT4
head, and the optional lossless CPU-embedding overlay (frozen into the run).
"""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
IMAGE = 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2'
REFERENCE = Path('/mnt/fast-ai/bench-results/optimization-validation-20260915/restored-service/container-inspect.json')
MODEL_DIR = Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
OVERLAY = ROOT / 'experiments/qwen38-27b-b70/overlays/b70-cpu-embed'
HELPER = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
GUARD = ROOT / 'experiments/qwen38-27b-b70/scripts/host_memory_guard.py'
PASSWORD_FILE = Path('/home/steve/SUDO_PASSWORD.txt')
MEMORY_LINES = re.compile(r'Model loading took|Loading weights took|torch\.compile took|Available KV cache memory|'
                          r'GPU KV cache size|Maximum concurrency|CUDA graph|init engine|Free memory|requested|'
                          r'b70_cpu_embed|Actual usage|OutOfMemory|out of memory|Error|ValueError', re.I)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def set_flag(cmd, flag, value):
    index = cmd.index(flag)
    cmd[index + 1] = value


def reference(image_env):
    record = json.loads(REFERENCE.read_text())
    record = record[0] if isinstance(record, list) else record
    if record['Image'] != IMAGE:
        raise RuntimeError('Reference container is not the qualified image')
    env = dict(e.split('=', 1) for e in record['Config']['Env'] if e not in image_env)
    return env, list(record['Config']['Cmd'])


def build(args, name, out, image_env):
    env, cmd = reference(image_env)
    env.update(ZE_AFFINITY_MASK=str(args.gpu), ONEAPI_DEVICE_SELECTOR='level_zero:0',
               VLLM_XPU_DRAFT_LM_HEAD_INT4='1' if args.draft_int4 else '0')
    set_flag(cmd, '--tensor-parallel-size', '1')
    set_flag(cmd, '--gpu-memory-utilization', str(args.mem))
    set_flag(cmd, '--max-model-len', str(args.max_model_len))
    set_flag(cmd, '--max-num-batched-tokens', str(args.batched))
    index = cmd.index('--speculative-config')
    if args.mtp == 0:
        del cmd[index:index + 2]
    else:
        cmd[index + 1] = json.dumps({'method': 'qwen3_next_mtp', 'num_speculative_tokens': args.mtp})
    if args.eager:
        cmd.append('--enforce-eager')
    mounts = ['--mount', f'type=bind,source={MODEL_DIR},target=/model,readonly',
              '--mount', f'type=bind,source={out}/cache,target=/root/.cache/vllm']
    if args.cpu_embed:
        mounts += ['--mount', f'type=bind,source={out}/overlay,target=/overlay,readonly']
        env.update(PYTHONPATH='/overlay', B70_CPU_EMBED='1')
    argv = ['docker', 'run', '--name', name, '--restart', 'no', '--network', 'bridge',
            '--device', '/dev/dri', '--group-add', 'render', '--ipc', 'host', '--cap-add', 'SYS_PTRACE',
            '--shm-size', '8g', '--memory', '12g', '--memory-swap', '16g', '--ulimit', 'core=0',
            '--security-opt', 'label=disable', '-p', f'127.0.0.1:{args.port}:8000', '--workdir', '/'] + mounts
    for key, value in sorted(env.items()):
        argv += ['--env', f'{key}={value}']
    return argv + [IMAGE] + cmd


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=18132)
    ap.add_argument('--gpu', type=int, default=0, choices=(0, 1))
    ap.add_argument('--mem', type=float, default=0.95)
    ap.add_argument('--max-model-len', type=int, default=8448)
    ap.add_argument('--batched', type=int, default=2048)
    ap.add_argument('--mtp', type=int, default=0, choices=range(0, 6))
    ap.add_argument('--eager', action='store_true')
    ap.add_argument('--draft-int4', action='store_true')
    ap.add_argument('--cpu-embed', action='store_true')
    ap.add_argument('--keep', action='store_true', help='stay up after ready until STOP file or signal')
    ap.add_argument('--startup-timeout', type=int, default=1500)
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists() or (out.parent / 'FAULT.json').exists():
        raise RuntimeError('Output must be new and the campaign must not be fault-latched')
    if not 0.5 <= a.mem <= 0.975:
        raise RuntimeError('Memory utilization must stay within 0.5-0.975')
    helper = load('fp8_tp1_helper', HELPER)
    guard = load('fp8_tp1_guard', GUARD)
    lock = open('/tmp/qwen-short-prefill-stage.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    name = 'fp8-tp1-' + uuid.uuid4().hex[:12]
    helper.check_available(a.port, name)
    image_info = json.loads(helper.run(['docker', 'image', 'inspect', IMAGE]).stdout)[0]
    out.mkdir(parents=True)
    (out / 'cache').mkdir()
    overlay_hashes = {}
    if a.cpu_embed:
        shutil.copytree(OVERLAY, out / 'overlay', ignore=shutil.ignore_patterns('__pycache__', 'test_*'))
        overlay_hashes = {str(p.relative_to(out / 'overlay')): sha(p) for p in sorted((out / 'overlay').rglob('*')) if p.is_file()}
    argv = build(a, name, out, image_info['Config']['Env'])
    started = helper.now()
    baseline = guard.unaccounted_bytes(guard.parse_meminfo(Path('/proc/meminfo').read_text()))
    write(out / 'launch.json', {'argv': argv, 'started': started, 'rung': vars(a) | {'out': str(out)},
                                'reference_sha256': sha(REFERENCE), 'overlay_sha256': overlay_hashes,
                                'guard_sha256': sha(GUARD), 'baseline_unaccounted': baseline})
    state = {'status': 'starting', 'owner_pid': os.getpid(), 'container_name': name, 'image_id': IMAGE,
             'port': a.port, 'started_at': started, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    write(out / 'state.json', state)
    stopping = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopping.append(True))
    child = guard_proc = None
    failure = None
    try:
        with (out / 'server.log').open('x') as log:
            child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=helper.clean_env())
            deadline = time.monotonic() + a.startup_timeout
            while not stopping and not (out / 'STOP').exists():
                faults = [line for line in helper.journal(started).splitlines() if helper.FAULT.search(line)]
                if faults:
                    write(out.parent / 'FAULT.json', {'at': helper.now(), 'stage': str(out), 'lines': faults})
                    raise RuntimeError('Kernel GPU fault; campaign latched')
                if child.poll() is not None:
                    raise RuntimeError(f'Server exited {child.returncode}')
                if not state.get('container_id'):
                    info = helper.inspect_container(name)
                    if info:
                        state['container_id'] = info['Id']
                        write(out / 'state.json', state)
                if guard_proc is None and state.get('container_id'):
                    guard_proc = subprocess.Popen(['sudo', '-S', '-p', '', 'python3', str(GUARD), '--container-id', state['container_id'],
                                                   '--out', str(out), '--baseline-unaccounted', str(baseline)],
                                                  stdin=subprocess.PIPE, text=True, start_new_session=True)
                    guard_proc.stdin.write(PASSWORD_FILE.read_text().strip() + '\n')
                    guard_proc.stdin.close()
                if guard_proc is not None and guard_proc.poll() not in (None, 0):
                    raise RuntimeError(f'Host memory guard exited {guard_proc.returncode}')
                if state['status'] == 'starting':
                    if state.get('container_id') and helper.healthy(a.port):
                        state.update(status='ready', ready_at=helper.now())
                        write(out / 'state.json', state)
                        print(f'Ready: http://127.0.0.1:{a.port}/v1', flush=True)
                        if not a.keep:
                            break
                    elif time.monotonic() > deadline:
                        raise TimeoutError('Startup deadline exceeded')
                time.sleep(3)
    except BaseException as exc:
        failure = f'{type(exc).__name__}: {exc}'
    finally:
        confirmed = True
        if child is not None:
            info = helper.inspect_container(name)
            if info is not None and info['State']['Running']:
                helper.run(['docker', 'stop', '--time', '30', info['Id']], check=False, timeout=60)
            try:
                child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                confirmed = False
            final = helper.inspect_container(name)
            if final is not None:
                write(out / 'container-final.json', final)
                if final['State']['Running']:
                    confirmed = False
                else:
                    helper.run(['docker', 'rm', final['Id']], check=False, timeout=60)
        lines = [line for line in (out / 'server.log').read_text(errors='replace').splitlines() if MEMORY_LINES.search(line)] \
            if (out / 'server.log').exists() else []
        state.update(status='failed' if failure else ('stopped' if state['status'] != 'starting' else 'stopped-before-ready'),
                     error=failure, stop_confirmed=confirmed, finished_at=helper.now(), memory_log=lines[-40:])
        write(out / 'state.json', state)
        lock.close()
    print(json.dumps({k: state.get(k) for k in ('status', 'error', 'stop_confirmed', 'ready_at')}))


if __name__ == '__main__':
    main()
