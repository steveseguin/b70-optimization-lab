#!/usr/bin/env python3
"""One supervised local pilot server; no retries, settings changes or hard kills."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

REPO = Path(__file__).resolve().parents[3]
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python'
MODEL = '/home/steve/.cache/huggingface/hub/models--Qwen--Qwen3.5-0.8B/snapshots/2fc06364715b967f1860aea9cf38778875588b17'
FAULT = re.compile(r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump|Timedout job|wedged|Out of memory: Killed process', re.I)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    interrupted = []
    def request_stop(signum, frame):
        interrupted.append(signum)
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    signalled = set()
    def graceful_stop(child):
        if child.poll() is None and child.pid not in signalled:
            signalled.add(child.pid)
            try: child.send_signal(signal.SIGINT)
            except ProcessLookupError: pass
        child.wait()  # Hold all locks until exit; never escalate or retry.
    def save(name, value):
        with (out / name).open('w') as stream:
            json.dump(value, stream, indent=2); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
    def journal(since=None):
        cmd = ['journalctl', '-k', '-b', '--no-pager']
        if since: cmd += ['--since', since]
        return subprocess.check_output(cmd, text=True, timeout=20)
    def run_probe(command, environment, log_path, label):
        if interrupted: raise RuntimeError('Interrupted; refusing a new probe')
        with log_path.open('w') as log:
            child = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            try:
                return child.wait(timeout=120)
            except subprocess.TimeoutExpired:
                save('FAULT.json', {'reason': label + ' timeout', 'pid': child.pid})
                raise
            finally:
                if child.poll() is None: graceful_stop(child)
    handles = []
    for name in ['/run/lock/muse-glimmer-gpu-exclusive.lock', '/tmp/b70-benchmark.lock'] + [f'/tmp/b70-gpu{i}.lock' for i in range(4)]:
        handle = open(name, 'a'); fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB); handles.append(handle)
    for key in ('ZE_AFFINITY_MASK', 'ONEAPI_DEVICE_SELECTOR', 'SYCL_DEVICE_FILTER'):
        if os.environ.get(key): raise RuntimeError('Unexpected inherited device filter: ' + key)
    nodes = sorted(Path('/dev/dri').glob('renderD*'))
    if len(nodes) != 4: raise RuntimeError('Expected four render nodes')
    owners = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, timeout=10)
    if owners.returncode != 1 or owners.stdout or owners.stderr: raise RuntimeError('Render nodes not idle')
    if subprocess.check_output(['docker', 'ps', '-q'], timeout=10).strip(): raise RuntimeError('Container already running')
    with socket.socket() as sock: sock.bind(('127.0.0.1', 18125))
    mem = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
    if mem['MemAvailable'] < 32 * 1024**2: raise RuntimeError('Require 32GiB available RAM')
    for block in range(53, 58):
        if Path(f'/sys/devices/system/memory/memory{block}/state').read_text().strip() != 'offline':
            raise RuntimeError('Existing RAM exclusion is not in place')
    disk = os.statvfs(out)
    if disk.f_bavail * disk.f_frsize < 50 * 1024**3 + 256 * 1024**2: raise RuntimeError('Disk reserve not met')
    before = journal(); (out / 'journal-before.txt').write_text(before)
    # Historical October4 OOMs are preserved in the baseline. Any new OOM halts
    # this pilot; no device-fault recovery is automated by this launcher.
    historical_gpu_faults = [line for line in before.splitlines() if FAULT.search(line) and 'Out of memory: Killed process' not in line]
    if historical_gpu_faults: raise RuntimeError('Current boot contains device fault evidence; review before launch')
    since = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('VLLM_', 'B70_', 'CCL_', 'ZE_', 'SYCL_', 'ONEAPI_', 'TORCH_'))}
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='8', MKL_NUM_THREADS='8')
    probe_command = [PYTHON, '-B', str(REPO / 'experiments/ltx25-b70/scripts/check-four-card-health.py'), str(out / 'health.json')]
    probe_code = run_probe(probe_command, env, out / 'health.log', 'preflight')
    if probe_code or not json.loads((out / 'health.json').read_text()).get('passed'):
        raise RuntimeError('Health probe failed; no model launched')
    env.update(ZE_AFFINITY_MASK='0', VLLM_PLUGINS='')
    command = [PYTHON, '-B', '-m', 'vllm.entrypoints.openai.api_server', '--model', MODEL,
               '--served-model-name', 'qwen35-0.8b-bf16-pilot', '--host', '127.0.0.1', '--port', '18125',
               '--dtype', 'bfloat16', '--kv-cache-dtype', 'auto', '--tensor-parallel-size', '1',
               '--pipeline-parallel-size', '1', '--max-model-len', '16384', '--max-num-seqs', '1',
               '--max-num-batched-tokens', '512', '--gpu-memory-utilization', '0.25',
               '--language-model-only', '--no-enable-prefix-caching', '--enforce-eager']
    save('launch.json', {'command': command, 'experiment_env': {k: env[k] for k in ['HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'ZE_AFFINITY_MASK', 'VLLM_PLUGINS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']},
                        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'since': since,
                        'supervisor_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'server_start_planned': True})
    stop_sent = False; started = time.monotonic(); reason = 'server exited'
    with (out / 'server.log').open('w') as log:
        admission_journal = journal(since)
        (out / 'journal-admission.txt').write_text(admission_journal)
        if interrupted or FAULT.search(admission_journal):
            raise RuntimeError('Interrupted or new fault during admission; no server launch')
        child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            save('pid.json', {'server_pid': child.pid, 'supervisor_pid': os.getpid(), 'server_start_attempts': 1})
            while child.poll() is None:
                current = journal(since)
                if FAULT.search(current):
                    save('FAULT.json', {'reason': 'new kernel fault'}); (out / 'journal-fault.txt').write_text(current)
                stop = interrupted or (out / 'STOP').exists() or (out / 'FAULT.json').exists() or time.monotonic() - started > 2400
                if stop and not stop_sent:
                    reason = 'fault' if (out / 'FAULT.json').exists() else 'requested stop or 40-minute deadline'
                    signalled.add(child.pid); stop_sent = True
                    try: child.send_signal(signal.SIGINT)
                    except ProcessLookupError: pass
                    save('stop-signal.json', {'reason': reason, 'signal': 'SIGINT', 'server_pid': child.pid})
                time.sleep(3)
        except BaseException as exc:
            save('FAULT.json', {'reason': 'supervisor error', 'error': str(exc)})
            raise
        finally:
            if child.poll() is None: graceful_stop(child)
    after = journal(since); (out / 'journal-after.txt').write_text(after)
    remaining = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, timeout=10)
    idle = remaining.returncode == 1 and not remaining.stdout and not remaining.stderr
    postflight_passed = False
    if idle and not interrupted and not FAULT.search(after) and not (out / 'FAULT.json').exists():
        post_env = dict(env); post_env.pop('ZE_AFFINITY_MASK')
        code = run_probe([*probe_command[:-1], str(out / 'postflight-health.json')], post_env, out / 'postflight-health.log', 'postflight')
        postflight_passed = code == 0 and json.loads((out / 'postflight-health.json').read_text()).get('passed', False)
        after = journal(since); (out / 'journal-after.txt').write_text(after)
    save('shutdown.json', {'returncode': child.returncode, 'reason': reason, 'stop_signal_sent': stop_sent,
                          'new_kernel_fault': bool(FAULT.search(after)), 'render_nodes_idle': idle, 'four_card_postflight_passed': postflight_passed})
    return 0 if child.returncode == 0 and not FAULT.search(after) and postflight_passed else 1


if __name__ == '__main__': raise SystemExit(main())
