#!/usr/bin/env python3
"""Read-only time accounting for the hourly efficiency review.

Reconstructs per-lane and combined evidenced device occupancy from live device
children and receipts over the last N hours. Journals and queue events supply
attribution, never busy time. Admission waits count as idle. It also
lists idle gaps, Codex activity, recent commits and the record floor.
It never launches, stops or edits anything.

Usage: python3 -B gpu_time_review.py [--hours 6]
"""
import argparse
import datetime as dt
import glob
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from compile_turn import process_table, device_descendants

# Units that hold or wait for GPUs: device windows, chains and drivers.
DEVICE = re.compile(r'^(packet\d+\S*|p\d+\S*|screen\S*)\.service$')  # p61x-chain etc. (review 3 fix)
# Unit lifetimes supply attribution only, never device occupancy.
WAITERS = re.compile(r'^(p58-after-p57\S*)\.service$')
LINE = re.compile(r'^(\S+) \S+ systemd\[\d+\]: (?:Started (\S+\.service)|(\S+\.service): (Deactivated successfully|Failed with result.*|Consumed .*))')
SCRATCH = '/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad'
REPO = '/home/steve/llm-optimizations'
OPS = Path(__file__).resolve().parent
CHAIN = re.compile(r'^(?:packet|p)\d+.*-chain(?:[.-]|$)')
RESULTS = Path('/home/steve/own-xpu-runtime-results')
PROC = Path('/proc')


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(dt.timezone.utc)


def active(unit):
    try:
        return subprocess.run(['systemctl', '--user', 'is-active', unit],
                              capture_output=True, text=True, timeout=10).stdout.strip() == 'active'
    except (OSError, subprocess.TimeoutExpired):
        return False


def read_json(path):
    try:
        with open(path) as stream:
            row = json.load(stream)
        return row if isinstance(row, dict) else {}
    except (OSError, ValueError):
        return {}


def queue_events(now, notes):
    """Use durable START/terminal events for attribution, never occupancy."""
    starts, intervals, lanes = {}, [], {}
    for lane in ('A', 'B'):
        path = OPS / 'lane-queue' / f'events-{lane}.jsonl'
        try:
            lines = path.read_text().splitlines()
        except OSError:
            notes.add(f'Lane {lane}: queue events unavailable; using journal evidence.')
            continue
        for line in lines:
            try:
                row = json.loads(line)
                if row.get('lane') != lane or not row.get('name'):
                    continue
                unit = 'screen-' + row['name'] + '.service'
                stamp = timestamp(row['utc'])
                kind = row['event']
                lanes[unit] = lane
                if kind == 'START':
                    starts[unit] = stamp
                elif kind in ('DONE', 'REFUSED-fast', 'FAILED', 'FAILED-status',
                              'FAILED-postflight', 'REPORT-FAILED') and unit in starts:
                    intervals.append((starts.pop(unit), stamp, unit, kind))
            except (ValueError, KeyError, TypeError, AttributeError):
                notes.add(f'Lane {lane}: malformed queue event skipped.')
    for unit, start in starts.items():
        if active(unit):
            intervals.append((start, now, unit, 'still active'))
        else:
            notes.add(f'{unit}: unfinished queue event; active state unconfirmed, end unknown.')
    return intervals, lanes


