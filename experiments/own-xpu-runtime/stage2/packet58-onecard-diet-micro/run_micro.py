"""Coordinator-owned lane-B micro window for packet58-onecard-diet-micro (card 2, 0000:43:00.0); --plan is CPU-only.

Structure and guards are packet193's run_micro.py (= packet192's = packet162b's: frozen v4-lanes reservation, drain
permit, fault review, single-card FD census, supervisor, graceful stop); only the binary, its argv, the in-window
gates and the report differ. Exact instruction-diet micro of the ONE-card record gate/up kernel: never a record row,
no model load. packet193's lesson is built in: (1) the device byte-identity gate accepts NaN-payload-order differences
on the NaN-only diagnostic strata (nan_claim rows: is-NaN per word, no status/error byte) and kills only on a value
difference in a claimed stratum; (2) the lane is released (drain.complete + lease.complete) BEFORE the exactness gate
and the report run, so a post-drain failure writes report-failure.json and exits 1 cleanly; a self-owned
active-lane-B marker that survives is archived into the evidence and removed, never latched as a fault.
"""
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
OUTPUT = P / 'evidence/dietmicro-B1'
BINARY = P / 'build/micro-device'
BUILD = P / 'evidence/build.json'
FIXTURES = P / 'build/fixtures'
REAL_ROWS = P.parent / 'packet162-iq2-lookup/build/micro-inputs'
ROUTES = P / 'lineage-inputs/routes-p100b.json'
WATCHDOG = 1800
COLD_REPEATS, WARM_REPEATS, PASSES = 20, 200, 2
CANDIDATES = ['p58-diet']
SCHEMA = 'packet58dm.diet.v1'
PLANNED_WRITE_BYTES = 96 * 1024**2
DEVICE_BYTES_UPPER_BOUND = 1_200_000_000
MASK = dict(NEOReadDebugKeys='1', FilterBdfPath=PCI, ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',
            ZE_AFFINITY_MASK='0', ONEAPI_DEVICE_SELECTOR='level_zero:0')


def native_command():
    return [str(BINARY), '--rank', '0', '--routes', str(ROUTES), '--real-rows', str(REAL_ROWS), '--fixtures', str(FIXTURES),
            '--mode', 'device', '--cold-repeats', str(COLD_REPEATS), '--warm-repeats', str(WARM_REPEATS), '--passes', str(PASSES),
            '--coordinator-admitted-device-window']


def build_gate():
    verify_wrapper()
    row = read(BUILD)
    require(row.get('passed') is True and row.get('device_executed') is False and row.get('warning_lines') == 0, 'clean CPU build required')
    verify_map(ROOT, row['sources'])
    modes = {}
    for r in row['records']:
        verify_map(ROOT, r['closure'])
        require(sha(ROOT / r['path']) == r['sha256'], 'binary changed: ' + r['mode'])
        modes[r['mode']] = r['sha256']
    require(set(modes) == {'gnu-host', 'intel-host', 'device'} and modes['device'] == sha(BINARY), 'three builds required; device binary bound')
    inputs = read(P / 'lineage-inputs/parent-inputs.json')
    for parent in inputs['parents']:
        if 'parent_relpath' in parent:
            require(sha(ROOT / parent['parent_relpath']) == parent['parent_digest'], 'parent input changed: ' + parent['name'])
    require(sha(ROUTES) == inputs['routes_json_sha256'], 'routes json changed')
    fixtures = read(P / 'evidence/fixtures.json')
    require(fixtures.get('passed') is True and fixtures['generator_sha256'] == modes['gnu-host'] and fixtures['verifier_sha256'] == modes['intel-host'], 'fixtures belong to another host twin')
    verify_map(ROOT, fixtures['files'])
    isa = read(P / 'evidence/isa.json')
    require(isa.get('passed') is True and isa.get('device_executed') is False and all(isa['decisions'][c]['kept'] for c in CANDIDATES), 'every candidate must have passed the ISA gate')
    require(isa['source_sha256'] == sha(P / 'micro.cpp'), 'ISA receipt belongs to another source')
    return dict(build_receipt_sha256=sha(BUILD), binary_sha256=sha(BINARY), fixtures_sha256=sha(P / 'evidence/fixtures.json'), isa_sha256=sha(P / 'evidence/isa.json'),
                routes_sha256=sha(ROUTES), parent_inputs_sha256=sha(P / 'lineage-inputs/parent-inputs.json'), wrapper_seal_sha256=sha(WRAPPER / 'wrapper-seal.json'))


