"""Coordinator-owned lane-B microbenchmark; --plan is entirely CPU-only."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
WRAPPER = P.parent / 'screen/v4-lanes'
sys.path.insert(0, str(WRAPPER))
from common import M, S, SUPPORT, W, read, require, save, sha, verify_map
from conditions import cpu_gate, lane_gate
from cpu_seal import verify as verify_wrapper
from chain_devices import admit_clients, process_identity, private_home, xe_fds
from devices import topology_admit
from drain_gate import DEFAULT_DRAIN_ROOT, DrainPermit
from lane_admission import Reservation, atomic_json
from screen import unit_gate, unit_conditions
import fault_review

GIB = 1024**3
PCI = '0000:43:00.0'
OUTPUT = P / 'evidence/micro-B'
BINARY = P / 'build/microbench'
BUILD = P / 'evidence/microbench-build.json'
WATCHDOG = 600
MASK = dict(NEOReadDebugKeys='1', FilterBdfPath=PCI, ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',
            ZE_AFFINITY_MASK='0', ONEAPI_DEVICE_SELECTOR='level_zero:0')


def build_gate():
    verify_wrapper()
    verify_map(ROOT, read(P / 'shared-wrapper-pin.json')['sources'])
    row = read(BUILD)
    require(row.get('passed') is True and row.get('device_executed') is False,
            'completed CPU microbenchmark build required')
    verify_map(ROOT, row['sources'])
    verify_map(P, row['artifacts'])
    require(row['artifacts'].get('build/microbench') == sha(BINARY), 'micro binary not bound')
    identity=dict(build_receipt_sha256=sha(BUILD), binary_sha256=sha(BINARY), wrapper_seal_sha256=sha(WRAPPER/'wrapper-seal.json'))
    route=P/'evidence/route-inputs.json'
    if route.is_file() and read(route).get('ready'):
        import route_inputs
        routes=route_inputs.require_ready();identity.update(route_manifest_sha256=sha(route),route_bytes_sha256=routes['route_bytes_sha256'])
    return identity


def storage_admit():
    free = shutil.disk_usage('/').free
    require(free >= 12 * GIB + 64 * 1024**2, 'root free below 12 GiB plus micro log budget')
    return dict(root_free_bytes=free, minimum_root_free_bytes=12 * GIB,
                planned_write_bytes=64 * 1024**2)


def memory_admit():
    row = M.meminfo()
    require(row['MemAvailable'] >= 10 * GIB, 'micro requires 10 GiB available: 8 GiB reserve plus 2 GiB scratch')
    return dict(snapshot=row, required_bytes=10 * GIB, host_reserve_bytes=8 * GIB,
                anonymous_budget_bytes=2 * GIB, device_bytes_upper_bound=2 * GIB)


def fault_latch_gate(boot):
    directories = (WRAPPER, WRAPPER.parent / 'v3', WRAPPER.parent / 'v2',
                   DEFAULT_DRAIN_ROOT, P, P / 'build')
    require(not any(list(root.glob('fault-' + boot + '*.json')) for root in directories)
            and not (WRAPPER.parent / ('fault-' + boot + '.json')).exists(),
            'fault or uncertain owner latch; coordinator recovery required')
    path = P / 'build/FAULT.json'
    require(not path.exists() or read(path).get('boot_id') != boot,
            'packet build fault latch requires coordinator recovery')


def native_summary(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    require(rows and rows[-1].get('kind') == 'summary', 'missing final native summary')
    summary = rows[-1]
    require(summary.get('passed') is True and summary.get('drained') is True
            and summary.get('rows') == 2560 and summary.get('columns') == 640,
            'native microbenchmark failed, wrong shape or drain unproved')
    return summary


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lane', choices=('B',), default='B')
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--fault-review', type=Path)
    ap.add_argument('--authorized-device-window', action='store_true')
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    require(args.plan or args.run, 'choose --plan or --run')
    require(not OUTPUT.exists(), 'fresh micro-B output required; no retry or overwrite')
    if args.plan:
        cpu_gate()
    identity = build_gate()
    command = [str(BINARY), '--coordinator-admitted-device-window', str(P/'evidence/routes.bin')]
    if not args.plan:
        import route_inputs
        routes = route_inputs.require_ready()
        identity['route_manifest_sha256'] = sha(P/'evidence/route-inputs.json')
        identity['route_bytes_sha256'] = routes['route_bytes_sha256']
    if args.plan:
        print(json.dumps(dict(passed=True, device_executed=False, runnable=False, lane='B',
             command=command, identity=identity, physical_cards=[2], native_card=0,
             device_mask=MASK, output=str(OUTPUT), reservation_scope='lane-B',
             drain='shared DrainPermit held across entire autonomous native lifetime',
             required_host_available_bytes=10*GIB, host_reserve_bytes=8*GIB,
             maximum_host_scratch_bytes=2*GIB, device_bytes_upper_bound=2*GIB,
             minimum_root_free_bytes=12*GIB, watchdog_seconds=WATCHDOG, retries=0,
             micro_qualification='pending measured >=15% faster; no engine speed verdict'), indent=2))
        return 0
    lane_gate('B')
    require(args.authorized_device_window and args.fault_review,
            'coordinator authorization and fault review required')
    cgroup = Path('/proc/self/cgroup').read_text()
    unit_gate(cgroup)
    props = unit_conditions(cgroup)
    environment = dict(W.closed_environment(), **MASK)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    fault_latch_gate(boot)
    storage_admit()
    memory_admit()
    review, initial, fresh, cursor = fault_review.validate(args.fault_review)
    reasons, handlers = [], {}
    child = None
    completed = False
    record = dict(schema='own-runtime.packet100.micro-window.v1', passed=False,
                  device_executed=False, drained=False, child_still_running=False,
                  lane='B', physical_cards=[2], native_card=0, pci=PCI, boot_id=boot,
                  identity=identity, **identity, command=command, systemd_cgroup=cgroup,
                  systemd_properties=props, started_utc_ns=time.time_ns(),
                  model_lifetimes=1, watchdog_seconds=WATCHDOG, stop_reasons=reasons)
    OUTPUT.mkdir(parents=True)
    environment = private_home(environment, OUTPUT / 'native-home')
    record['environment'] = environment
    (OUTPUT / 'kernel-boot-before-review.jsonl').write_text(initial)
    (OUTPUT / 'kernel-before.jsonl').write_text(fresh)
    record['coordinator_fault_review'] = review
    latch_path = DEFAULT_DRAIN_ROOT / ('fault-' + boot + '-B.json')

    def persist():
        save(OUTPUT / 'window.json', record)

    def latch(reason):
        save(latch_path, dict(boot_id=boot, output=str(OUTPUT), reason=reason,
                              pid=None if child is None else child.pid))

    def check():
        nonlocal cursor
        require(not reasons and not (P / 'evidence/STOP').exists(), 'micro stopped')
        lines, cursor = S.journal(cursor)
        with (OUTPUT / 'kernel-before.jsonl').open('a') as log:
            log.write(lines)
        require(not fault_review.fault_lines(lines), 'fresh fault during micro admission')

    handlers = {sig: signal.signal(sig, lambda number, frame: reasons.append('coordinator stop ' + str(number)))
                for sig in (signal.SIGINT, signal.SIGTERM)}
    persist()
    try:
        with Reservation('B', window='screen', check=check) as lease:
            with (DEFAULT_DRAIN_ROOT / 'lane-B.lock').open('a') as legacy:
                fcntl.flock(legacy, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with DrainPermit(OUTPUT, check=check, reservation=lease.record) as drain:
                    check()
                    record['device_topology'] = topology_admit('B')
                    require(any(node['pci'] == PCI for node in record['device_topology']['nodes']), 'physical card2 missing')
                    record['clients_before'] = admit_clients('lane-B')
                    record['memory_fence'] = W.memory_fence()
                    record['memory_admission'] = memory_admit()
                    record['storage_admission'] = storage_admit()
                    record['ldd'] = S.ldd_preflight(BINARY, environment)
                    require(build_gate() == identity, 'micro identity changed during admission')
                    fault_review.validate(args.fault_review)
                    check()
                    S.ANONYMOUS_LIMIT_BYTES = 2 * GIB
                    S.ANONYMOUS_STOP_BYTES = 2 * GIB - 64 * 1024**2
                    observed = set()

                    def sensor(pid):
                        sample = SUPPORT.process_tree_anon(pid)
                        if not sample['root_seen'] and SUPPORT._exited_status(Path('/proc'), pid):
                            sample.update(root_seen=True, root_pf_exiting_or_gone=True)
                        require(M.meminfo()['MemAvailable'] >= 8 * GIB, 'host available below 8 GiB reserve')
                        storage_admit()
                        if process_identity(pid) is not None:
                            current = process_identity(pid)
                            require(current is None or current == record['process_start_ticks'], 'micro PID changed')
                            try:
                                fds = xe_fds(pid)
                            except (FileNotFoundError, ProcessLookupError):
                                require(process_identity(pid) is None, 'live micro fdinfo unavailable')
                                fds = []
                            actual = {row['pci'] for row in fds}
                            require(all(row['driver'] == 'xe' for row in fds) and actual <= {PCI},
                                    'micro opened foreign or unidentified device')
                            observed.update(actual)
                            record['device_isolation'] = dict(passed=observed == {PCI}, allowed_pci=[PCI],
                                                              observed_pci=sorted(observed), latest_fds=fds)
                        require(not (P / 'evidence/STOP').exists(), 'packet stop file')
                        return sample

                    persist()
                    with (OUTPUT / 'samples.jsonl').open('x') as samples, (OUTPUT / 'native.stderr.log').open('x') as errorlog, (OUTPUT / 'kernel-window.jsonl').open('x') as kernel:
                        child = subprocess.Popen(command, env=environment, cwd=ROOT,
                                                 stdin=subprocess.DEVNULL, stdout=samples, stderr=errorlog)
                        record.update(pid=child.pid, process_start_ticks=SUPPORT.process_start(child.pid), device_executed=True)
                        persist()
                        record.update(S.supervise(child, WATCHDOG, cursor, kernel, reasons, latch, persist,
                            memory_sensor=sensor, observe_memory=record.update, drain_seconds=90, read_journal=S.journal))
                    if record['child_still_running']:
                        record['child_retained'] = True
                        persist()
                        return 75
                    require(not reasons and child.returncode == 0, 'micro failed or interrupted; no retry')
                    require(record.get('device_isolation', {}).get('passed') is True, 'single-card device ownership unproved')
                    record['native_summary'] = native_summary(OUTPUT / 'samples.jsonl')
                    require(process_identity(child.pid) != record['process_start_ticks'], 'micro still alive')
                    record['clients_after_drain'] = admit_clients('lane-B')
                    check()
                    drain.complete()
                    record.update(drained=True, samples_sha256=sha(OUTPUT / 'samples.jsonl'))
                lease.complete(drained=True)
                record.update(lease_released=True, passed=True, finished_utc_ns=time.time_ns())
                completed = True
                atomic_json(OUTPUT / 'lane-coordination.json', dict(passed=True, reservation=lease.record,
                            clients_after_drain=record['clients_after_drain'], released_before_report=True))
                persist()
        import micro_gate
        micro_gate.evaluate(P)
        return 0
    except Exception as error:
        if completed:
            save(OUTPUT / 'report-failure.json', dict(passed=False, device_failure=False, error=str(error)))
            return 1
        reasons.append(str(error))
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            record.update(child_still_running=True, child_retained=True)
            latch('supervision failed; graceful stop requested; owner retained')
        elif child is not None or fault_review.fault_lines(str(error)):
            latch(str(error))
        persist()
        return 75 if record.get('child_still_running') else 1
    finally:
        for sig, previous in handlers.items():
            signal.signal(sig, previous)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit('REFUSED: ' + str(error))
