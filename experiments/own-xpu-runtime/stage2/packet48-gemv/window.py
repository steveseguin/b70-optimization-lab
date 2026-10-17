#!/usr/bin/env python3
"""Coordinator-only card-0 layer windows. Never invoked during preparation."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

import summarize
from window_support import (HERE, SUPERVISION, environment, gpu_clients, host_memory,
                            identity, prerequisite, process_start, require, save,
                            sealed_gate, sha, storage)


def native_files(output):
    names = ('receipt.json', 'comparisons.jsonl', 'iterations.jsonl')
    return {'run/' + name: sha(output / 'run' / name) for name in names}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('exact', 'timing'), required=True)
    parser.add_argument('--card', type=int, choices=(0,), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exactness', nargs=2, type=Path)
    parser.add_argument('--faults-reviewed-through')
    parser.add_argument('--seconds', type=float, default=7200)
    parser.add_argument('--authorized-device-window', action='store_true')
    args = parser.parse_args(argv)
    require(args.authorized_device_window, 'explicit coordinator device-window authorization required')
    require(math.isfinite(args.seconds) and 7200 <= args.seconds <= 14400,
            'bounded watchdog must be 7200..14400 seconds')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'packet48 windows require nice 19')
    allowed = set(range(4, 16)) | set(range(20, 32))
    require(set(os.sched_getaffinity(0)) <= allowed, 'packet48 affinity must stay on cores 4-15,20-31')
    cgroup = Path('/proc/self/cgroup').read_text()
    require('packet48-' in cgroup and '.service' in cgroup,
            'run through the coordinator-owned packet48-* systemd user unit')
    env = environment()
    seal_path = HERE / 'seal.json'
    sealed_gate(seal_path)
    output = args.output.resolve()
    require(output.is_relative_to(HERE / 'evidence') and not output.exists(),
            'new output below packet48/evidence required')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    latch_path = HERE / 'build' / ('fault-' + boot + '.json')
    require(not latch_path.exists(), 'this boot has a retained packet48 fault/uncertain-owner latch')
    review, reviewed_us = SUPERVISION.fault_review(args.faults_reviewed_through, time.time_ns() // 1000)
    record = dict(schema='own-runtime.packet48.window.v1', **identity(seal_path, env, boot),
                  mode=args.mode, passed=False, device_executed=False, child_still_running=False,
                  microbenchmark_only=True, model_speed_claim=False, started_utc_ns=time.time_ns(),
                  watchdog_seconds=args.seconds, cpu_affinity=sorted(os.sched_getaffinity(0)),
                  coordinator_fault_review=review, systemd_cgroup=cgroup)
    if args.mode == 'timing':
        record['exactness_companions'] = prerequisite(args.exactness or [], record)
    else:
        require(args.exactness is None, 'exact mode takes no inherited exactness result')
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
            binary = HERE / 'build/device/bench'
            record['ldd'] = SUPERVISION.ldd_preflight(binary, env)
            command = [str(binary), '--mode', args.mode, '--card', '0',
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
                    reasons, latch, persist, observe_memory=record.update))
            if record['child_still_running']:
                record['child_retained'] = True
                persist()
                return 75
            require(not reasons and child.returncode == 0, 'native failed or window interrupted')
            result = summarize.exact(output / 'run') if args.mode == 'exact' else summarize.timing(output / 'run')
            record['native_files'] = native_files(output)
            if args.mode == 'exact':
                record['exact_output_identity'] = result['exact_output_identity']
            else:
                save(output / 'summary.json', result)
                record['summary_sha256'] = sha(output / 'summary.json')
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


if __name__ == '__main__':
    raise SystemExit(main())