def execution_gate():
    ready = read(P / 'READY-FOR-DEVICE.json')
    require(ready.get('ready') is True and ready.get('device_executed') is False, 'preparation is not ready')
    verify_map(ROOT, ready['sources'])
    require(ready['native_command'] == native_command(), 'READY binds another native command')


def storage_admit():
    free = shutil.disk_usage('/').free
    require(free >= 25_000_000_000, 'root free below 25 GB')
    return dict(root_free_bytes=free, minimum_root_free_bytes=25_000_000_000, planned_write_bytes=PLANNED_WRITE_BYTES)


def memory_admit():
    row = M.meminfo()
    require(row['MemAvailable'] >= 10 * GIB, 'micro requires 10 GiB available: 8 GiB reserve plus 2 GiB scratch')
    return dict(snapshot=row, required_bytes=10 * GIB, host_reserve_bytes=8 * GIB,
                anonymous_budget_bytes=2 * GIB, device_bytes_upper_bound=DEVICE_BYTES_UPPER_BOUND)


def fault_latch_gate(boot):
    directories = (WRAPPER, WRAPPER.parent / 'v3', WRAPPER.parent / 'v2', DEFAULT_DRAIN_ROOT, P, P / 'build')
    require(not any(list(root.glob('fault-' + boot + '*.json')) for root in directories)
            and not (WRAPPER.parent / ('fault-' + boot + '.json')).exists(),
            'fault or uncertain owner latch; coordinator recovery required')
    path = P / 'build/FAULT.json'
    require(not path.exists() or read(path).get('boot_id') != boot, 'packet build fault latch requires coordinator recovery')


def native_summary(path):
    """Post-drain evidence gate: stream presence/format and the exactness rows only; timing verdicts are offline.

    Kill rules (packet193's lesson applied): a claimed stratum (exactness_claim) must be byte-equal; a NaN-only
    diagnostic stratum (nan_claim) must be nan_equal (every differing word NaN on both sides, no status/error byte);
    a NaN-payload-order-only difference there is recorded, never a kill.
    """
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    require(rows and rows[-1].get('kind') == 'summary', 'missing final native summary')
    require(all(r.get('kind') in ('start', 'allocation', 'bytes', 'sample', 'summary') for r in rows), 'unknown native stream row')
    require(any(r.get('kind') == 'sample' for r in rows) and any(r.get('kind') == 'bytes' for r in rows), 'native timing/byte stream absent')
    payload_order = []
    for r in rows:
        if r['kind'] == 'sample':
            require(all(type(r.get(k)) is int for k in ('route', 'pass', 'repeat', 'start_ns', 'end_ns', 'event_ns')) and isinstance(r.get('stratum'), str) and r.get('candidate') in CANDIDATES + ['control'] and r.get('arm') in ('production', 'candidate'), 'native event format')
        if r['kind'] == 'bytes':
            require(type(r.get('exactness_claim')) is bool and type(r.get('nan_claim')) is bool and r['exactness_claim'] != r['nan_claim'], 'bytes row claim labels')
            if r['exactness_claim']:
                require(r.get('different_bytes') == 0, 'native byte mismatch in a claimed stratum (value difference): ' + json.dumps(r))
            else:
                require(r.get('nan_equal') is True, 'native value difference or status/error byte in a NaN-only stratum: ' + json.dumps(r))
                if r.get('different_bytes'):
                    payload_order.append(dict(candidate=r['candidate'], stratum=r['stratum'], against=r['against'], nan_vs_nan_words=r['nan_vs_nan_words']))
        if r['kind'] == 'allocation':
            require(r.get('device_peak_bytes', 0) <= DEVICE_BYTES_UPPER_BOUND, 'device allocation above the declared bound')
    summary = rows[-1]
    require(summary.get('passed') is True and summary.get('drained') is True and summary.get('schema') == SCHEMA
            and summary.get('mode') == 'device' and summary.get('route_count') == 384 and summary.get('candidates') == CANDIDATES
            and (summary.get('cold_repeats'), summary.get('warm_repeats'), summary.get('passes')) == (COLD_REPEATS, WARM_REPEATS, PASSES),
            'native micro failed, wrong identity (384 routes, 20/200 repeats, 2 passes, 1 candidate) or drain unproved')
    return dict(summary, nan_payload_order_rows=payload_order)


def report_completed(output):
    # Called only after the shared drain and lane release.
    import s58dm_report
    return s58dm_report.evaluate(output)


