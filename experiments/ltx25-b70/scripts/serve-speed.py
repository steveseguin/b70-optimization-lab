#!/usr/bin/env python3
"""Persistent optimization server; one planned migration, no restart policy."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import threading
import time

LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
EVIDENCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
RUN = EVIDENCE / 'speed-server'
RUN.mkdir(exist_ok=False)
FAULT = re.compile(r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump', re.I)
locks = []
for name in ['/run/lock/muse-glimmer-gpu-exclusive.lock', '/tmp/b70-benchmark.lock'] + [
        f'/tmp/b70-gpu{i}.lock' for i in range(4)]:
    handle = open(name, 'a')
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    locks.append(handle)
assert not subprocess.check_output(['docker', 'ps', '-q'], text=True, timeout=10).strip()
nodes = list(Path('/dev/dri').glob('renderD*'))
assert len(nodes) == 4
owners = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, text=True, timeout=10)
assert owners.returncode == 1 and not owners.stdout.strip() and not owners.stderr.strip(), owners
before = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager'], text=True, timeout=10)
(RUN / 'journal-before.txt').write_text(before)
assert not FAULT.search(before), 'device fault in current boot'
assert json.loads((EVIDENCE / 'model-verification.json').read_text())['revision'] == '5e6e71018ee1756ed329b697a7b4aedc934dfce9'
assert not (EVIDENCE / 'FAULT.json').exists()
since = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
for key in ['ZE_AFFINITY_MASK', 'ONEAPI_DEVICE_SELECTOR', 'SYCL_DEVICE_FILTER']:
    assert not os.environ.get(key), key
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['OMP_NUM_THREADS'] = '16'
os.environ['MKL_NUM_THREADS'] = '16'
import torch

torch.set_num_threads(16)
assert torch.xpu.device_count() == 4
devices = []
for i in range(4):
    x = torch.ones((1024, 1024), device=f'xpu:{i}')
    assert float((x + 1).sum().cpu()) == 2097152.0
    torch.xpu.synchronize(i)
    devices.append({'ordinal': i, 'properties': str(torch.xpu.get_device_properties(i)), 'copy_compute': 'passed'})
    del x
torch.xpu.set_device(0)
after_preflight = subprocess.check_output(['journalctl', '-k', '-b', '--since', since, '--no-pager'], text=True, timeout=10)
(RUN / 'journal-after-preflight.txt').write_text(after_preflight)
assert not FAULT.search(after_preflight), 'device fault during preflight'
(RUN / 'server-identity.json').write_text(json.dumps({
    'pid': os.getpid(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    'start_utc': since, 'devices': devices, 'torch': torch.__version__,
    'source_commit': subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip(),
    'extension_sha256s': {name: hashlib.sha256((LANE / 'scripts' / name).read_bytes()).hexdigest()
                         for name in ['resident_node.py', 'ltx_layer_shard.py', 'capture_node.py']},
    'launcher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}, indent=2) + '\n')

def watch_journal():
    while True:
        try:
            journal = subprocess.check_output(['journalctl', '-k', '-b', '--since', since, '--no-pager'], text=True, timeout=10)
            if FAULT.search(journal):
                (RUN / 'journal-fault.txt').write_text(journal)
                (EVIDENCE / 'FAULT.json').write_text(json.dumps({'reason': 'kernel device fault', 'time': time.time()}))
                if 'comfy.model_management' in sys.modules:
                    sys.modules['comfy.model_management'].interrupt_current_processing(True)
                print('FAULT: halt all new requests; preserve this process for incident review', flush=True)
                return
        except subprocess.SubprocessError as error:
            (EVIDENCE / 'FAULT.json').write_text(json.dumps({'reason': str(error)}))
            return
        time.sleep(5)

threading.Thread(target=watch_journal, daemon=True).start()
os.chdir(SOURCE)
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(LANE / "scripts"))
sys.argv = [str(SOURCE / 'main.py'), '--listen', '127.0.0.1', '--port', '8188',
            '--disable-auto-launch', '--cache-none', '--deterministic',
            '--disable-async-offload', '--disable-dynamic-vram', '--disable-comfy-compiler',
            '--disable-cuda-graphs', '--disable-pinned-memory',
            '--reserve-vram', '6', '--bf16-unet', '--bf16-text-enc', '--bf16-vae',
            '--use-pytorch-cross-attention', '--disable-xformers',
            '--disable-api-nodes',
            '--extra-model-paths-config', str(LANE / 'data/model-paths.yaml'),
            '--output-directory', str(EVIDENCE / 'output'),
            '--disable-all-custom-nodes', '--whitelist-custom-nodes', 'ltx_baseline_capture', 'ltx_speed_lab']
import comfy.options
comfy.options.enable_args_parsing()
import comfy.model_management
torch.use_deterministic_algorithms(True, warn_only=False)
(RUN / 'server-args.json').write_text(json.dumps(sys.argv, indent=2) + '\n')
runpy.run_path(str(SOURCE / 'main.py'), run_name='__main__')
