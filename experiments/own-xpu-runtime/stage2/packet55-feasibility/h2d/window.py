#!/usr/bin/env python3
"""Coordinator-only H2D windows; passive admission, inherited graceful supervision."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time

from summarize import summarize
HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
spec = importlib.util.spec_from_file_location('p55_h2d_inherited', PACKET.parent / 'packet54-compute/window_support.py')
SUPPORT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SUPPORT)
S = SUPPORT.SUPERVISION
require, sha, save = S.require, S.sha, S.save
PCI = {2: '0000:43:00.0', 3: '0000:47:00.0'}


def selected_clients(card, proc=Path('/proc')):
    """Reading fdinfo never creates a device context. Other-card clients are recorded."""
    selected, other, inaccessible = [], [], 0
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        try:
            infos = list((pid / 'fdinfo').iterdir())
        except PermissionError:
            inaccessible += 1
            continue
        except FileNotFoundError:
            continue
        for info in infos:
            try:
                fields = dict(line.split(':', 1) for line in info.read_text().splitlines() if ':' in line)
            except PermissionError:
                inaccessible += 1
                continue
            except (FileNotFoundError, ProcessLookupError):
                continue
            if fields.get('drm-driver', '').strip() != 'xe':
                continue
            pci = fields.get('drm-pdev', '').strip()
            row = {'pid': int(pid.name), 'pci': pci, 'fd': info.name}
            (selected if pci == PCI[card] or not pci else other).append(row)
    require(not selected, 'selected card is owned (or Xe client identity unavailable): ' + str(selected))
    return dict(selected_clients=selected, other_card_clients=other,
                inaccessible_entries=inaccessible, hidden_clients_require_coordinator_ownership=True)


def memory_fence(sysroot=Path('/sys/devices/system/memory')):
    states = {str(n): (sysroot / ('memory' + str(n)) / 'state').read_text().strip() for n in range(53, 58)}
    require(all(state == 'offline' for state in states.values()), 'memory fence 53–57 changed')
    return states


def build_gate():
    row = json.loads((HERE / 'build-receipt.json').read_text())
    require(row.get('passed') is True and row.get('device_executed') is False, 'CPU build incomplete')
    require(row['source_sha256'] == sha(HERE / 'stream_bench.cpp'), 'source differs from compiled source')
    require(row['binary_sha256'] == sha(HERE / 'build/stream-bench'), 'binary differs from build receipt')
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card', type=int, choices=(2, 3), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--faults-reviewed-through', required=True)
    parser.add_argument('--authorized-device-window', action='store_true')
    args = parser.parse_args()
    require(args.authorized_device_window, 'coordinator authorization required')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4, 16)) | set(range(20, 32)), 'restricted affinity required')
    cgroup = Path('/proc/self/cgroup').read_text()
    require('packet55-' in cgroup and '.service' in cgroup, 'coordinator-owned packet55-* user unit required')
    env = S.environment_gate()
    env['ONEAPI_DEVICE_SELECTOR'] = 'level_zero:' + str(args.card)
    build = build_gate()
    out = args.output.resolve()
    require(out.is_relative_to((HERE / 'evidence').resolve()) and not out.exists(), 'new output below h2d/evidence required')
    out.mkdir(parents=True)
    reasons, child = [], None
    record = dict(schema='ownrt.packet55.h2d.window.v1', passed=False, device_executed=False,
                  card=args.card, pci_bdf=PCI[args.card], build=build, environment=env,
                  boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  command=None, started_utc_ns=time.time_ns(), stop_reasons=reasons, systemd_cgroup=cgroup)
    def persist():
        save(out / 'window.json', record)
    latch_path = PACKET / ('fault-' + record['boot_id'] + '.json')
    def latch(reason):
        save(latch_path, dict(reason=reason, output=str(out), pid=None if child is None else child.pid))
    persist()
    handlers = {}
    try:
        with (PACKET / 'window.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(not latch_path.exists(), 'packet55 fault latch requires coordinator recovery')
            record['fenced_memory_blocks'] = memory_fence()
            mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
            require(int(mem['MemAvailable'].split()[0]) * 1024 >= 2 * 1024**3, '2 GiB available host headroom required')
            require(shutil.disk_usage(out).free >= 8_000_000_000 + 16 * 1024**2, '8 GB free disk floor required')
            record['clients'] = selected_clients(args.card)
            review, through = S.fault_review(args.faults_reviewed_through, time.time_ns() // 1000)
            record['faults_reviewed_through'] = review
            initial, cursor = S.journal()
            (out / 'kernel-boot-before-review.jsonl').write_text(initial)
            initial, cursor = S.journal(cursor, since_us=through)
            (out / 'kernel-before.jsonl').write_text(initial)
            require(not S.FAULT.search(initial), 'unreviewed GPU fault; coordinator recovery required')
            binary = HERE / 'build/stream-bench'
            record['ldd'] = S.ldd_preflight(binary, env)
            command = [str(binary), '--card', str(args.card), '--output', str(out / 'run'), '--authorized-device-window']
            record['command'] = command
            persist()
            handlers = {sig: signal.signal(sig, lambda signum, frame: reasons.append('coordinator stop ' + str(signum))) for sig in (signal.SIGTERM, signal.SIGINT)}
            with (out / 'native.log').open('w') as log, (out / 'kernel-window.jsonl').open('w') as kernel:
                child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
                record.update(pid=child.pid, process_start_ticks=SUPPORT.process_start(child.pid), device_executed=True)
                persist()
                record.update(S.supervise(child, 600, cursor, kernel, reasons, latch, persist,
                    observe_memory=record.update, memory_sensor=S.process_tree_anon))
            if record['child_still_running']:
                record['child_retained'] = True
                persist()
                return 75
            require(not reasons and child.returncode == 0, 'native window failed or interrupted')
            summary = summarize(out / 'run')
            save(out / 'summary.json', summary)
            record['native_files'] = {name: sha(out / 'run' / name) for name in ('metadata.json', 'receipt.json', 'iterations.jsonl')}
            record.update(passed=True, finished_utc_ns=time.time_ns())
            persist()
            return 0
    except Exception as error:
        reasons.append(str(error))
        if child is not None and child.poll() is None:
            record.update(child_still_running=True, child_retained=True)
            latch('supervision failed; live child retained for coordinator')
        persist()
        return 75 if record.get('child_still_running') else 1
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)

if __name__ == '__main__':
    raise SystemExit(main())