def unit_lane(unit, evidence):
    if unit in evidence:
        return evidence[unit]
    if CHAIN.match(unit) or unit.startswith('packet58-onecard-'):
        return 'A'
    # Transient units may already have been collected. Query only the affinity,
    # never Environment/ExecStart (which could expose secrets).
    try:
        result = subprocess.run(['systemctl', '--user', 'show', unit,
                                 '--property=CPUAffinity', '--value'],
                                capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    cpus = set()
    try:
        for part in re.split(r'[ ,]+', result.stdout.strip()):
            if not part:
                continue
            bounds = [int(n) for n in part.split('-')]
            if len(bounds) == 1:
                cpus.add(bounds[0])
            elif len(bounds) == 2 and 0 <= bounds[0] <= bounds[1] < 4096:
                cpus.update(range(bounds[0], bounds[1] + 1))
            else:
                return None
    except ValueError:
        return None
    for lane, expected in (('A', set(range(4)) | set(range(16, 20))),
                           ('B', set(range(4, 8)) | set(range(20, 24)))):
        if cpus == expected:
            return lane
    return None


def receipt_paths():
    """Only runtime evidence trees, including externalized packet builds."""
    paths = set()
    for root in (OPS.parent / 'stage2', RESULTS):
        for pattern in ('packet*/build/device*/*/window.json',
                        'packet*/evidence/**/window.json',
                        'packet*/v*/evidence/**/window.json',
                        'screen/**/window.json'):
            paths.update(Path(p).resolve() for p in glob.glob(str(root / pattern), recursive=True))
    return sorted(paths)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def work_spans(row):
    """Proven device work only; wrapper start/finish and drain times don't count."""
    if isinstance(row, dict):
        if row.get('device_executed') is False or row.get('cpu_rehearsal') is True:
            return
        for first, last in (('device_start_monotonic', 'device_end_monotonic'),
                            ('request_start_monotonic', 'request_end_monotonic'),
                            ('work_start', 'work_end')):
            start, end = row.get(first), row.get(last)
            if finite(start) and finite(end) and end > start:
                yield start, end
        for value in row.values():
            if isinstance(value, (dict, list)):
                yield from work_spans(value)
    elif isinstance(row, list):
        for value in row:
            yield from work_spans(value)


def device_evidence(begin, now, notes):
    """Return (device intervals, lane map, actual whole-host spans, waits).

    Historical receipts lacking child exit clocks provide a conservative lower
    bound ending at the last proven device request. Never substitute window
    completion, drain completion, mtime, or an active unit for a missing clock.
    Monotonic receipts are usable only on their recorded boot.
    """
    intervals, lanes, holds, waits = [], {}, [], []
    unclocked = 0
    try:
        boot = (PROC / 'sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        notes.add('Device clocks unavailable: cannot identify this boot; no busy time inferred.')
        return intervals, lanes, holds, waits
    # `now` is the report boundary captured before queue/systemctl reads; do
    # not shift every receipt earlier by the time those reads took.
    current = dt.datetime.now(dt.timezone.utc)
    uptime = time.monotonic()
    epoch = current - dt.timedelta(seconds=uptime)
    ticks = os.sysconf('SC_CLK_TCK')
    rows = process_table(PROC)

    def stamp(seconds):
        return epoch + dt.timedelta(seconds=seconds)

    def monotonic_value(value):
        return finite(value) and value <= uptime

    def add(start, end, unit, lane, scope, source):
        if not (monotonic_value(start) and monotonic_value(end) and start < end):
            return
        s, e = max(stamp(start), begin), min(stamp(end), now)
        if s < e:
            intervals.append((s, e, unit, source))
            lanes[unit] = lane
            if scope == 'whole-host':
                holds.append((s, e))

    def wait(start, end, unit, lane):
        if monotonic_value(start) and monotonic_value(end) and start < end:
            s, e = max(stamp(start), begin), min(stamp(end), now)
            if s < e:
                waits.append((s, e, unit, lane))

    for path in receipt_paths():
        row = read_json(path)
        if row.get('boot_id') != boot or row.get('cpu_rehearsal') is True:
            continue
        admission = read_json(path.parent.with_name(path.parent.name + '-lane-admission.json'))
        coord = admission.get('coordination', {})
        if not isinstance(coord, dict) or coord.get('boot_id') != boot:
            coord = {}
        drain = admission.get('shared_drain', {})
        if isinstance(drain, dict) and monotonic_value(drain.get('completed_monotonic')):
            if stamp(drain['completed_monotonic']) <= begin:
                continue
        if finite(row.get('finished_utc_ns')) and row['finished_utc_ns'] / 1e9 <= begin.timestamp():
            continue
        identity = row.get('identity', {})
        lane = coord.get('lane') or row.get('lane') or (
            identity.get('lane') if isinstance(identity, dict) else None)
        # Card selection is durable even after a transient unit is collected.
        if lane not in ('A', 'B'):
            lane = {0: 'A', 1: 'A', 2: 'B', 3: 'B'}.get(row.get('card'))
        scope = coord.get('scope')
        cgroup = row.get('systemd_cgroup', '')
        if not isinstance(cgroup, str):
            cgroup = ''
        unit = next((part for part in re.split(r'[/\n]', cgroup)
                     if part.endswith('.service') and DEVICE.match(part)), None)
        unit = unit or str(path.parent)
        if coord and isinstance(drain, dict):
            # This is admission waiting, not a device interval. Drain entry is
            # recorded after the other lane released its lease.
            wait(coord.get('started_monotonic'), drain.get('started_monotonic'), unit, lane)
        if row.get('device_executed') is not True:
            continue
        spans = list(work_spans(row))
        for name in ('run/receipt.json', 'run/summary.json', 'summary.json'):
            spans.extend(work_spans(read_json(path.parent / name)))
        # Suite summaries need not embed the request clocks. Read only their
        # small per-request receipts, not native tensor/state artifacts.
        for pattern in ('run/*/receipt.json', 'run/repeat-*/*/receipt.json'):
            for receipt in path.parent.glob(pattern):
                spans.extend(work_spans(read_json(receipt)))
        owners = admission.get('owners', {})
        starts = [o['start_ticks'] / ticks for o in owners.values()
                  if isinstance(o, dict) and o.get('seen') is True
                  and finite(o.get('start_ticks'))] if isinstance(owners, dict) else []
        isolation = read_json(path.parent / 'run/device-isolation.json')
        if isolation.get('passed') is True and not isolation.get('errors'):
            ranks = isolation.get('ranks', [])
            if isinstance(ranks, list):
                for rank in ranks:
                    if not isinstance(rank, dict) or not rank.get('fds'):
                        continue
                    birth = rank.get('process_start_ticks')
                    sampled = isolation.get('sampled_monotonic')
                    if finite(birth) and finite(sampled) and birth / ticks < sampled:
                        starts.append(birth / ticks)
                        spans.append((birth / ticks, sampled))
        # With exactly one rank lifetime, its observed process birth extends
        # measured work back through loading. Serial fixture owners must never
        # bridge unobserved gaps, and no end clock means no historical credit.
        if spans and starts and len(starts) <= 2 and max(starts) <= min(s for s, _ in spans):
            spans.append((min(starts), max(e for _, e in spans)))
        for start, end in spans:
            add(start, end, unit, lane, scope, 'device receipt')
        if not spans:
            unclocked += 1

    coord_root = RESULTS / 'coordination/chain-lanes-v1'
    markers = [read_json(coord_root / f'active-lane-{lane}.json') for lane in 'AB']
    for owner in markers:
        if owner.get('boot_id') != boot:
            continue
        children = device_descendants(owner, rows)
        if (owner.get('scope') == 'whole-host' and not children
                and owner.get('pid') in rows
                and rows[owner['pid']]['start_ticks'] == owner.get('start_ticks')
                and (coord_root / 'hold-lane-B').exists()
                and (coord_root / 'active-lane-B.json').exists()):
            wait(owner.get('started_monotonic'), (now - epoch).total_seconds(),
                 'active-lane-A.json', owner.get('lane'))
    for pid, row in rows.items():
        if row['comm'] != 'own-rt-iq3':
            continue
        try:
            # CPU mock binaries have the same comm. Require the device build.
            exe = (PROC / str(pid) / 'exe').resolve(strict=True)
            if 'device' not in exe.parts:
                continue
            cgroup = (PROC / str(pid) / 'cgroup').read_text()
            unit = next((p for p in re.split(r'[/\n]', cgroup)
                         if p.endswith('.service') and DEVICE.match(p)), None)
            if not unit:
                continue
            owner = next((o for o in markers if o.get('boot_id') == boot
                          and pid in device_descendants(o, rows)), {})
            # Recheck identity after reading exe/cgroup to reject PID reuse.
            stat = (PROC / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(stat[19]) != row['start_ticks'] or stat[0] in ('Z', 'X', 'x'):
                continue
            add(row['start_ticks'] / ticks, (now - epoch).total_seconds(),
                unit, owner.get('lane'), owner.get('scope'), 'live device child')
        except (OSError, ValueError, IndexError):
            continue
    notes.add('Device evidence is a lower bound when historical child exit clocks are missing; '
              'only observed process/request time is used then. Service waits, cooldowns and drain tails are excluded.')
    if unclocked:
        notes.add(f'{unclocked} device receipts lack usable clocks; their wrapper lifetimes are not counted.')
    return intervals, lanes, holds, waits


def parse(hours):
    # Look back 12 h further so units that started before the window are still paired.
    out = subprocess.run(['journalctl', '--user', '--since', f'-{hours + 12}h', '-o', 'short-iso', '--no-pager'],
                         capture_output=True, text=True, check=True).stdout
    starts, intervals, failed = {}, [], {}
    for line in out.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        stamp = dt.datetime.fromisoformat(m.group(1)).astimezone(dt.timezone.utc)
        if m.group(2):
            if DEVICE.match(m.group(2)):
                starts[m.group(2)] = stamp
        else:
            unit = m.group(3)
            # The user manager logs 'Consumed ...' as the last line of every stop
            # (success or failure); 'Failed with result' precedes it on failures.
            if unit in starts:
                if m.group(4).startswith('Failed'):
                    failed[unit] = True
                elif m.group(4).startswith(('Consumed', 'Deactivated')):
                    intervals.append((starts.pop(unit), stamp, unit, 'failed' if failed.pop(unit, False) else 'ok'))
    now = dt.datetime.now(dt.timezone.utc)
    for unit, start in starts.items():
        if active(unit):
            intervals.append((start, now, unit, 'still active'))
    return sorted(intervals), now


def union(spans):
    merged = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def accounting(spans, begin, now):
    busy = union((max(s, begin), min(e, now)) for s, e in spans
                 if e > begin and s < now and e > s)
    gaps, cursor = [], begin
    for s, e in busy:
        if (s - cursor).total_seconds() > 300:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if (now - cursor).total_seconds() > 300:
        gaps.append((cursor, now))
    return sum((e - s).total_seconds() for s, e in busy), gaps


def subtract(spans, busy):
    """An admission wait is idle only where this lane has no device evidence."""
    result = []
    for start, end in union(spans):
        cursor = start
        for s, e in union(busy):
            if e <= cursor or s >= end:
                continue
            if cursor < s:
                result.append((cursor, s))
            cursor = max(cursor, e)
        if cursor < end:
            result.append((cursor, end))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=float, default=6)
    a = ap.parse_args()
    if not 0 < a.hours < float('inf'):
        ap.error('--hours must be positive and finite')
    intervals, now = parse(a.hours)
    begin = now - dt.timedelta(hours=a.hours)
    notes = set()
    queued, evidence = queue_events(now, notes)
    # Prefer the manager's precise start/stop when both sources saw the same
    # invocation. Queue events fill journal gaps and retain the lane after GC.
    intervals = sorted(intervals + [q for q in queued if not any(
        u == q[2] and s <= q[1] and e >= q[0] for s, e, u, _ in intervals)])
    wrappers = intervals
    intervals, receipt_lanes, holds, waits = device_evidence(begin, now, notes)
    evidence.update({u: lane for u, lane in receipt_lanes.items() if lane in ('A', 'B')})
    lanes = {u: unit_lane(u, evidence) for s, e, u, _ in intervals
             if e > begin and s < now and not WAITERS.match(u)}
    # Union rank pairs and duplicate receipt clocks before listing each source.
    intervals = [(s, e, u, 'device evidence') for u in sorted({r[2] for r in intervals})
                 for s, e in union((s, e) for s, e, unit, _ in intervals if unit == u)]
    notes.add(f'{len(wrappers)} wrapper intervals retained for attribution only; '
              'active services and queue START/DONE events do not establish busy time.')
    spans = [(s, e) for s, e, u, _ in intervals if not WAITERS.match(u)]
    busy_s, gaps = accounting(spans + holds, begin, now)
    fmt = lambda t: t.strftime('%H:%M')
    print(f'Window: last {a.hours:g} h ({fmt(begin)}-{fmt(now)} UTC)')
    strict_s, _ = accounting([(s, e) for s, e, u, _ in intervals
                              if not WAITERS.match(u) and '-model-' not in u] + holds, begin, now)
    print(f'Device units in flight (union, excl. pure waiters): {busy_s/3600:.2f} h = {100*busy_s/(a.hours*3600):.0f}% of wall time')
    print(f'  ... also excluding *-model-* queues (they can sit waiting on a CPU oracle): {strict_s/3600:.2f} h = {100*strict_s/(a.hours*3600):.0f}%')
    print('NOTE: in-flight now means evidenced device children/work, not active wrappers; '
          'this is occupancy, not a GPU compute-utilization measurement.')
    for lane, cards in (('A', '0+1'), ('B', '2+3')):
        lane_spans = [(s, e) for s, e, u, _ in intervals
                      if not WAITERS.match(u) and lanes.get(u) == lane]
        # A holds B only for evidenced device activity, never admission waits.
        lane_spans += holds
        seconds, idle = accounting(lane_spans, begin, now)
        print(f'Lane {lane} (cards {cards}) busy/held: {seconds/3600:.2f} h = '
              f'{100*seconds/(a.hours*3600):.0f}% of wall time')
        print(f'  Lane {lane} idle gaps > 5 min (no attributed device unit or hold):')
        for s, e in idle:
            print(f'    {fmt(s)}-{fmt(e)} UTC  {(e-s).total_seconds()/60:.0f} min')
        if not idle:
            print('    none')
        admission_idle = subtract([(s, e) for s, e, _, owner in waits if owner == lane], lane_spans)
        idle_s, _ = accounting(admission_idle, begin, now)
        print(f'  Lane {lane} idle_admission_wait: {idle_s/60:.1f} min')
        for s, e in admission_idle:
            print(f'    {fmt(s)}-{fmt(e)} UTC  {(e-s).total_seconds()/60:.0f} min  [idle_admission_wait]')
    hold_s, _ = accounting(holds, begin, now)
    print(f'  Lane B whole-host holds included: {hold_s/60:.1f} min')
    unknown = sorted(u for u, lane in lanes.items() if lane is None)
    if unknown:
        notes.add('Unassigned units count only in the combined union; per-lane busy may be understated: '
                  + ', '.join(unknown))
    for note in sorted(notes):
        print('NOTE: ' + note)
    print('\nIdle gaps > 5 min (no device unit in flight):')
    for s, e in gaps:
        print(f'  {fmt(s)}-{fmt(e)} UTC  {(e-s).total_seconds()/60:.0f} min')
    print('\nDevice units:')
    for s, e, u, r in intervals:
        if e >= begin:
            print(f'  {fmt(s)}-{fmt(e)}  {(e-s).total_seconds()/60:6.1f} min  {u}  [{r}; lane {lanes.get(u) or "unknown"}]')
    print('\nCodex jobs (scratchpad logs; last write time):')
    for f in sorted(glob.glob(os.path.join(SCRATCH, 'codex-*.log')), key=os.path.getmtime)[-10:]:
        m = dt.datetime.fromtimestamp(os.path.getmtime(f), dt.timezone.utc)
        if m >= begin:
            print(f'  {fmt(m)}  {os.path.basename(f)}  {os.path.getsize(f)//1024} KiB')
    running = subprocess.run(['pgrep', '-fc', 'codex-linux-x64/vendor'], capture_output=True, text=True).stdout.strip()
    print(f'  Codex processes running now: {running or 0}')
    log = subprocess.run(['env', 'TZ=UTC', 'git', '-C', REPO, 'log', f"--since={begin.strftime('%Y-%m-%dT%H:%M:%SZ')}", '--format=%cd %h %an: %s', '--date=format-local:%H:%M'],
                         capture_output=True, text=True).stdout.splitlines()
    print(f'\nCommits in window: {len(log)}')
    for line in log[:25]:
        print('  ' + line[:150])
    try:
        th = json.load(open(os.path.join(REPO, 'scripts/packet49_record_threshold.json')))['records'][-1]
        print(f"\nCurrent 2-card record floor: {th['threshold_tok_s']:.4f} tok/s ({th['reference_submission']})")
    except Exception as error:
        print(f'\nRecord floor unavailable: {error}')


if __name__ == '__main__':
    main()
