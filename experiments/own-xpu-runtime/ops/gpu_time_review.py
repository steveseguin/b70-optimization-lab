#!/usr/bin/env python3
"""Read-only time accounting for the hourly efficiency review.

Reconstructs per-lane and combined occupancy from the systemd user journal,
lane-queue events and whole-host hold receipts over the last N hours. It also
lists idle gaps, Codex activity, recent commits and the record floor.
It never launches, stops or edits anything.

Usage: python3 -B gpu_time_review.py [--hours 6]
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import time
from pathlib import Path

# Units that hold or wait for GPUs: device windows, chains and drivers.
DEVICE = re.compile(r'^(packet\d+\S*|p\d+\S*|screen\S*)\.service$')  # p61x-chain etc. (review 3 fix)
# Driver units that only wait (no GPU work while they wait) are reported, but
# not counted as busy.
# Only units that purely wait (no device work of their own). Chain drivers such as
# p56-chain/p55-chain run windows themselves and count as busy (reviewer, 2026-10-17).
WAITERS = re.compile(r'^(p58-after-p57\S*)\.service$')
LINE = re.compile(r'^(\S+) \S+ systemd\[\d+\]: (?:Started (\S+\.service)|(\S+\.service): (Deactivated successfully|Failed with result.*|Consumed .*))')
SCRATCH = '/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad'
REPO = '/home/steve/llm-optimizations'
OPS = Path(__file__).resolve().parent
CHAIN = re.compile(r'^(?:packet|p)\d+.*-chain(?:[.-]|$)')
TIMING_WINDOWS = ('W2m', 'WSs', 'WS128')


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
    """Use durable START/terminal events, never queue contents, as occupancy."""
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


def whole_host_holds(begin, now, notes):
    """Best effort from completed lane-admission receipts on this boot.

    A whole-host chain-lanes.v1 reservation proves hold-lane-B was created.
    Its shared-drain completion bounds the hold (release immediately follows).
    Never infer a hold from a timing window's name alone, or from file mtime.
    """
    spans = []
    try:
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        notes.add('Whole-host hold receipts unavailable: cannot identify this boot.')
        return spans
    epoch = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=time.monotonic())
    patterns = [str(OPS.parent / 'stage2/packet*/build/device*/*-lane-admission.json'),
                '/home/steve/own-xpu-runtime-results/packet*/build/device*/*-lane-admission.json']
    paths = {Path(p).resolve() for pattern in patterns for p in glob.glob(pattern)}
    for path in sorted(paths):
        row = read_json(path)
        if row.get('window') not in TIMING_WINDOWS:
            continue
        coord = row.get('coordination', {})
        drain = row.get('shared_drain', {})
        if not isinstance(coord, dict) or not isinstance(drain, dict):
            continue
        if not (row.get('passed') is True and row.get('scope') == 'whole-host'
                and coord.get('schema') == 'own-runtime.chain-lanes.v1'
                and coord.get('scope') == 'whole-host' and coord.get('lane') == 'A'
                and coord.get('boot_id') == boot and drain.get('drained') is True):
            continue
        try:
            start = epoch + dt.timedelta(seconds=coord['started_monotonic'])
            end = epoch + dt.timedelta(seconds=drain['completed_monotonic'])
        except (KeyError, TypeError, ValueError, OverflowError):
            notes.add(f'{path.parent.name}/{row["window"]}: hold timing unavailable.')
            continue
        if begin < end <= now and start < end:
            spans.append((max(start, begin), end))
    notes.add('Lane B holds: best effort from completed W2m/WSs/WS128 whole-host '
              'receipts on this boot; missing, unfinished or older-boot holds are not counted.')
    return spans


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
    lanes = {u: unit_lane(u, evidence) for s, e, u, _ in intervals
             if e > begin and s < now and not WAITERS.match(u)}
    holds = whole_host_holds(begin, now, notes)
    spans = [(s, e) for s, e, u, _ in intervals if not WAITERS.match(u)]
    busy_s, gaps = accounting(spans + holds, begin, now)
    fmt = lambda t: t.strftime('%H:%M')
    print(f'Window: last {a.hours:g} h ({fmt(begin)}-{fmt(now)} UTC)')
    strict_s, _ = accounting([(s, e) for s, e, u, _ in intervals
                              if not WAITERS.match(u) and '-model-' not in u] + holds, begin, now)
    print(f'Device units in flight (union, excl. pure waiters): {busy_s/3600:.2f} h = {100*busy_s/(a.hours*3600):.0f}% of wall time')
    print(f'  ... also excluding *-model-* queues (they can sit waiting on a CPU oracle): {strict_s/3600:.2f} h = {100*strict_s/(a.hours*3600):.0f}%')
    print('NOTE: in-flight includes 90/305 s cooldowns and model loads inside chains; it is an upper bound on GPU compute.')
    for lane, cards in (('A', '0+1'), ('B', '2+3')):
        lane_spans = [(s, e) for s, e, u, _ in intervals
                      if not WAITERS.match(u) and lanes.get(u) == lane]
        # A's whole-host reservation occupies A and holds B, even if the
        # corresponding chain start has fallen out of the available journal.
        lane_spans += holds
        seconds, idle = accounting(lane_spans, begin, now)
        print(f'Lane {lane} (cards {cards}) busy/held: {seconds/3600:.2f} h = '
              f'{100*seconds/(a.hours*3600):.0f}% of wall time')
        print(f'  Lane {lane} idle gaps > 5 min (no attributed device unit or hold):')
        for s, e in idle:
            print(f'    {fmt(s)}-{fmt(e)} UTC  {(e-s).total_seconds()/60:.0f} min')
        if not idle:
            print('    none')
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
