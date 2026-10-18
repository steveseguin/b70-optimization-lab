#!/usr/bin/env python3
"""Coordinator-only card-0 draft-head windows. Never invoked during preparation."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

import p56_head_summary as summarize
from p56_head_support import (HERE, SUPERVISION, environment, gpu_clients, host_memory,
                            identity, process_start, require, save,
                            sha, storage)


def native_files(output):
    names = ('receipt.json', 'comparisons.jsonl', 'events.jsonl')
    return {'run/' + name: sha(output / 'run' / name) for name in names}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('timing',), default='timing')
    parser.add_argument('--card', type=int, choices=(0,), required=True)
    parser.add_argument('--output', type=Path, required=True)

    parser.add_argument('--faults-reviewed-through')
    parser.add_argument('--seconds', type=float, default=2880)
    parser.add_argument('--authorized-device-window', action='store_true')
    args = parser.parse_args(argv)
    require(args.authorized_device_window, 'explicit coordinator device-window authorization required')
    require(math.isfinite(args.seconds) and args.seconds == 2880,
            'sealed watchdog must be 2880 seconds')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'packet56 windows require nice 19')
    allowed = set(range(4, 16)) | set(range(20, 32))
    require(set(os.sched_getaffinity(0)) <= allowed, 'packet56 affinity must stay on cores 4-15,20-31')
    cgroup = Path('/proc/self/cgroup').read_text()
    require('packet56-' in cgroup and '.service' in cgroup,
            'run through the coordinator-owned packet56-* systemd user unit')
    env = environment()
    from p56_seal import verify
    verify()
    seal_path = HERE / 'build-receipt.json'
    output = args.output.resolve()
    require(output.is_relative_to((HERE / 'evidence').resolve()) and not output.exists(),
            'new output below packet56/evidence required')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    latch_path = HERE / 'build' / ('fault-' + boot + '.json')
    require(not latch_path.exists(), 'this boot has a retained packet56 fault/uncertain-owner latch')
    require(args.faults_reviewed_through is not None, 'past UTC fault-review boundary required')
    review, reviewed_us = SUPERVISION.fault_review(args.faults_reviewed_through, time.time_ns() // 1000)
    record = dict(schema='own-runtime.packet56.window.v1', **identity(seal_path, env, boot),
                  mode=args.mode, passed=False, device_executed=False, child_still_running=False,
                  microbenchmark_only=True, model_speed_claim=False, started_utc_ns=time.time_ns(),
                  watchdog_seconds=args.seconds, cpu_affinity=sorted(os.sched_getaffinity(0)),
                  coordinator_fault_review=review, systemd_cgroup=cgroup)
    record['host_memory'] = host_memory()
    record['storage_admission'] = storage(output)
    record['foreign_clients'] = gpu_clients()
    output.mkdir(parents=True)
    child, reasons = None, []
    record['stop_reasons'] = reasons
    def persist():
        save(output / 'window.json', record)
    def latch(reason):
        if child is not None or SUPERVISION.FAULT.search(reason):
            save(latch_path, dict(boot_id=boot, reason=reason, output=str(output),
                                  pid=None if child is None else child.pid))
    persist()
    previous_signals = {}
    try:
        # The lock is additional packet-local protection. It does not assert
        # that unrelated runtimes participate; passive admission and coordinator
        # ownership remain necessary.
        with (HERE / 'build/device-window.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            initial, cursor = SUPERVISION.journal()
            (output / 'kernel-boot-before-review.txt').write_text(initial)
            if reviewed_us is not None:
                before = [line for stamp, line in SUPERVISION.journal_entries(initial) if stamp <= reviewed_us]
                record['reviewed_fault_lines'] = sum(bool(SUPERVISION.FAULT.search(line)) for line in before)
                initial, cursor = SUPERVISION.journal(cursor, since_us=reviewed_us)
            (output / 'kernel-before.txt').write_text(initial)
            require(not SUPERVISION.FAULT.search(initial), 'unreviewed kernel fault; coordinator recovery/review required')
            binary = HERE / 'build/device/p56-head-fixtures'
            record['ldd'] = SUPERVISION.ldd_preflight(binary, env)
            (output / 'run').mkdir()
            command = [str(binary), '--iterations', '100', '--card', '0',
                       '--output', str(output / 'run'), '--authorized-device-window']
            record['command'] = command
            persist()
            previous_signals = {sig: signal.signal(sig, lambda signum, frame:
                                reasons.append('coordinator stop signal ' + str(signum)))
                                for sig in (signal.SIGTERM, signal.SIGINT)}
            with (output / 'native.log').open('w') as log, (output / 'kernel-window.txt').open('w') as journal:
                # The coordinator's user unit owns the complete process tree;
                # closing this shell never sends a hard-kill to a busy GPU.
                child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
                record.update(pid=child.pid, process_start_ticks=process_start(child.pid), device_executed=True)
                persist()
                record.update(SUPERVISION.supervise(child, args.seconds, cursor, journal,
                    reasons, latch, persist, observe_memory=record.update,
                    memory_sensor=SUPERVISION.process_tree_anon))
            if record['child_still_running']:
                record['child_retained'] = True
                persist()
                return 75
            require(not reasons and child.returncode == 0, 'native failed or window interrupted')
            result = summarize.summarize(output / 'run')
            record['native_files'] = native_files(output)
            record['exact_output_identity'] = result['exact_output_identity']
            save(output / 'summary.json', result)
            record['summary_sha256'] = sha(output / 'summary.json')
            record['kernel_files'] = {name: sha(output/name) for name in ('kernel-before.txt','kernel-window.txt')}
            record['passed'] = True
            record['finished_utc_ns'] = time.time_ns()
            persist()
            return 0
    except Exception as error:
        reasons.append(str(error))
        if child is not None and child.poll() is None:
            record.update(child_still_running=True, child_retained=True)
            latch('supervision failure; live owner retained for coordinator')
        persist()
        return 75 if record.get('child_still_running') else 1
    finally:
        for sig, handler in previous_signals.items():
            signal.signal(sig, handler)


def verify_window(path):
    from p56_seal import verify
    verify()
    path = Path(path).resolve()
    row = json.loads(path.read_text())
    require(row.get('schema') == 'own-runtime.packet56.window.v1' and row.get('passed') is True
            and row.get('device_executed') is True and row.get('child_still_running') is False
            and row.get('returncode') == 0 and not row.get('stop_reasons'), 'incomplete prefix window')
    require(row.get('card') == 0 and row.get('boot_id') == Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'prefix window card/boot identity')
    require(row.get('seal_sha256') == sha(HERE/'build-receipt.json')
            and row.get('binary_sha256') == sha(HERE/'build/device/p56-head-fixtures'), 'prefix window seal/binary changed')
    require(isinstance(row.get('pid'), int) and row['pid'] > 0 and row.get('process_start_ticks'), 'missing fresh owner identity')
    require(row.get('native_files') == native_files(path.parent), 'prefix native evidence changed')
    result = summarize.summarize(path.parent/'run')
    require(row.get('exact_output_identity') == result['exact_output_identity'], 'prefix output identity changed')
    require(sha(path.parent/'summary.json') == row.get('summary_sha256')
            and json.loads((path.parent/'summary.json').read_text()) == result, 'prefix summary changed')
    require(row.get('kernel_files') == {name: sha(path.parent/name) for name in ('kernel-before.txt','kernel-window.txt')}, 'kernel evidence changed')
    for name in ('kernel-before.txt','kernel-window.txt'):
        require(not SUPERVISION.FAULT.search((path.parent/name).read_text()), 'prefix window recorded GPU fault')
    require(not (HERE/'build'/('fault-'+row['boot_id']+'.json')).exists(), 'prefix fault latch exists')
    return row


if __name__ == '__main__':
    raise SystemExit(main())
