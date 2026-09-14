#!/usr/bin/env python3
"""One bounded recovery diagnostic for the recorded external boot; no recovery actions."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from kernel_fault_detector import matching_lines

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
BOOT = '8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a'
OLD_BOOT = '39a36df1-8b22-498e-b74a-28384839a024'
OLD_FAULT_SHA = '8d2beb84936424bcab87b81ad685efd0c57635db9bf321878731d0478c6ce305'
OUT = ROOT / 'external-boot-recovery-01'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def check_identity():
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT != OLD_BOOT,
            'Not the explicitly reviewed new boot')
    require(hashlib.sha256((ROOT / 'FAULT.json').read_bytes()).hexdigest() == OLD_FAULT_SHA,
            'Historical fault changed; stop recovery diagnostic')


def journal(name):
    value = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager'], text=True, timeout=10)
    (OUT / name).write_text(value)
    matches = matching_lines(value)
    require(not matches, 'Current boot has kernel/device fault: ' + repr(matches[:3]))


def main():
    check_identity()
    OUT.mkdir(exist_ok=False)
    report = {'schema': 'ltx25.external-boot-recovery-diagnostic.v1', 'status': 'running',
              'boot_id': BOOT, 'historical_boot_id': OLD_BOOT, 'historical_fault_sha256': OLD_FAULT_SHA,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'reboot_performed_by_this_agent': False, 'fault_latch_removed': False,
              'device_results': [], 'model_loaded': False}
    locks = []
    try:
        for path in ['/run/lock/muse-glimmer-gpu-exclusive.lock', '/tmp/b70-benchmark.lock'] + [
                f'/tmp/b70-gpu{i}.lock' for i in range(4)]:
            handle = open(path, 'a')
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locks.append(handle)
        require(not subprocess.check_output(['docker', 'ps', '-q'], text=True, timeout=10).strip(),
                'A container is running')
        render = sorted(Path('/dev/dri').glob('renderD*'))
        require(len(render) == 4, 'Expected four render nodes')
        owners = subprocess.run(['fuser', *map(str, render)], capture_output=True, text=True, timeout=10)
        require(owners.returncode == 1 and not owners.stdout.strip() and not owners.stderr.strip(),
                'Render ownership is not clear')
        for pid in (95931, 96119, 102144):
            require(not Path(f'/proc/{pid}').exists(), 'Historical PID exists; inspect identity first')
        memory = {line.split(':')[0]: int(line.split()[1])
                  for line in Path('/proc/meminfo').read_text().splitlines()}
        require(memory['MemAvailable'] >= 16 * 1024**2, 'Insufficient host memory')
        report['mem_available_kib_before'] = memory['MemAvailable']
        report['render_mapping'] = {p.name: str(p.resolve()) for p in Path('/dev/dri/by-path').glob('*-render')}
        journal('journal-before.txt')
        check_identity()
        for key in ('ZE_AFFINITY_MASK', 'ONEAPI_DEVICE_SELECTOR', 'SYCL_DEVICE_FILTER'):
            require(not os.environ.get(key), 'Unexpected device filter ' + key)
        print('Passive recovery checks passed; beginning one four-card copy/compute diagnostic', flush=True)
        import torch
        report['torch'] = str(torch.__version__)
        require(torch.__version__ == '2.14.0+xpu', 'Unexpected Torch version')
        torch.set_num_threads(16)
        torch.use_deterministic_algorithms(True, warn_only=False)
        require(torch.xpu.device_count() == 4, 'Expected four XPU devices')
        for i in range(4):
            check_identity()
            journal(f'journal-before-card-{i}.txt')
            value = torch.ones((1024, 1024), device=f'xpu:{i}')
            require(float((value + 1).sum().cpu()) == 2097152.0, 'Copy/compute mismatch')
            torch.xpu.synchronize(i)
            report['device_results'].append({'ordinal': i, 'properties': str(torch.xpu.get_device_properties(i)),
                                             'copy_compute': 'passed'})
            del value
            print(f'Card {i}: copy/compute passed', flush=True)
        journal('journal-after-compute.txt')
        check_identity()
        report['status'] = 'four-card-recovery-diagnostic-passed'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        report['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        for handle in reversed(locks):
            handle.close()
    print(json.dumps({'status': report['status'], 'result': str(OUT / 'result.json')}), flush=True)


if __name__ == '__main__':
    main()
