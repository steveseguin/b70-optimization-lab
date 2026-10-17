#!/usr/bin/env python3
"""Read-only time accounting for the hourly efficiency review.

Reconstructs, from the systemd user journal, when coordinator device units
(GPU windows and chains) were in flight over the last N hours. It also lists
idle gaps, Codex job activity from the scratchpad logs, recent commits and the
current GPU fault-line count. It never launches, stops or edits anything.

Usage: python3 -B gpu_time_review.py [--hours 6]
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess

# Units that hold or wait for GPUs: device windows, chains and drivers.
DEVICE = re.compile(r'^(packet\d+\S*|p49\S*|p5\d\S*|screen\S*)\.service$')
# Driver units that only wait (no GPU work while they wait) are reported, but
# not counted as busy.
# Only units that purely wait (no device work of their own). Chain drivers such as
# p56-chain/p55-chain run windows themselves and count as busy (reviewer, 2026-10-17).
WAITERS = re.compile(r'^(p58-after-p57\S*)\.service$')
LINE = re.compile(r'^(\S+) \S+ systemd\[\d+\]: (?:Started (\S+\.service)|(\S+\.service): (Deactivated successfully|Failed with result.*|Consumed .*))')
SCRATCH = '/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad'
REPO = '/home/steve/llm-optimizations'


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
        state = subprocess.run(['systemctl', '--user', 'is-active', unit], capture_output=True, text=True).stdout.strip()
        if state == 'active':
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=float, default=6)
    a = ap.parse_args()
    intervals, now = parse(a.hours)
    begin = now - dt.timedelta(hours=a.hours)
    busy = union([(max(s, begin), e) for s, e, u, _ in intervals if e > begin and not WAITERS.match(u)])
    busy_s = sum((e - s).total_seconds() for s, e in busy)
    gaps, cursor = [], begin
    for s, e in busy:
        if (s - cursor).total_seconds() > 300:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if (now - cursor).total_seconds() > 300:
        gaps.append((cursor, now))
    fmt = lambda t: t.strftime('%H:%M')
    print(f'Window: last {a.hours:g} h ({fmt(begin)}-{fmt(now)} UTC)')
    strict = union([(max(s, begin), e) for s, e, u, _ in intervals if e > begin and not WAITERS.match(u) and '-model-' not in u])
    strict_s = sum((e - s).total_seconds() for s, e in strict)
    print(f'Device units in flight (union, excl. pure waiters): {busy_s/3600:.2f} h = {100*busy_s/(a.hours*3600):.0f}% of wall time')
    print(f'  ... also excluding *-model-* queues (they can sit waiting on a CPU oracle): {strict_s/3600:.2f} h = {100*strict_s/(a.hours*3600):.0f}%')
    print('NOTE: in-flight includes 90/305 s cooldowns and model loads inside chains; it is an upper bound on GPU compute.')
    print('\nIdle gaps > 5 min (no device unit in flight):')
    for s, e in gaps:
        print(f'  {fmt(s)}-{fmt(e)} UTC  {(e-s).total_seconds()/60:.0f} min')
    print('\nDevice units:')
    for s, e, u, r in intervals:
        if e >= begin:
            print(f'  {fmt(s)}-{fmt(e)}  {(e-s).total_seconds()/60:6.1f} min  {u}  [{r}]')
    print('\nCodex jobs (scratchpad logs; last write time):')
    for f in sorted(glob.glob(os.path.join(SCRATCH, 'codex-*.log')), key=os.path.getmtime)[-10:]:
        m = dt.datetime.fromtimestamp(os.path.getmtime(f), dt.timezone.utc)
        if m >= begin:
            print(f'  {fmt(m)}  {os.path.basename(f)}  {os.path.getsize(f)//1024} KiB')
    running = subprocess.run(['pgrep', '-fc', 'codex-linux-x64/vendor'], capture_output=True, text=True).stdout.strip()
    print(f'  Codex processes running now: {running or 0}')
    log = subprocess.run(['env', 'TZ=UTC', 'git', '-C', REPO, 'log', f'--since={a.hours} hours ago', '--format=%cd %h %an: %s', '--date=format-local:%H:%M'],
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
