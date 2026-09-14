#!/usr/bin/env python3
"""One published R304 FP8 server, bounded 512/2048 prefill and profiling. No retries/restarts.

Adapted from run-prefill-followup-stage.py; the frozen original is unchanged.
Preserves the frozen earlier campaign; optional profiler requests are separate
from all measurements. This measures a baseline, not an optimization promotion.
"""
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
import sys
import time
import urllib.request

REPO = Path(__file__).resolve().parents[3]
SHARED = REPO / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70'
R308 = 'sha256:b9bbb5190f6dd47973501e61aa129706c92345b310eeec4537a20256eba424ba'
R304 = 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2'
KERNEL = '6d92b1bfbf32767ecda8e819613eb151e70030ad'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)
RUNTIME = '/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py'
PROFILES = {
    '27b-fp8': ('experiments/qwen38-27b-b70/scripts/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh', '/mnt/fast-ai/llm-models/qwen3.8-27b-fp8', 2, 1, R304),
}
REFERENCES = {
    '27b-fp8': '/mnt/fast-ai/bench-results/qwen38-fp8-rebase-v0290-rb1-20260913/mtp1-a/strict',
}


def checked(cmd, **kwargs):
    return subprocess.run([str(x) for x in cmd], check=True, text=True, capture_output=True, timeout=90, **kwargs).stdout


def write_json(path, obj):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, indent=2) + '\n')
    os.replace(temp, path)


def faults(text):
    return [line for line in text.splitlines() if FAULT.search(line) and not line.endswith('Xe device coredump has been deleted.')]


def check_port_available(port):
    # Reuse a closed listener's TIME_WAIT tuples without sharing a live listener.
    # SO_REUSEPORT is deliberately absent: an active listener must still fail.
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', port))
        sock.listen(1)


