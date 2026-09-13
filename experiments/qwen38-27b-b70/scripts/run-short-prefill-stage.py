#!/usr/bin/env python3
"""One owned server, serial short-context A/B/A screen. No retries or restarts.

This experimental overlay requires an independently checked parent-contract
receipt and a pinned modified runtime file. It does not qualify a public image.
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
    '4b': ('repro/qwen35-4b-w4a16-b70/scripts/run-qwen35-4b-w4a16-server.sh', '/home/steve/llm-models/qwen35-4b-w4a16', 1, 3, R308),
    '9b': ('repro/qwen35-9b-w4a16-b70/scripts/run-qwen35-9b-w4a16-server.sh', '/home/steve/llm-models/qwen35-9b-w4a16', 1, 3, R308),
    '27b-int4': ('repro/qwen38-27b-autoround-int4-b70/scripts/run-fixed-k-mtp-server.sh', '/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel', 2, 4, R304),
    '27b-fp8': ('experiments/qwen38-27b-b70/scripts/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh', '/mnt/fast-ai/llm-models/qwen3.8-27b-fp8', 2, 1, R304),
}


def checked(cmd, **kwargs):
    return subprocess.run([str(x) for x in cmd], check=True, text=True, capture_output=True, timeout=90, **kwargs).stdout


def write_json(path, obj):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, indent=2) + '\n')
    os.replace(temp, path)


def faults(text):
    return [line for line in text.splitlines() if FAULT.search(line) and not line.endswith('Xe device coredump has been deleted.')]


class Stage:
    def __init__(self, args):
        self.a = args
        self.out = args.out.resolve()
        self.server = None
        self.client = None
        self.started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.name = f'short-prefill-{args.profile}-{os.getpid()}'
        self.flag = self.out / 'cache/prefill-direct-out.enabled'
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
        cmd = [sys.executable, Path(__file__).with_name('bench-short-prefill.py'), '--base-url', self.base,
            '--model', self.name, '--out', self.out / arm]
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
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', self.a.port))
        receipt = self.a.base_contract_receipt.read_bytes()
        if not receipt or b'PASS' not in receipt:
            raise RuntimeError('parent contract receipt lacks PASS')
        (self.out / 'parent-contract.log').write_bytes(receipt)
        launcher, model, tp, depth, parent = PROFILES[self.a.profile]
        image = json.loads(checked(['docker', 'image', 'inspect', self.a.image]))
        if image[0]['Id'] != self.a.image_id:
            raise RuntimeError('overlay image ID mismatch')
        write_json(self.out / 'image-inspect.json', image)
        (self.out / 'cache').mkdir()
        explicit = dict(IMAGE=self.a.image, EXPECTED_IMAGE_ID=self.a.image_id,
            EXPECTED_KERNEL_HEAD=KERNEL, SKIP_IMAGE_CONTRACT='1', MODEL_DIR=model,
            VLLM_CACHE_DIR=str(self.out / 'cache'), CONTAINER_NAME=self.name,
            SERVED_MODEL_NAME=self.name, PORT=str(self.a.port), MAX_MODEL_LEN='1024',
            MAX_NUM_BATCHED_TOKENS='1024', MAX_NUM_SEQS='1', TENSOR_PARALLEL_SIZE=str(tp),
            MTP_DEPTH=str(depth), XPU_DEVICE_MASK='0' if tp == 1 else '0,1',
            VLLM_USE_V2_MODEL_RUNNER='0', CLASSPAD='0', VLLM_XPU_FP16_LINEAR_CLASSPAD='0')
        # Keep launch configuration isolated from unrelated inherited experiment knobs.
        self.env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'USER', 'LANG', 'LC_ALL', 'TMPDIR')}
        self.env.update(explicit)
        write_json(self.out / 'identity.json', {'argv': sys.argv, 'explicit_env': explicit,
            'parent_image': parent, 'parent_receipt_sha256': hashlib.sha256(receipt).hexdigest(),
            'runtime_path': RUNTIME, 'runtime_sha256': self.a.runtime_sha256,
            'started_utc': self.started, 'scope': 'same-server experimental A/B/A, no headline qualification'})
        self.base = f'http://127.0.0.1:{self.a.port}'
        self.journal('baseline')
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
                if actual.split()[0] != self.a.runtime_sha256:
                    raise RuntimeError('runtime file SHA mismatch')
                self.bench('baseline')
                self.strict('baseline')
                self.flag.write_text('enabled by client-owned A/B/A stage\n')
                self.bench('candidate', True)
                self.strict('candidate')
                self.phase('strict-comparison', [sys.executable, REPO / 'scripts/compare-strict-attempt-outputs.py',
                    self.out / 'baseline-strict', self.out / 'candidate-strict', '--output', self.out / 'strict-comparison.json'])
                comparison = json.loads((self.out / 'strict-comparison.json').read_text())
                if not comparison['qualification']['strict_pair_qualified'] or comparison['comparison']['exact_prompts'] != 12 or comparison['comparison']['total_prompts'] != 12:
                    raise RuntimeError('strict complete output parity failed')
                self.flag.unlink()
                self.bench('final-control', True)
                self.journal('workload-final')
                success = True
        except BaseException as exc:
            (self.out / 'ABORTED').write_text(f'{type(exc).__name__}: {exc}\n')
            raise
        finally:
            self.flag.unlink(missing_ok=True)
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
                {'ROOT': str(REPO), 'PHYSICAL_DEVICES': '0,1', 'XCCL_DEVICES': '0,1', 'PYTHON': '/home/steve/.venvs/vllm-xpu/bin/python'})
            self.journal('postflight-final')
            if success:
                (self.out / 'DONE').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat() + '\n')
        lock.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', choices=PROFILES, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=18139)
    ap.add_argument('--image', required=True)
    ap.add_argument('--image-id', required=True)
    ap.add_argument('--runtime-sha256', required=True)
    ap.add_argument('--base-contract-receipt', type=Path, required=True)
    args = ap.parse_args()
    if not re.fullmatch('[a-f0-9]{64}', args.runtime_sha256):
        ap.error('runtime SHA must be64hex characters')
    def interrupted(signum, frame):
        raise RuntimeError(f'received signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    Stage(args).run()

if __name__ == '__main__':
    main()
