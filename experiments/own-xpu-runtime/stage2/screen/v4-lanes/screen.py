#!/usr/bin/env python3
"""Coordinator-only diagnostic screen. --plan is CPU-only and never opens a device."""
import argparse
import fcntl
from lane_admission import Reservation, atomic_json
from chain_devices import process_identity, admit_clients
from drain_gate import DEFAULT_DRAIN_ROOT, screen_teardown_admit
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import fault_review
from devices import masked_environment, topology_admit, mask_for
from conditions import LANES, cpu_gate, lane_gate, selected_clients, teardown_admit

from common import (D, HERE, M, ROOT, S, SUPPORT, W, compare_tokens, label,
                    read, require, save, sealed, sha, summary)

WRITES = {'tp2': 1_100_000_000, 'onecard': 256 * 1024**2}
WATCHDOG = {'tp2': 3600, 'onecard': 7200}


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', choices=('tp2',), default='tp2')
    ap.add_argument('--lane', choices=('A', 'B'), required=True)
    ap.add_argument('--placement', choices=('1-split23', '0-split23', '0', '1'), default='1-split23')
    ap.add_argument('--timing', choices=('token', 'attribution'), default='token')
    ap.add_argument('--pair-dir', type=Path, help=argparse.SUPPRESS)
    ap.add_argument('--lineage', type=Path, required=True)
    for name in ('binary', 'dispatch', 'seal'):
        ap.add_argument('--' + name, type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--fault-review', type=Path)
    ap.add_argument('--authorized-device-window', action='store_true')
    ap.add_argument('--plan', action='store_true')
    return ap


def command(args, identity, manifest):
    return ['/usr/bin/python3', '-B', str(Path(__file__).with_name('tp2_worker.py')),
            '--identity', str(args.output / 'identity.json'), '--output', str(args.output / 'run'),
            '--seconds', str(WATCHDOG[args.profile])] + (
                ['--pair-dir', str(args.pair_dir.resolve())] if args.pair_dir else [])


def memory_admit(profile):
    snapshot = M.meminfo()
    if profile == 'onecard':
        return M.admit(snapshot)
    require(snapshot['MemAvailable'] >= 97 * M.GIB, 'tp2 screen requires 97 GiB available before load')
    return dict(snapshot=snapshot, required_bytes=97 * M.GIB)


def memory_sensor(pid, profile, memory):
    if profile == 'onecard':
        return W.live_memory_sensor(pid, memory['snapshot'].get('GPUActive', 0), budget=memory['plan'])
    sample = SUPPORT.process_tree_anon(pid)
    if not sample['root_seen'] and SUPPORT._exited_status(Path('/proc'), pid):
        sample.update(root_seen=True, root_pf_exiting_or_gone=True)
    host = M.meminfo()
    require(host['MemAvailable'] >= M.HOST_RESERVE, 'host available memory below 8 GiB stop floor')
    sample['host'] = host
    return sample


def unit_gate(text):
    require(any('/user@' in line and line.rsplit('/', 1)[-1].startswith('screen-')
                and line.endswith('.service') for line in text.splitlines()),
            'coordinator-owned screen-* systemd user service required')


def unit_conditions(cgroup):
    unit = next(line.rsplit('/', 1)[-1] for line in cgroup.splitlines()
                if '/user@' in line and line.endswith('.service'))
    names = ('Restart', 'SendSIGKILL', 'KillMode', 'ExitType', 'TimeoutStopUSec')
    result = subprocess.run(['/usr/bin/systemctl', '--user', 'show', unit,
                             *[arg for name in names for arg in ('-p', name)]],
                            capture_output=True, text=True, check=True, timeout=10,
                            env={'PATH': '/usr/bin:/bin', 'XDG_RUNTIME_DIR': '/run/user/' + str(os.getuid())})
    props = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    require(props == dict(Restart='no', SendSIGKILL='no', KillMode='process',
                          ExitType='cgroup', TimeoutStopUSec='infinity'),
            'unit needs Restart=no, SendSIGKILL=no, KillMode=process, ExitType=cgroup, TimeoutStopSec=infinity')
    return props


def pair_barrier(args, identity, reasons):
    pair = args.pair_dir.resolve()
    config = read(pair / 'pair.json')
    require(pair.is_relative_to(HERE / 'evidence') and args.output.parent == pair,
            'pair barrier outside registered output')
    require(config['outputs'][args.lane] == str(args.output), 'unregistered pair output')
    require(config['identities'][args.lane] == identity, 'pair identity changed')
    require(SUPPORT.process_start(config['pid']) == config['process_start_ticks'], 'pair coordinator gone')
    require(config['memory_admission']['required_bytes'] >= 105*M.GIB, 'pair memory admission missing')
    save(pair / (args.lane + '-ready.json'), dict(pid=os.getpid(), identity=identity))
    end = time.monotonic() + 120
    while not (pair / 'GO').exists():
        require(not reasons and not (pair / 'STOP').exists(), 'pair admission stopped')
        require(time.monotonic() < end, 'pair admission timeout')
        require(SUPPORT.process_start(config['pid']) == config['process_start_ticks'], 'pair coordinator gone')
        time.sleep(.1)


def screen_main(argv=None, *, release=None):
    args = parser().parse_args(argv)
    cpu_gate() if args.plan else lane_gate(args.lane)
    args.lineage, args.output = args.lineage.resolve(), args.output.resolve()
    require(args.output.is_relative_to(HERE / 'evidence') and not args.output.exists(), 'new screen evidence output required')
    identity = sealed(args)
    identity.update(lane=args.lane, conditions=LANES[args.lane])
    manifest = D.oracle_inputs()
    require(manifest['prompts'][0]['prompt_id'] == 'incident-retrospective', 'incident must be first')
    cmd = command(args, identity, manifest)
    if args.plan:
        print(json.dumps(dict(evidence_label='screen', device_executed=False, supported=identity['placement']['supported'], identity=identity,
                              command=cmd, model_lifetimes=1, watchdog_seconds=WATCHDOG[args.profile],
                              planned_write_bytes=WRITES[args.profile],
                              physical_cards=LANES[args.lane]['cards'], native_card_arguments=[0, 1],
                              device_mask=mask_for(args.lane), timing=args.timing,
                              reservation_scope='lane-' + args.lane), indent=2))
        return 0 if identity['placement']['supported'] else 2
    require(identity['placement']['supported'], identity['placement']['reason'])
    require(args.authorized_device_window, 'coordinator authorization required')
    require(args.fault_review, '--fault-review receipt required')
    from cpu_seal import verify
    verify()
    screen_teardown_admit(args.lane)
    cgroup = Path('/proc/self/cgroup').read_text()
    unit_gate(cgroup)
    unit_properties = unit_conditions(cgroup)
    env = masked_environment(args.lane)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    latch_path = HERE.parent / 'v3' / ('fault-' + boot + '-' + args.lane + '.json')
    require(not list(HERE.glob('fault-' + boot + '*.json'))
            and not list(DEFAULT_DRAIN_ROOT.glob('fault-' + boot + '*.json'))
            and not list((HERE.parent / 'v3').glob('fault-' + boot + '*.json'))
            and not list((HERE.parent / 'v2').glob('fault-' + boot + '*.json'))
            and not (HERE.parent / ('fault-' + boot + '.json')).exists(),
            'screen fault/uncertain-owner latch; coordinator recovery required')
    # Never clear or change a parent's latch, including a latch from another arm.
    for path in (args.lineage / 'build/FAULT.json', args.lineage / ('fault-' + boot + '.json')):
        if path.exists():
            require(read(path).get('boot_id') != boot, 'lineage fault latch requires coordinator recovery')
    SUPPORT.storage(args.output, WRITES[args.profile])
    memory_admit(args.profile)
    review, boot_log, fresh_log, cursor = fault_review.validate(args.fault_review)
    args.output.mkdir(parents=True)
    save(args.output / 'identity.json', identity)
    save(args.output / 'suite-manifest.snapshot.json', manifest)
    (args.output / 'suite-inputs.tsv').write_text(''.join(
        f"{e['prompt_id']} {(ROOT/e['input_bundle']/'tokens.txt').resolve()}\n" for e in manifest['prompts']))
    record = label(dict(schema='own-runtime.screen.window.v4', window='screen', passed=False,
        device_executed=False, child_still_running=False, profile=args.profile, boot_id=boot,
        lane=args.lane, conditions=LANES[args.lane], timing=args.timing,
        identity=identity, environment=env, coordinator_fault_review=review, systemd_cgroup=cgroup, systemd_properties=unit_properties,
        started_utc_ns=time.time_ns(), model_lifetimes=1, internal_cooldown_seconds=0,
        watchdog_seconds=WATCHDOG[args.profile], stop_reasons=[],
        wrapper_seal_sha256=sha(HERE / 'placement-validation/wrapper-seal.json'),
        wrapper_sources={str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob('*.py')},
        oracle_completion_sha256=sha(D.ORACLE / 'results/completion.json')))
    child, handlers = None, {}
    device_complete = False
    reasons = record['stop_reasons']
    def persist():
        save(args.output / 'window.json', record)
    def latch(reason):
        save(latch_path, dict(boot_id=boot, output=str(args.output), reason=reason,
                              pid=None if child is None else child.pid))
    persist()
    try:
        with (HERE.parent / 'v3' / ('lane-' + args.lane + '.lock')).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record['memory_fence'] = W.memory_fence()
            record['device_topology'] = topology_admit(args.lane)
            record['clients'] = selected_clients(args.lane)
            record['whole_host_isolated'] = False
            record['reservation_scope'] = 'lane-' + args.lane
            review, initial, fresh, cursor = fault_review.validate(args.fault_review)
            (args.output / 'kernel-boot-before-review.jsonl').write_text(initial)
            (args.output / 'kernel-before.jsonl').write_text(fresh)
            record['ldd'] = S.ldd_preflight(Path(identity['binary']), env)
            record['memory_admission'] = memory = memory_admit(args.profile)
            record['memory_fence'] = W.memory_fence()
            record['storage_admission'] = SUPPORT.storage(args.output, WRITES[args.profile])
            record['command'] = cmd
            handlers = {s: signal.signal(s, lambda n, f: reasons.append('coordinator stop ' + str(n)))
                        for s in (signal.SIGTERM, signal.SIGINT)}
            S.ANONYMOUS_LIMIT_BYTES = 8*M.GIB
            S.ANONYMOUS_STOP_BYTES = S.ANONYMOUS_LIMIT_BYTES - 256*1024**2
            def sensor(pid):
                return memory_sensor(pid, args.profile, memory)
            if args.pair_dir:
                pair_barrier(args, identity, reasons)
                # Catch faults during the admission barrier before either launch.
                fresh, cursor = S.journal(cursor)
                require(not fault_review.fault_lines(fresh), 'fault during pair admission')
                with (args.output / 'kernel-before.jsonl').open('a') as before:
                    before.write(fresh)
            require(not reasons, 'stop requested before launch')
            persist()
            with (args.output / 'native.log').open('w') as log, (args.output / 'kernel-window.jsonl').open('w') as kernel:
                child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
                record.update(pid=child.pid, process_start_ticks=SUPPORT.process_start(child.pid), device_executed=True)
                persist()
                record.update(S.supervise(child, WATCHDOG[args.profile], cursor, kernel, reasons, latch, persist,
                                          memory_sensor=sensor, observe_memory=record.update,
                                          drain_seconds=90, read_journal=S.journal))
            if record['child_still_running']:
                record['child_retained'] = True
                persist()
                return 75
            require(not reasons and child.returncode == 0, 'screen failed or interrupted')
            require(release is not None, 'lane release callback required')
            teardown = read(args.output / 'run/teardown.json')
            require(teardown.get('drained') is True, 'screen teardown unproven')
            coordination = release(record)  # postflight and lease release BEFORE aggregation
            device_complete = True
            # The old v3 lock is also a lane admission lock. Release it before
            # CPU reporting so the next lease cannot collide with this reporter.
            fcntl.flock(lock, fcntl.LOCK_UN)
            record.update(device_complete=True, lease_released=True)
            atomic_json(args.output / 'lane-coordination.json', coordination)
            persist()
            proof = read(args.output / 'run/report-inputs.json')
            require(proof.get('passed') is True and proof.get('device_isolation', {}).get('passed') is True,
                    'screen exactness/isolation unproven')
            require(proof['lane'] == args.lane and len(proof['requests']) == 12
                    and proof['incident64'].get('passed') is True
                    and all(r.get('passed') is True and r.get('exact_oracle') is True for r in proof['requests']),
                    'screen quality incomplete')
            result = summary(proof['requests'], proof['incident64'], args.profile)
            result.update(placement=proof['placement'], lane=args.lane, conditions=LANES[args.lane],
                          timing=identity['timing'], device_isolation=proof['device_isolation'])
            save(args.output / 'run/summary.json', result)
            save(args.output / 'summary.json', label(result))
            record.update(passed=True, finished_utc_ns=time.time_ns(),
                          elapsed_seconds=(time.time_ns()-record['started_utc_ns'])/1e9,
                          files={str(p.relative_to(args.output)):sha(p) for p in args.output.rglob('*')
                                 if p.is_file() and p.name not in ('window.json', 'lane-coordination.json')})
            persist()
            return 0
    except Exception as error:
        if device_complete:
            record.update(report_failed=True, report_error=str(error), passed=False)
            save(args.output / 'report-failure.json', dict(passed=False, device_failure=False, error=str(error)))
            persist()
            return 1
        reasons.append(str(error))
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            record.update(child_still_running=True, child_retained=True)
            latch('supervision failed; SIGTERM requested; owner retained')
        elif child is not None or S.FAULT.search(str(error)):
            latch(str(error))
        persist()
        return 75 if record.get('child_still_running') else 1
    finally:
        for s, handler in handlers.items():
            signal.signal(s, handler)



def main(argv=None):
    args = parser().parse_args(argv)
    if args.plan:
        return screen_main(argv)
    lane_gate(args.lane)
    require(args.authorized_device_window and args.fault_review, 'coordinator authorization and review required')
    from cpu_seal import verify
    verify()
    fault_review.validate(args.fault_review)
    _, cursor = S.journal()
    stopped = []
    def check():
        nonlocal cursor
        require(not stopped and not (args.output.parent / 'STOP').exists(), 'coordinator stopped screen')
        fresh, cursor = S.journal(cursor)
        require(not fault_review.fault_lines(fresh), 'fresh fault during lane reservation')
    handlers = {sig: signal.signal(sig, lambda n, f: stopped.append(n))
                for sig in (signal.SIGINT, signal.SIGTERM)}
    lease = Reservation(args.lane, window='screen', check=check)
    lease.record['output'] = str(args.output.resolve())
    try:
        with lease:
            def release(row):
                require(row.get('device_executed') is True and row.get('child_still_running') is False
                        and not row.get('child_retained') and not row.get('stop_reasons'), 'screen not drained')
                require(type(row.get('pid')) is int and type(row.get('process_start_ticks')) is int
                        and process_identity(row['pid']) != row['process_start_ticks'], 'screen worker still alive')
                clients = admit_clients('lane-' + args.lane)
                check()
                lease.complete(drained=True)
                return dict(
                    schema='own-runtime.screen-lane.v4', passed=True, reservation=lease.record,
                    clients_after_drain=clients, released_before_report=True)
            return screen_main(argv, release=release)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit('REFUSED: ' + str(error))