class Stage:
    def __init__(self, args):
        self.a = args
        self.out = args.out.resolve()
        self.server = None
        self.client = None
        self.started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.name = f'fp8-prefill-focus-{os.getpid()}'
        self.owned = False

    def journal(self, label):
        text = checked(['journalctl', '-k', '-b', '0', '--no-pager', '--since', self.started])
        (self.out / f'{label}-journal.txt').write_text(text)
        bad = faults(text)
        if bad:
            (self.out / 'fault-lines.txt').write_text('\n'.join(bad) + '\n')
            raise RuntimeError('new kernel fault; halting requests')

    def monitor(self, process, timeout, label):
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            self.journal(label)
            if time.monotonic() >= deadline:
                raise TimeoutError(f'{label} exceeded {timeout}s')
            if self.server is not None and self.server.poll() is not None:
                raise RuntimeError('owned server exited during workload')
            time.sleep(3)
        self.journal(label)
        if process.returncode:
            raise RuntimeError(f'{label} exited {process.returncode}')

    @staticmethod
    def terminate(process):
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=15)

    def phase(self, label, cmd, extra=None):
        env = self.env.copy()
        env.update(extra or {})
        write_json(self.out / f'{label}-command.json', {'argv': [str(x) for x in cmd], 'explicit_env': extra or {}})
        with (self.out / f'{label}.log').open('w') as log:
            self.client = subprocess.Popen([str(x) for x in cmd], env=env, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                self.monitor(self.client, 900, label)
            finally:
                self.terminate(self.client)
                self.client = None

    def bench(self, arm, baseline=False):
        cmd = [sys.executable, Path(__file__).with_name('bench-prefill-followup.py'), '--base-url', self.base,
            '--model', self.name, '--out', self.out / arm, '--lengths', '512,2048',
            '--max-model-len', '4096', '--corpus', REPO / 'experiments/qwen38-27b-b70/data/2026-09-14-fp8-prefill-corpus.json']
        if baseline:
            cmd += ['--baseline', self.out / 'baseline/summary.json']
        self.phase(arm, cmd)

    def strict(self, arm):
        self.phase(arm + '-strict', ['bash', SHARED / 'bench-w8a16-mtp1-strict.sh'], {
            'OUT_DIR': str(self.out / (arm + '-strict')), 'BASE_URL': self.base,
            'MODEL_NAME': self.name, 'PROFILE_LABEL': 'short-prefill-' + self.a.profile,
            'ATTEMPT_LABEL': arm + '-same-process',
            'SUITE': str(REPO / 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json')})

    def run(self):
        self.out.mkdir(parents=True, exist_ok=False)
        lock = open('/tmp/qwen-short-prefill-stage.lock', 'w')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if checked(['docker', 'ps', '-q']).strip():
            raise RuntimeError('another container is running')
        owners = subprocess.run(['fuser', '/dev/dri/renderD128', '/dev/dri/renderD129'], text=True, capture_output=True)
        (self.out / 'device-owners.txt').write_text(owners.stdout + owners.stderr)
        if owners.returncode != 1:
            raise RuntimeError('render device owned or ownership check failed')
        check_port_available(self.a.port)
        launcher, model, tp, depth, parent = PROFILES[self.a.profile]
        self.a.image = parent
        self.a.image_id = parent
        image = json.loads(checked(['docker', 'image', 'inspect', self.a.image]))
        if image[0]['Id'] != self.a.image_id:
            raise RuntimeError('published image ID mismatch')
        write_json(self.out / 'image-inspect.json', image)
        (self.out / 'cache').mkdir()
        explicit = dict(IMAGE=self.a.image, EXPECTED_IMAGE_ID=self.a.image_id,
            EXPECTED_KERNEL_HEAD=KERNEL, MODEL_DIR=model,
            VLLM_CACHE_DIR=str(self.out / 'cache'), CONTAINER_NAME=self.name,
            SERVED_MODEL_NAME=self.name, PORT=str(self.a.port), MAX_MODEL_LEN='4096',
            MAX_NUM_BATCHED_TOKENS='4096', MAX_NUM_SEQS='1', TENSOR_PARALLEL_SIZE=str(tp),
            MTP_DEPTH=str(depth), XPU_DEVICE_MASK='0' if tp == 1 else '0,1',
            VLLM_USE_V2_MODEL_RUNNER='0', CLASSPAD='0', VLLM_XPU_FP16_LINEAR_CLASSPAD='0',
            GPU_MEMORY_UTILIZATION='0.96' if tp == 1 else '0.95')
        if self.a.profile_trace:
            explicit.update(PROFILER_CONFIG=json.dumps({'profiler': 'torch', 'torch_profiler_dir': '/profiles', 'torch_profiler_with_stack': False, 'torch_profiler_record_shapes': True}), PROFILER_DIR=str(self.out / 'profile'))
        # Keep launch configuration isolated from unrelated inherited experiment knobs.
        self.env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'USER', 'LANG', 'LC_ALL', 'TMPDIR')}
        self.env.update(explicit)
        write_json(self.out / 'identity.json', {'argv': sys.argv, 'explicit_env': explicit,
            'parent_image': parent, 'runtime_path': RUNTIME,
            'started_utc': self.started, 'scope': 'unchanged published R304 baseline; one process, no new decode or optimization promotion'})
        self.base = f'http://127.0.0.1:{self.a.port}'
        self.journal('baseline')
        # Retain complete qualified outputs, not just an external host path.
        import shutil
        shutil.copyfile(SHARED / 'model-direct.json', self.out / 'model-manifest.json')
        shutil.copytree(REFERENCES[self.a.profile], self.out / 'original-reference')
        write_json(self.out / 'original-reference-hashes.json', {str(p.relative_to(self.out / 'original-reference')): hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.out / 'original-reference').rglob('*') if p.is_file()})
        self.phase('preflight-health', ['bash', REPO / 'scripts/check-qwen36-xpu-xccl-health.sh'],
            {'ROOT': str(REPO), 'PHYSICAL_DEVICES': '0,1', 'XCCL_DEVICES': '0,1', 'XCCL_MASTER_PORT': '29519', 'PYTHON': '/home/steve/.venvs/vllm-xpu/bin/python'})
        self.journal('preflight-final')
        success = False
        try:
            with (self.out / 'launcher.log').open('w') as log:
                self.server = subprocess.Popen(['bash', str(REPO / launcher)], env=self.env, cwd=REPO,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                self.owned = True
                deadline = time.monotonic() + 1200
                while True:
                    self.journal('startup')
                    if self.server.poll() is not None:
                        raise RuntimeError('launcher exited before healthy')
                    try:
                        with urllib.request.urlopen(self.base + '/health', timeout=3) as response:
                            if response.status == 200:
                                break
                    except (OSError, TimeoutError):
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError('startup exceeded1200s')
                    time.sleep(5)
                write_json(self.out / 'container-inspect.json', json.loads(checked(['docker', 'inspect', self.name])))
                actual = checked(['docker', 'exec', self.name, 'sha256sum', RUNTIME])
                (self.out / 'runtime-sha256.txt').write_text(actual)
                self.bench('baseline')
                self.strict('baseline')
                self.phase('original-reference-comparison', [sys.executable, REPO / 'scripts/compare-strict-attempt-outputs.py',
                    self.out / 'original-reference', self.out / 'baseline-strict', '--output', self.out / 'original-reference-comparison.json'])
                comparison = json.loads((self.out / 'original-reference-comparison.json').read_text())
                if not comparison['qualification']['strict_pair_qualified'] or comparison['comparison']['exact_prompts'] != 12 or comparison['comparison']['total_prompts'] != 12:
                    raise RuntimeError('strict complete original-output parity failed')
                if self.a.profile_trace:
                    # One trace only after unprofiled measurements and quality gates.
                    self.phase('profile-request', [sys.executable, Path(__file__).with_name('profile-prefill-followup.py'),
                        '--base-url', self.base, '--model', self.name, '--out', self.out / 'profile-request',
                        '--baseline', self.out / 'baseline/summary.json'])
                    traces = [p for p in (self.out / 'profile').rglob('*') if p.is_file() and p.stat().st_size > 100 and '.pt.trace.json' in p.name]
                    if not traces:
                        raise RuntimeError('profiler exported no nonempty traces')
                    write_json(self.out / 'profile-trace-hashes.json', {str(p.relative_to(self.out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in traces})
                self.bench('final-control', True)
                self.journal('workload-final')
                success = True
        except BaseException as exc:
            (self.out / 'ABORTED').write_text(f'{type(exc).__name__}: {exc}\n')
            raise
        finally:
            self.terminate(self.client)
            if self.owned:
                # One graceful stop only; never remove or stop another container.
                stop = subprocess.run(['docker', 'stop', '-t', '60', self.name], text=True, capture_output=True, timeout=90)
                (self.out / 'stop.log').write_text(stop.stdout + stop.stderr)
                self.terminate(self.server)
            if checked(['docker', 'ps', '-q']).strip():
                raise RuntimeError('container remains running after stage')
            self.server = None
            self.journal('post-stop')
            discovery = checked(['xpu-smi', 'discovery'])
            (self.out / 'postflight-discovery.txt').write_text(discovery)
            if discovery.count('Device State: normal') != 2:
                raise RuntimeError('postflight device state abnormal')
            self.phase('postflight-health', ['bash', REPO / 'scripts/check-qwen36-xpu-xccl-health.sh'],
                {'ROOT': str(REPO), 'PHYSICAL_DEVICES': '0,1', 'XCCL_DEVICES': '0,1', 'XCCL_MASTER_PORT': '29519', 'PYTHON': '/home/steve/.venvs/vllm-xpu/bin/python'})
            self.journal('postflight-final')
            if success:
                (self.out / 'DONE').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat() + '\n')
        lock.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', choices=PROFILES, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=18152)
    ap.add_argument('--profile-trace', action='store_true')
    args = ap.parse_args()
    def interrupted(signum, frame):
        raise RuntimeError(f'received signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    Stage(args).run()

if __name__ == '__main__':
    main()
