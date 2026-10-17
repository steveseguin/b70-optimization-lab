#!/usr/bin/env python3
"""Concurrent X/A vs Y/B, then X/B vs Y/A. Coordinator device windows only."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import statistics
import subprocess
import time
from types import SimpleNamespace

from common import D, HERE, M, SUPPORT, W, label, read, require, save, sealed, sha
from conditions import CPU_CORES, LANES, cpu_gate, selected_clients, teardown_admit
import fault_review
import screen

RATE = 'tok_s_1_100_intervals_after_ttft'


def candidate(args, role):
    lineage = getattr(args, role).resolve()
    return sealed(SimpleNamespace(lineage=lineage, profile='tp2',
        timing=getattr(args, role + '_timing'),
        binary=getattr(args, role + '_binary'), dispatch=getattr(args, role + '_dispatch'),
        seal=getattr(args, role + '_seal')))


def orders():
    return ({'A': 'x', 'B': 'y'}, {'A': 'y', 'B': 'x'})


def lane_identity(identity, lane):
    return dict(identity, lane=lane, conditions=LANES[lane])


def lane_command(identity, lane, output, review, pair):
    return ['/usr/bin/taskset', '-c', LANES[lane]['affinity'], '/usr/bin/python3', '-B',
            str(HERE / 'screen.py'), '--lane', lane, '--lineage', identity['lineage'],
            '--binary', identity['binary'], '--dispatch', identity['dispatch'], '--seal', identity['seal'],
            '--timing', identity['timing'], '--output', str(output), '--fault-review', str(review),
            '--pair-dir', str(pair), '--authorized-device-window']


def checked_rows(summary):
    require(summary.get('passed') is True and summary.get('incident64', {}).get('passed') is True,
            'paired report requires incident and exactness pass')
    rows = summary.get('requests', [])
    require([r['prompt_id'] for r in rows] == list(D.CHECK.PROMPT_IDS), 'need all 12 ordered prompts')
    for row in rows:
        pid = row['prompt_id']
        require(row.get('passed') is True and row.get('exact_oracle') is True, 'request not exact')
        require(row['prompt_class'] == D.METRICS.PROMPT_CLASSES[pid], 'class mismatch')
        expected = D.CHECK.token_record(D.ORACLE / 'results' / pid)
        require(row['tokens'] == expected[:128] and len(row['tokens']) == 128, '128-token oracle mismatch')
        require(type(row[RATE]) in (int, float) and math.isfinite(row[RATE]) and row[RATE] > 0,
                'invalid paired rate')
    return {r['prompt_id']: r for r in rows}


def difference(x, y):
    return dict(candidate_tok_s=x, control_tok_s=y, difference_tok_s=x-y, difference_percent=100*(x/y-1))


def paired_report(summaries):
    order_rows = []
    for index, assignment in enumerate(orders()):
        lanes = {role: lane for lane, role in assignment.items()}
        x = checked_rows(summaries[index][lanes['x']])
        y = checked_rows(summaries[index][lanes['y']])
        prompts = {pid: difference(x[pid][RATE], y[pid][RATE]) for pid in x}
        classes = {}
        for cls in sorted(set(D.METRICS.PROMPT_CLASSES.values())):
            ids = [pid for pid in x if x[pid]['prompt_class'] == cls]
            row = difference(statistics.median(x[pid][RATE] for pid in ids),
                             statistics.median(y[pid][RATE] for pid in ids))
            row['median_prompt_paired_difference_tok_s'] = statistics.median(prompts[pid]['difference_tok_s'] for pid in ids)
            classes[cls] = row
        overall = difference(statistics.median(r['candidate_tok_s'] for r in classes.values()),
                             statistics.median(r['control_tok_s'] for r in classes.values()))
        order_rows.append(dict(order=index+1, candidate_lane=lanes['x'], control_lane=lanes['y'],
                               per_prompt=prompts, per_class=classes, overall=overall))
    # Averaging both directional differences cancels a fixed additive lane bias;
    # geometric paired ratios cancel a fixed multiplicative lane bias.
    def combine(rows):
        return dict(mean_paired_difference_tok_s=statistics.mean(r['difference_tok_s'] for r in rows),
                    geometric_paired_difference_percent=100*(math.sqrt(
                        math.prod(r['candidate_tok_s']/r['control_tok_s'] for r in rows))-1),
                    ordering_differences_percent=[r['difference_percent'] for r in rows])
    return label(dict(schema='own-runtime.screen.ab.v3', passed=True, orders=order_rows,
        per_class={cls: combine([r['per_class'][cls] for r in order_rows]) for cls in order_rows[0]['per_class']},
        overall=combine([r['overall'] for r in order_rows]),
        metric='99 intervals, events 1–100; per-class medians then median across classes',
        uncertainty='One crossover is screening evidence; 1–2% differences need repeated fresh crossovers.'))


def run_pair(pair, assignment, identities, review, env, stopped):
    require(not stopped, 'stop before ordering')
    teardown_admit()
    selected_clients('A'); selected_clients('B')
    fault_review.validate(review)
    snapshot = M.meminfo()
    # Same immutable mapped model inputs are shared; reserve another full 8 GiB
    # anonymous envelope in addition to the inherited 97 GiB single-pair floor.
    require(snapshot['MemAvailable'] >= 105*M.GIB, 'concurrent pair needs 105 GiB available')
    SUPPORT.storage(pair, 2*screen.WRITES['tp2'])
    pair.mkdir()
    outputs = {lane: pair / (lane + '-' + role) for lane, role in assignment.items()}
    actual = {lane: lane_identity(identities[role], lane) for lane, role in assignment.items()}
    save(pair / 'pair.json', dict(pid=os.getpid(), process_start_ticks=SUPPORT.process_start(os.getpid()),
        assignments=assignment, outputs={k:str(v) for k,v in outputs.items()}, identities=actual,
        memory_admission=dict(snapshot=snapshot, required_bytes=105*M.GIB),
        teardown_gap_seconds=60))
    children, logs, signalled = {}, [], set()
    def stop_all():
        (pair / 'STOP').touch()
        for lane, child in children.items():
            if child.poll() is None and lane not in signalled:
                child.send_signal(signal.SIGTERM); signalled.add(lane)
    try:
        for lane in ('A', 'B'):
            require(not stopped, 'stop during launch')
            log = (pair / (lane + '.log')).open('w'); logs.append(log)
            cmd = lane_command(actual[lane], lane, outputs[lane], review, pair)
            children[lane] = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
        end = time.monotonic() + 120
        while not all((pair / (lane + '-ready.json')).exists() for lane in children):
            require(not stopped, 'coordinator stop during admission')
            require(all(p.poll() is None for p in children.values()), 'lane refused admission')
            require(time.monotonic() < end, 'pair admission timeout')
            time.sleep(.1)
        fault_review.validate(review)
        require(not stopped, 'stop before concurrent release')
        (pair / 'GO').touch()
        while any(p.poll() is None for p in children.values()):
            if stopped or any(p.poll() not in (None, 0) for p in children.values()):
                stop_all()
            time.sleep(.25)
        require(not stopped and all(p.returncode == 0 for p in children.values()), 'pair failed; no next ordering')
        drains = sorted((read(out / 'run/teardown.json') for out in outputs.values()),
                        key=lambda r:r['started_monotonic'])
        require(all(r['drained'] for r in drains) and
                drains[1]['started_monotonic'] - drains[0]['completed_monotonic'] >= 60,
                'teardown spacing failed')
        fault_review.validate(review)
        return {lane: read(out / 'summary.json') for lane, out in outputs.items()}
    except BaseException:
        stop_all()
        # Never kill; lane wrappers retain uncertain owners in the coordinator unit.
        end = time.monotonic() + 180
        while any(p.poll() is None for p in children.values()) and time.monotonic() < end:
            time.sleep(.25)
        raise
    finally:
        for log in logs:
            log.close()


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    for role in ('x', 'y'):
        ap.add_argument('--' + role, type=Path, required=True)
        ap.add_argument('--' + role + '-timing', choices=('token', 'attribution'), default='token')
        for name in ('binary', 'dispatch', 'seal'):
            ap.add_argument('--' + role + '-' + name, type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--fault-review', type=Path)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--authorized-device-window', action='store_true')
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    if args.plan:
        cpu_gate()
    else:
        require(os.getpriority(os.PRIO_PROCESS, 0) == 0, 'coordinator must start at nice0; cannot elevate nice19')
        require(set(os.sched_getaffinity(0)) <= CPU_CORES, 'A/B supervisor uses cores8-15,24-31')
    identities = {role:candidate(args, role) for role in ('x', 'y')}
    D.oracle_inputs()
    args.output = args.output.resolve()
    require(args.output.is_relative_to(HERE / 'evidence') and not args.output.exists(), 'fresh v3 output required')
    if args.plan:
        print(json.dumps(dict(device_executed=False, identities=identities, orderings=orders(), lanes=LANES,
            expected_seconds=[480,600], expected_duration_is_estimate=True, teardown_gap_seconds=60,
            commands=[{lane:lane_command(lane_identity(identities[role],lane),lane,
                args.output / str(index+1) / (lane+'-'+role), args.fault_review or Path('REVIEW.json'),
                args.output / str(index+1)) for lane,role in order.items()} for index,order in enumerate(orders())]), indent=2))
        return 0
    require(args.authorized_device_window and args.fault_review, 'coordinator authorization and fault receipt required')
    from cpu_seal import verify
    verify()
    cgroup = Path('/proc/self/cgroup').read_text()
    screen.unit_gate(cgroup)
    screen.unit_conditions(cgroup)
    env = W.closed_environment()
    args.fault_review = args.fault_review.resolve()
    fault_review.validate(args.fault_review)
    # Retain both orderings' output, not just the peak concurrent allocation.
    SUPPORT.storage(args.output, 4*screen.WRITES['tp2'])
    args.output.mkdir()
    stopped = []
    handlers = {s:signal.signal(s, lambda n,f:stopped.append(n)) for s in (signal.SIGINT,signal.SIGTERM)}
    record = label(dict(passed=False, device_executed=False, identities=identities, orderings=orders()))
    try:
        with (HERE / 'ab.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
            summaries = []
            for index, assignment in enumerate(orders()):
                save(args.output / 'window.json', record)
                summaries.append(run_pair(args.output / str(index+1), assignment, identities, args.fault_review, env, stopped))
            report = paired_report(summaries)
            report['identities'] = identities
            save(args.output / 'comparison.json', report)
            record.update(passed=True, comparison_sha256=sha(args.output / 'comparison.json'))
            print(json.dumps(dict(overall=report['overall'], per_class=report['per_class'],
                                  comparison=str(args.output / 'comparison.json')), indent=2))
    except Exception as error:
        record['error'] = str(error)
    finally:
        record['device_executed'] = any(read(p).get('device_executed') is True
            for p in args.output.glob('[12]/*/window.json'))
        save(args.output / 'window.json', record)
        for s, handler in handlers.items():signal.signal(s, handler)
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit('REFUSED: ' + str(error))
