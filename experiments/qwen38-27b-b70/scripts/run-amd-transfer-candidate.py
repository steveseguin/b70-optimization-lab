#!/usr/bin/env python3
"""One candidate application load; no automatic restoration/restart/retry.

Requires an already-built immutable image and stopped original service. Parent
owns the maintenance transition and reviews results before restoring service.
"""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = 'http://127.0.0.1:18128'
MODEL = 'qwen38-fp8-amd-transfer-screen'


def run(cmd, **kwargs):
    return subprocess.run([str(x) for x in cmd], capture_output=True, text=True,
                          timeout=90, check=True, **kwargs).stdout


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--control-root', type=Path, required=True)
    ap.add_argument('--draft-dir', type=Path, required=True)
    a = ap.parse_args()
    if not a.image.startswith('sha256:') or len(a.image) != 71:
        ap.error('image must be the exact local image ID')
    a.out.mkdir(parents=True, exist_ok=False)
    if (a.control_root / 'FAULT.json').exists():
        raise RuntimeError('campaign fault latch present')
    lock = open('/tmp/qwen-short-prefill-stage.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if run(['docker', 'ps', '-q']).strip():
        raise RuntimeError('another container is running')
    owners = subprocess.run(['fuser', '/dev/dri/renderD128', '/dev/dri/renderD129'], capture_output=True, text=True)
    (a.out / 'device-owners.txt').write_text(owners.stdout + owners.stderr)
    if owners.returncode != 1:
        raise RuntimeError('GPU owner present or ownership check failed')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 18128))
    image = json.loads(run(['docker', 'image', 'inspect', a.image]))[0]
    if image['Id'] != a.image:
        raise RuntimeError('image identity mismatch')
    save(a.out / 'image.json', image)
    control = json.loads((a.control_root / 'control-identity.json').read_text())
    env = dict(e.split('=', 1) for e in control['env'])
    env.update(VLLM_USE_V2_MODEL_RUNNER='1', VLLM_XPU_DRAFT_LM_HEAD_INT4='0',
               VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST='')
    spec = dict(method='dflash', model='/draft', num_speculative_tokens=7,
                draft_tensor_parallel_size=2, attention_backend='TRITON_ATTN')
    args = list(control['command'])
    args[args.index('--served-model-name') + 1] = MODEL
    args[args.index('--speculative-config') + 1] = json.dumps(spec)
    name = 'amd-transfer-dflash-' + str(os.getpid())
    cache = a.out / 'cache'
    cache.mkdir()
    cmd = ['docker', 'run', '--name', name, '--network', 'bridge', '--restart', 'no',
           '--device', '/dev/dri', '--group-add', 'render', '--ipc', 'host',
           '--shm-size', '8g', '--memory', '12g', '--memory-swap', '16g',
           '--ulimit', 'core=0', '--cap-add', 'SYS_PTRACE', '--security-opt', 'label=disable',
           '-p', '127.0.0.1:18128:8000', '--workdir', '/',
           '--mount', 'type=bind,source=/mnt/fast-ai/llm-models/qwen3.8-27b-fp8,target=/model,readonly',
           '--mount', f'type=bind,source={a.draft_dir.resolve()},target=/draft,readonly',
           '--mount', f'type=bind,source={cache.resolve()},target=/root/.cache/vllm']
    for key, value in sorted(env.items()):
        cmd += ['--env', f'{key}={value}']
    cmd += [a.image] + args
    save(a.out / 'launch.json', {'argv': cmd, 'speculative': spec,
        'scope': 'combined newest upstream + accepted overlay + V2 + DFlash2; unqualified',
        'started': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    child = None
    client = None
    def client_run(label, command, extra_env=None, timeout=1800):
        nonlocal client
        save(a.out / (label + '-command.json'), {'argv': list(map(str, command)), 'explicit_env': extra_env})
        with (a.out / (label + '.log')).open('w') as log:
            client = subprocess.Popen(list(map(str, command)), cwd=ROOT,
                env={**os.environ, **(extra_env or {})}, stdout=log, stderr=subprocess.STDOUT)
            try:
                code = client.wait(timeout=timeout)
                if code:
                    raise RuntimeError(f'{label} failed ({code}); subsequent requests skipped')
            finally:
                if client.poll() is None:
                    client.send_signal(signal.SIGINT)
                    client.wait(timeout=15)
                client = None
    try:
        with (a.out / 'server.log').open('w') as log:
            child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 1200
            while True:
                if child.poll() is not None:
                    raise RuntimeError('candidate exited before ready; no retry')
                try:
                    with urllib.request.urlopen(BASE + '/health', timeout=3) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError('candidate startup exceeded bound')
                time.sleep(3)
            save(a.out / 'container.json', json.loads(run(['docker', 'inspect', name]))[0])
            client_run('prefixes', [sys.executable, ROOT / 'experiments/qwen38-27b-b70/scripts/check-amd-transfer-prefixes.py',
                '--base-url', BASE, '--model', MODEL, '--reference-performance', a.control_root / 'control-strict/performance.json',
                '--output-dir', a.out / 'prefixes'])
            client_run('strict', ['bash', ROOT / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh'], {
                'OUT_DIR': str(a.out / 'strict'), 'BASE_URL': BASE, 'MODEL_NAME': MODEL,
                'PROFILE_LABEL': 'amd-transfer-dflash-screen', 'ATTEMPT_LABEL': 'single-candidate-process'})
            client_run('strict-parity', [sys.executable, ROOT / 'scripts/compare-strict-attempt-outputs.py',
                a.control_root / 'control-strict', a.out / 'strict', '--output', a.out / 'strict-parity.json'])
            comparison = json.loads((a.out / 'strict-parity.json').read_text())
            if comparison['comparison']['exact_prompts'] != 12 or comparison['comparison']['total_prompts'] != 12:
                raise RuntimeError('complete strict output mismatch; context timing skipped')
            client_run('contexts', [sys.executable, ROOT / 'experiments/qwen38-27b-b70/scripts/bench-prefill-followup.py',
                '--base-url', BASE, '--model', MODEL, '--out', a.out / 'contexts',
                '--corpus', ROOT / 'experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/corpus.json',
                '--lengths', '512,2048,16384', '--max-model-len', '33024', '--max-tokens', '128', '--repeats', '2',
                '--baseline', a.control_root / 'control-context/summary.json'])
            (a.out / 'SCREEN_PASSED').write_text('No promotion or independent-process confirmation claimed.\n')
    except BaseException as exc:
        (a.out / 'ABORTED').write_text(f'{type(exc).__name__}: {exc}\n')
        raise
    finally:
        if client is not None and client.poll() is None:
            client.send_signal(signal.SIGINT)
        found = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=20)
        if found.returncode == 0:
            record = json.loads(found.stdout)[0]
            save(a.out / 'final-container.json', record)
            if record['Image'] != a.image:
                raise RuntimeError('owned container image unexpectedly changed')
            if record['State']['Running']:
                stopped = subprocess.run(['docker', 'stop', '--time', '30', record['Id']], capture_output=True, text=True, timeout=45)
                (a.out / 'stop.log').write_text(stopped.stdout + stopped.stderr)
                if stopped.returncode:
                    raise RuntimeError('single graceful stop failed; no retry')
            subprocess.run(['docker', 'rm', record['Id']], check=True, capture_output=True, text=True, timeout=20)
        if child is not None:
            child.wait(timeout=20)
        lock.close()


if __name__ == '__main__':
    main()
