#!/usr/bin/env python3
"""One health assessment after user-confirmed reboot; preserve FAULT and runtime holds.

This is not a model launcher or a recovery/reset policy. Native work is limited
to one child, four tiny copy/compute checks and twelve directed peer copies.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import encoder_runtime_common as common
from kernel_fault_detector import matching_lines

LANE = Path(__file__).resolve().parents[1]
ADMISSION = LANE / 'data/external-boot-health-02/admission.json'
ADMISSION_SHA = '131ab0b474d38c7bde4eceb6f64718e4ee1099ff559dc6d849f31f8a3b65e8ab'
OUT = common.ROOT / 'external-boot-health-assessment-02'
HELPER_PINS = {'encoder_runtime_common.py': '81a1ca4476eff3dc733b923b06ed166a5827b71f5ab9296321c5b1a5211ce26a', 'kernel_fault_detector.py': 'e7ff6824f2dbd108bdbdf53fca28ea7a25c58629a17a710273494f3f6f70539e'}
FIELDS = ('__CURSOR', '_BOOT_ID', '__MONOTONIC_TIMESTAMP', '__REALTIME_TIMESTAMP', 'MESSAGE', 'PRIORITY')
LOCKS = ['/run/lock/muse-glimmer-gpu-exclusive.lock', '/tmp/b70-benchmark.lock'] + [f'/tmp/b70-gpu{i}.lock' for i in range(4)]


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def identity():
    for name, digest in HELPER_PINS.items():
        require(common.sha(Path(__file__).parent / name) == digest, 'Health helper source changed: ' + name)
    require(common.sha(ADMISSION) == ADMISSION_SHA, 'Incident admission changed')
    a = json.loads(ADMISSION.read_text())
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == a['boot_id'], 'Boot changed')
    require(common.sha(common.ROOT / 'FAULT.json') == a['fault_sha256'], 'Fault latch changed')
    common.verify_runtime(a['runtime'])
    require(not any(os.environ.get(k) for k in ('ZE_AFFINITY_MASK', 'ONEAPI_DEVICE_SELECTOR', 'SYCL_DEVICE_FILTER')), 'Unexpected device filter')
    return a


def new_fault(record):
    message = record['MESSAGE']
    return bool(matching_lines(message) or int(record['PRIORITY']) <= 3 or any(
        term in message.lower() for term in ('invoked oom-killer', 'oom-kill:', 'out of memory: killed process')))


def check_journal_records(records, a):
    count = a['journal_prefix_count']
    require(len(records) >= count and canonical_sha(records[:count]) == a['journal_prefix_sha256'], 'Historical kernel prefix changed or was lost')
    require(all(r['_BOOT_ID'] == a['boot_id'].replace('-', '') for r in records), 'Mixed kernel boot identity')
    faults = [r for r in records[count:] if new_fault(r)]
    require(not faults, 'New kernel fault/error: ' + repr(faults[:3]))
    return {'historical_prefix_matches': True, 'historical_records': count,
            'new_records': len(records) - count, 'new_faults': faults,
            'last_cursor': records[-1]['__CURSOR']}


def journal(a, destination=None):
    raw = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager', '-o', 'json'], text=True, timeout=10)
    if destination is not None:
        with destination.open('x') as stream:
            stream.write(raw)
    records = [{k: r[k] for k in FIELDS} for r in map(json.loads, raw.splitlines())]
    return check_journal_records(records, a)


def passive(a, prefix=None):
    require(not any(Path(f'/proc/{pid}').exists() for pid in a['retired_pids']), 'Incident process still exists')
    render = sorted(Path('/dev/dri').glob('renderD*'))
    mapping = {p.name: str(p.resolve()) for p in sorted(Path('/dev/dri/by-path').glob('*-render'))}
    require(len(render) == 4 and mapping == a['render_mapping'], 'Render topology changed')
    owners = subprocess.run(['fuser', *map(str, render)], capture_output=True, text=True, timeout=10)
    require(owners.returncode == 1 and not owners.stdout.strip() and not owners.stderr.strip(), 'Render ownership is not clear')
    require(not subprocess.check_output(['docker', 'ps', '-q'], text=True, timeout=10).strip(), 'Running container')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 8188))
    raw_memory = Path('/proc/meminfo').read_text()
    memory = {line.split(':')[0]: int(line.split()[1]) for line in raw_memory.splitlines()}
    require(memory['MemAvailable'] >= 16 * 1024**2, 'Less than 16GiB RAM available')
    quiet = time.clock_gettime(time.CLOCK_MONOTONIC) - a['journal_last_monotonic_us'] / 1e6
    require(quiet >= a['minimum_quiet_seconds'], 'Quiet interval incomplete')
    return {'render_mapping': mapping, 'render_nodes_unowned': True, 'no_running_containers': True,
            'port_8188_unbound': True, 'incident_processes_absent': True,
            'quiet_since_historical_kernel_tail_seconds': quiet, 'meminfo': raw_memory,
            'journal': journal(a, OUT / (prefix + '-journal.jsonl') if prefix else None)}


def worker(parent_pid, lock_fds):
    require(os.getppid() == parent_pid and parent_pid > 1, 'Missing supervising parent')
    require(len(lock_fds) == len(LOCKS), 'Missing inherited exclusive locks')
    for fd, path in zip(lock_fds, LOCKS):
        require(os.fstat(fd).st_ino == os.stat(path).st_ino and os.fstat(fd).st_dev == os.stat(path).st_dev, 'Wrong inherited lock')
    a = identity()
    parent = json.loads((OUT / 'started.json').read_text())
    require(parent['pid'] == parent_pid and parent['boot_id'] == a['boot_id'] and
            parent['admission_sha256'] == ADMISSION_SHA and
            parent['source_sha256'] == common.sha(Path(__file__)), 'Parent/source admission mismatch')
    write(OUT / 'worker-started.json', {'pid': os.getpid(), 'parent_pid': parent_pid,
          'admission_sha256': ADMISSION_SHA, 'source_sha256': parent['source_sha256'],
          'helper_sha256s': HELPER_PINS, 'native_imports_started': False})
    report = {'status': 'running', 'pid': os.getpid(), 'devices': [], 'peer_copies': [],
              'model_loaded': False, 'fault_latch_removed': False}
    try:
        journal(a, OUT / 'worker-before-journal.jsonl')
        import torch
        require(torch.__version__ == a['runtime']['torch'], 'Torch import changed')
        torch.set_num_threads(16)
        torch.use_deterministic_algorithms(True, warn_only=False)
        require(torch.xpu.device_count() == 4, 'Expected four XPU devices')
        for i in range(4):
            identity()
            journal(a, OUT / f'card-{i}-before-journal.jsonl')
            properties = str(torch.xpu.get_device_properties(i))
            require(properties == a['expected_devices'][i]['properties'], 'Ordinal device UUID/properties changed')
            value = torch.ones((1024, 1024), device=f'xpu:{i}', dtype=torch.float32)
            require(float((value + 1).sum().cpu()) == 2097152.0, 'Copy/compute mismatch')
            torch.xpu.synchronize(i)
            report['devices'].append({'ordinal': i, 'properties': properties, 'copy_compute': 'passed'})
            del value
            print(f'Card {i}: copy/compute passed', flush=True)
        # Explicit fixed BF16 transfer set, one source at a time, no collective
        # library or claim about the driver's physical transport implementation.
        for source in range(4):
            identity()
            journal(a, OUT / f'peer-source-{source}-before-journal.jsonl')
            value = torch.full((256, 256), source + 1, dtype=torch.bfloat16, device=f'xpu:{source}')
            for target in range(4):
                if source == target:
                    continue
                identity()
                journal(a, OUT / f'peer-{source}-{target}-before-journal.jsonl')
                copied = value.to(f'xpu:{target}')
                require(bool(torch.all(copied.cpu() == source + 1)), 'Peer copy mismatch')
                torch.xpu.synchronize(target)
                report['peer_copies'].append({'source': source, 'target': target, 'dtype': 'bfloat16', 'bytes': 131072, 'exact': True})
                del copied
            del value
        journal(a, OUT / 'worker-after-journal.jsonl')
        identity()
        report.update(status='passed', strict_determinism=torch.are_deterministic_algorithms_enabled(),
                      warn_only=torch.is_deterministic_algorithms_warn_only_enabled())
        require(report['strict_determinism'] and not report['warn_only'], 'Determinism changed')
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        write(OUT / 'worker-result.json', report)


def main(check_only=False):
    a = identity()
    require(not OUT.exists() and not OUT.is_symlink(), 'One-use diagnostic output already exists')
    if check_only:
        print(json.dumps({'status': 'passive-check-only-passed', 'passive': passive(a), 'native_work': False}))
        return
    handles = []
    report = {'status': 'started', 'pid': os.getpid(), 'boot_id': a['boot_id'],
              'admission_sha256': ADMISSION_SHA, 'source_sha256': common.sha(Path(__file__)),
              'helper_sha256s': HELPER_PINS,
              'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'fault_latch_removed': False, 'model_admission': False, 'native_children': 0,
              'reboot_reset_restart_settings_actions': False}
    child = None
    OUT.mkdir(exist_ok=False)
    try:
        for path in LOCKS:
            handle = open(path, 'a')
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            handles.append(handle)
        report['preflight'] = passive(a, 'parent-before')
        identity()
        write(OUT / 'started.json', report)
        fds = [h.fileno() for h in handles]
        command = [sys.executable, '-B', str(Path(__file__).resolve()), '--worker', str(os.getpid()), *map(str, fds)]
        with (OUT / 'worker.log').open('x') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, pass_fds=fds)
            report.update(native_children=1, worker_pid=child.pid)
            try:
                code = child.wait(timeout=a['native_worker_timeout_seconds'])
            except subprocess.TimeoutExpired:
                report['worker_timeout'] = True
                child.send_signal(signal.SIGINT)
                report['one_graceful_interrupt_sent'] = True
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    report['worker_still_alive'] = True
                raise RuntimeError('Health worker exceeded bound; no retry or recovery action')
        report['worker_exit_code'] = code
        require(code == 0, 'Health worker failed')
        result = json.loads((OUT / 'worker-result.json').read_text())
        require(result['status'] == 'passed' and len(result['devices']) == 4 and len(result['peer_copies']) == 12, 'Incomplete health result')
        report['status'] = 'limited-health-assessment-passed'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        if child is not None and child.poll() is None and not report.get('one_graceful_interrupt_sent'):
            child.send_signal(signal.SIGINT)
            report['one_graceful_interrupt_sent'] = True
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                report['worker_still_alive'] = True
        raise
    finally:
        try:
            identity()
            report['postflight'] = passive(a, 'parent-after')
        except BaseException as error:
            report.update(status='failed', postflight_error=repr(error))
        report['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write(OUT / 'result.json', report)
        for handle in reversed(handles):
            handle.close()
    require(report['status'] == 'limited-health-assessment-passed', 'Postflight failed')
    print(json.dumps({'status': report['status'], 'result': str(OUT / 'result.json'), 'model_admission': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--worker', type=int, nargs='+')
    args = parser.parse_args()
    require(not (args.check_only and args.worker), 'Choose one operation')
    if args.worker:
        worker(args.worker[0], args.worker[1:])
    else:
        main(args.check_only)