def archive_self_marker(token, output):
    """A self-owned lane marker left after the lane was released is archived into the evidence and removed."""
    marker = DEFAULT_DRAIN_ROOT / 'active-lane-B.json'
    if not marker.exists():
        return dict(present=False)
    try:
        owner = json.loads(marker.read_text())
    except (OSError, ValueError):
        return dict(present=True, archived=False, reason='unreadable marker; retained for coordinator review')
    if owner.get('token') != token:
        return dict(present=True, archived=False, reason='marker belongs to another owner; retained')
    archived = output / 'active-lane-B.archived.json'
    shutil.copyfile(marker, archived)
    marker.unlink()
    return dict(present=True, archived=True, archive=str(archived))


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
    require(not OUTPUT.exists(), 'fresh dietmicro-B1 output required; no retry or overwrite')
    if args.plan:
        cpu_gate()
    identity = build_gate()
    command = native_command()
    if args.plan:
        print(json.dumps(dict(passed=True, device_executed=False, runnable=False, lane='B',
             command=command, identity=identity, physical_cards=[2], native_card=0,
             device_mask=MASK, output=str(OUTPUT), reservation_scope='lane-B',
             drain='shared DrainPermit held across entire autonomous native lifetime',
             host_required_available_bytes=10*GIB, host_reserve_bytes=8*GIB,
             maximum_host_scratch_bytes=2*GIB, device_bytes_upper_bound=DEVICE_BYTES_UPPER_BOUND,
             planned_write_bytes=PLANNED_WRITE_BYTES, candidates=CANDIDATES,
             minimum_root_free_bytes=25_000_000_000, watchdog_seconds=WATCHDOG, retries=0,
             micro_qualification='pending: the candidate <= 0.85 x production cold AND warm in both orders after device byte identity on every claimed stratum; diagnostic only; no speed or model-output claim'), indent=2))
        return 0
    execution_gate()
    lane_gate('B')
    require(args.authorized_device_window and args.fault_review, 'coordinator authorization and fault review required')
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
    token = None
    record = dict(schema='own-runtime.packet58dm.micro-window.v1', passed=False,
                  device_executed=False, drained=False, child_still_running=False,
                  lane='B', physical_cards=[2], native_card=0, pci=PCI, boot_id=boot,
                  identity=identity, **identity, command=command, systemd_cgroup=cgroup,
                  systemd_properties=props, started_utc_ns=time.time_ns(),
                  model_lifetimes=0, watchdog_seconds=WATCHDOG, stop_reasons=reasons)
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
        save(latch_path, dict(boot_id=boot, output=str(OUTPUT), reason=reason, pid=None if child is None else child.pid))

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
            token = lease.record['token']
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
                            require(all(row['driver'] == 'xe' for row in fds) and actual <= {PCI}, 'micro opened foreign or unidentified device')
                            observed.update(actual)
                            record['device_isolation'] = dict(passed=observed == {PCI}, allowed_pci=[PCI], observed_pci=sorted(observed), latest_fds=fds)
                        require(not (P / 'evidence/STOP').exists(), 'packet stop file')
                        return sample

                    persist()
                    with (OUTPUT / 'samples.jsonl').open('x') as samples, (OUTPUT / 'native.stderr.log').open('x') as errorlog, (OUTPUT / 'kernel-window.jsonl').open('x') as kernel:
                        child = subprocess.Popen(command, env=environment, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=samples, stderr=errorlog)
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
                    require(process_identity(child.pid) != record['process_start_ticks'], 'micro still alive')
                    record['clients_after_drain'] = admit_clients('lane-B')
                    check()
                    drain.complete()
                    record.update(drained=True, samples_sha256=sha(OUTPUT / 'samples.jsonl'))
                lease.complete(drained=True)
                record.update(lease_released=True, finished_utc_ns=time.time_ns())
                completed = True
                atomic_json(OUTPUT / 'lane-coordination.json', dict(passed=True, reservation=lease.record,
                            clients_after_drain=record['clients_after_drain'], released_before_report=True))
                persist()
    except Exception as error:
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
    # ---- post-drain, lane released: evidence gates and the report; a failure here is a report failure, never a fault ----
    record['marker_after_release'] = archive_self_marker(token, OUTPUT)
    persist()
    try:
        record['native_summary'] = native_summary(OUTPUT / 'samples.jsonl')
        record.update(passed=True)
        persist()
        report_completed(OUTPUT)
        return 0
    except Exception as error:
        record['stop_reasons'] = reasons + ['post-drain: ' + str(error)]
        persist()
        save(OUTPUT / 'report-failure.json', dict(passed=False, device_failure=False, lane_released=completed, error=str(error)))
        return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit('REFUSED: ' + str(error))
