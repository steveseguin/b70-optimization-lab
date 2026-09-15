#!/usr/bin/env python3
"""Bounded no-model allocation diagnostic for the newest-base research image.

Question: does a plain 2 GiB XPU allocation on image 506fcc26 leave host RAM in
GPU driver pages when both GPUs are visible, and does the qualified allocator
setting (PYTORCH_ALLOC_CONF=expandable_segments:True) prevent it? The research
launch that omitted that setting exhausted host RAM
(notes/2026-09-15-research-load-host-oom.md). No model, collectives or IPC.

One short container at a time, safest first, each under the root host-memory
guard and the kernel fault monitor. A kernel fault, guard trip or unconfirmed
stop ends the sequence. No retries. --check-only makes no Docker or GPU calls.
"""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / 'experiments/qwen38-27b-b70/scripts'
GUARD = SCRIPTS / 'host_memory_guard.py'
HELPER = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
IMAGE = 'sha256:506fcc26897b12915cb9e27c28e0adc256d278666fa745602a1ae5e1dd8ea066'
CAMPAIGN = Path('/mnt/fast-ai/bench-results/optimization-validation-20260915')
PASSWORD_FILE = Path('/home/steve/SUDO_PASSWORD.txt')
GIB = 1024 ** 3
ALLOC_BYTES = 2 * GIB
GUARD_MAX_GROWTH_GIB = 3
GUARD_MIN_AVAILABLE_GIB = 6
WORKER = f'''
import json, time, torch
torch.xpu.set_device(0)
x = torch.empty({ALLOC_BYTES}, dtype=torch.uint8, device="xpu")
x.fill_(1)
torch.xpu.synchronize()
time.sleep(4)
print("ALLOC-DONE " + json.dumps({{"torch": torch.__version__, "devices": torch.xpu.device_count(),
      "allocated": torch.xpu.memory_allocated()}}), flush=True)
'''
# Safest first: one visible GPU, then the qualified allocator, then the omitted setting.
RUNS = (
    ('one-gpu-default', {'ONEAPI_DEVICE_SELECTOR': 'level_zero:0', 'ZE_AFFINITY_MASK': '0'}),
    ('two-gpu-expandable', {'ONEAPI_DEVICE_SELECTOR': 'level_zero:0,1', 'ZE_AFFINITY_MASK': '0,1',
                            'PYTORCH_ALLOC_CONF': 'expandable_segments:True'}),
    ('two-gpu-default', {'ONEAPI_DEVICE_SELECTOR': 'level_zero:0,1', 'ZE_AFFINITY_MASK': '0,1'}),
)
PRIME_EXPORT = re.compile(r'PRIME_HANDLE_TO_FD', re.I)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def docker_argv(name, env):
    argv = ['docker', 'run', '-d', '--name', name, '--restart', 'no', '--network', 'none',
            '--device', '/dev/dri', '--group-add', 'render', '--ipc', 'host', '--cap-add', 'SYS_PTRACE',
            '--shm-size', '8g', '--memory', '12g', '--memory-swap', '16g', '--ulimit', 'core=0',
            '--security-opt', 'label=disable', '--workdir', '/', '--entrypoint', '/opt/venv/bin/python3']
    for key, value in sorted({'NEOReadDebugKeys': '1', 'PrintIoctlEntries': '1', **env}.items()):
        argv += ['--env', f'{key}={value}']
    return argv + [IMAGE, '-c', WORKER]


def run_result(label, env, samples, baseline, exit_code, fault_lines, guard_fired, log_text, timed_out):
    growth = (max(s['unaccounted'] for s in samples) - baseline) / GIB if samples else None
    return {'label': label, 'env': env, 'exit_code': exit_code, 'timed_out': timed_out,
            'guard_fired': guard_fired, 'fault_lines': fault_lines,
            'driver_growth_gib': None if growth is None else round(growth, 3),
            'min_available_gib': round(min(s['available'] for s in samples) / GIB, 3) if samples else None,
            'prime_exports': len(PRIME_EXPORT.findall(log_text)),
            'alloc_done': 'ALLOC-DONE' in log_text, 'guard_samples': len(samples)}


def clean(result):
    return bool(result and result['exit_code'] == 0 and result['alloc_done'] and not result['guard_fired']
                and not result['fault_lines'] and not result['timed_out']
                and result['driver_growth_gib'] is not None and result['driver_growth_gib'] < 0.5)


def verdict(results):
    by = {r['label']: r for r in results}
    repro = by.get('two-gpu-default')
    faults = any(r['fault_lines'] for r in results)
    return {'expandable_two_gpu_clean': clean(by.get('two-gpu-expandable')),
            'one_gpu_clean': clean(by.get('one-gpu-default')),
            'default_two_gpu_reproduces': bool(repro and (repro['guard_fired'] or repro['prime_exports'] > 0
                                                          or (repro['driver_growth_gib'] or 0) >= 1.5)),
            'gpu_fault': faults,
            'model_launch_admissible': clean(by.get('two-gpu-expandable')) and not faults}


def meminfo_unaccounted(guard):
    return guard.unaccounted_bytes(guard.parse_meminfo(Path('/proc/meminfo').read_text()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, default=CAMPAIGN / 'alloc-diagnostic-01')
    ap.add_argument('--timeout', type=int, default=180)
    ap.add_argument('--check-only', action='store_true')
    a = ap.parse_args()
    out = a.out.resolve()
    if (out.parent / 'FAULT.json').exists() or out.exists():
        raise RuntimeError('Output must be new and the campaign must not be fault-latched')
    if not 30 <= a.timeout <= 600:
        raise RuntimeError('Per-run timeout must be 30-600 seconds')
    plan = {'image': IMAGE, 'runs': [{'label': label, 'env': env} for label, env in RUNS],
            'alloc_bytes': ALLOC_BYTES, 'guard': {'max_growth_gib': GUARD_MAX_GROWTH_GIB, 'min_available_gib': GUARD_MIN_AVAILABLE_GIB},
            'sources': {'diagnostic': sha(__file__), 'guard': sha(GUARD), 'helper': sha(HELPER)}}
    if a.check_only:
        print(json.dumps({'check_only': True, 'docker_calls': 0, 'gpu_actions': 0, **plan}, indent=2))
        return
    helper = load('fp8_helper_for_alloc_diagnostic', HELPER)
    guard = load('host_memory_guard_for_alloc_diagnostic', GUARD)
    lock = open('/tmp/qwen-short-prefill-stage.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    helper.check_available(18131, 'alloc-diagnostic-probe')
    out.mkdir(parents=True)
    (out / 'plan.json').write_text(json.dumps({**plan, 'started': helper.now(),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}, indent=2) + '\n')
    password = PASSWORD_FILE.read_text().strip()
    results = []
    for label, env in RUNS:
        run_dir = out / label
        run_dir.mkdir()
        name = f'alloc-diag-{label}-{uuid.uuid4().hex[:8]}'
        baseline = meminfo_unaccounted(guard)
        since = helper.now()
        argv = docker_argv(name, env)
        (run_dir / 'launch.json').write_text(json.dumps({'argv': argv, 'since': since, 'baseline_unaccounted': baseline}, indent=2) + '\n')
        cid = helper.run(argv, timeout=60).stdout.strip()
        if not re.fullmatch(r'[0-9a-f]{64}', cid):
            raise RuntimeError('Docker returned no container ID; stopping')
        guard_proc = subprocess.Popen(['sudo', '-S', '-p', '', 'python3', str(GUARD), '--container-id', cid,
                                       '--out', str(run_dir), '--baseline-unaccounted', str(baseline),
                                       '--max-growth-gib', str(GUARD_MAX_GROWTH_GIB),
                                       '--min-available-gib', str(GUARD_MIN_AVAILABLE_GIB), '--interval', '0.25'],
                                      stdin=subprocess.PIPE, text=True)
        guard_proc.stdin.write(password + '\n')
        guard_proc.stdin.close()
        deadline = time.monotonic() + a.timeout
        fault_lines, timed_out = [], False
        while True:
            fault_lines = [line for line in helper.journal(since).splitlines() if helper.FAULT.search(line)]
            info = helper.inspect_container(cid)
            if fault_lines or guard_proc.poll() is not None or info is None or not info['State']['Running']:
                break
            if time.monotonic() > deadline:
                timed_out = True
                break
            time.sleep(1)
        info = helper.inspect_container(cid)
        if info is not None and info['State']['Running']:
            helper.run(['docker', 'stop', '--time', '10', cid], check=False, timeout=40)
        final = helper.inspect_container(cid)
        logs = helper.run(['docker', 'logs', cid], check=False, timeout=60)
        log_text = logs.stdout + logs.stderr
        (run_dir / 'container.log').write_text(log_text)
        if final is not None:
            (run_dir / 'container-final.json').write_text(json.dumps(final, indent=2) + '\n')
        try:
            guard_code = guard_proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            guard_code = None
        kernel = helper.journal(since)
        (run_dir / 'kernel.log').write_text(kernel)
        fault_lines = [line for line in kernel.splitlines() if helper.FAULT.search(line)]
        samples_path = run_dir / 'memory-guard.jsonl'
        samples = [json.loads(line) for line in samples_path.read_text().splitlines()] if samples_path.exists() else []
        running = final is not None and final['State']['Running']
        exit_code = None if final is None or running else final['State']['ExitCode']
        result = run_result(label, env, samples, baseline, exit_code, fault_lines, guard_code == guard.FIRED_EXIT, log_text, timed_out)
        result.update(container_id=cid, guard_exit=guard_code, stop_confirmed=not running)
        (run_dir / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        results.append(result)
        if final is not None and not running:
            helper.run(['docker', 'rm', cid], check=False, timeout=60)
        if fault_lines:
            with (out.parent / 'FAULT.json').open('x') as latch:
                json.dump({'at': helper.now(), 'stage': str(out), 'run': label, 'lines': fault_lines}, latch, indent=2)
            break
        if running or guard_code is None or result['guard_fired']:
            break
    summary = {'schema': 'neural.download.newest-base-alloc-diagnostic.v1', 'finished': helper.now(),
               'results': results, 'verdict': verdict(results), 'runs_planned': len(RUNS)}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    lock.close()
    print(json.dumps(summary['verdict'], indent=2))


if __name__ == '__main__':
    main()
