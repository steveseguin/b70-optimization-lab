#!/usr/bin/env python3
"""Read-only time accounting for the hourly efficiency review.

Reconstructs per-lane and combined busy/held time from device-backed queue jobs,
chain window receipts and live device children over the last N hours. Journal
wrappers alone do not establish occupancy. Admission waits count as idle. It also
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
# Unbounded journal wrapper lifetimes do not establish occupancy.
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


def scope_of(row):
    """Read only explicit scheduling metadata, not arbitrary nested scope text."""
    if not isinstance(row, dict):
        return None
    if row.get('scope') in ('whole-host', 'lane-A', 'lane-B'):
        return row['scope']
    for key in ('job', 'plan', 'lane_admission', 'coordination', 'reservation'):
        scope = scope_of(row.get(key))
        if scope:
            return scope
    return None


def json_lines(path, notes):
    try:
        with path.open() as stream:
            for line in stream:
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        yield row
                    else:
                        notes.add(f'{path.name}: malformed queue record skipped.')
                except ValueError:
                    notes.add(f'{path.name}: malformed queue record skipped.')
    except OSError:
        notes.add(f'{path.name}: queue evidence unavailable.')


def job_scope(job):
    """Use saved plans/receipts; never execute a job's plan command."""
    scope = scope_of(job)
    if scope:
        return scope
    argv = job.get('argv', [])
    if not isinstance(argv, list) or '--output' not in argv:
        return None
    index = argv.index('--output') + 1
    if index >= len(argv) or not isinstance(argv[index], str):
        return None
    output = Path(argv[index])
    if not output.is_absolute():
        output = Path(REPO) / output
    for path in [output / 'queue.json', output / 'plan.json',
                 output / 'window.json', *sorted(output.glob('*/window.json'))]:
        scope = scope_of(read_json(path))
        if scope:
            return scope
    return None


def busy_cards(row, path=None):
    """Explicit card identity, including one-card paths in older receipts."""
    card = row.get('card')
    if type(card) is int and card in range(4):
        return (card,)
    argv = row.get('argv', [])
    if isinstance(argv, list):
        for i, arg in enumerate(argv):
            value = argv[i + 1] if arg == '--card' and i + 1 < len(argv) else (
                arg.split('=', 1)[1] if isinstance(arg, str) and arg.startswith('--card=') else None)
            if value in ('0', '1', '2', '3'):
                return (int(value),)
        for arg in argv:
            if isinstance(arg, str):
                match = re.search(r'/evidence/card([0-3])-', arg)
                if match:
                    return (int(match[1]),)
    if path:
        match = re.search(r'/evidence/card([0-3])-', str(path))
        if match:
            return (int(match[1]),)
    for key in ('job', 'plan', 'lane_admission', 'coordination', 'reservation'):
        nested = row.get(key)
        if isinstance(nested, dict):
            cards = busy_cards(nested)
            if cards:
                return cards
    return None


def window_cards(row, path):
    # A rank receipt can name card 0 while belonging to a two-card job. Only
    # the one-card window schema/path or an explicit count proves exclusivity.
    if (re.search(r'/evidence/card[0-3]-', str(path))
            or str(row.get('schema', '')).startswith('own-runtime.packet58.')
            or row.get('gpu_count') == 1):
        return busy_cards(row, path)
    return None


def job_output(job):
    argv = job.get('argv', [])
    if not isinstance(argv, list):
        return None
    for i, arg in enumerate(argv):
        value = (argv[i + 1] if arg == '--output' and i + 1 < len(argv)
                 else arg.split('=', 1)[1] if isinstance(arg, str)
                 and arg.startswith('--output=') else None)
        if isinstance(value, str) and value:
            path = Path(value)
            return path if path.is_absolute() else Path(REPO) / path
    return None


def creation_time(path):
    """Linux birth time, never mtime/ctime (both move when logs are updated)."""
    try:
        result = subprocess.run(['/usr/bin/stat', '-c', '%w', '--', str(path)],
                                capture_output=True, text=True, timeout=5,
                                stdin=subprocess.DEVNULL)
        if result.returncode == 0 and result.stdout.strip() != '-':
            return timestamp(result.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def first_device(job, start, end, observed=()):
    """Earliest evidence in this attempt; old/reused outputs earn no credit.

    Output/log creation is an entry proxy, not proof of GPU compute. Explicit
    window clocks survive copies/archives where birth time is unavailable.
    Read metadata and small window receipts only, never native/model payloads.
    """
    unit = 'screen-' + job['name'] + '.service'
    candidates = [s for s, e, u, _ in observed if u == unit and start <= s <= end]
    output = job_output(job)
    if output and output.is_dir():
        windows = sorted(output.rglob('window.json'))
        rows = [(p, read_json(p)) for p in windows]
        excluded = [p.parent for p, row in rows if row.get('cpu_rehearsal') is True
                    or row.get('device_executed') is False]
        def allowed(path):
            return not any(path == root or root in path.parents for root in excluded)
        # Prefer the recorded clock when present; birth time still covers the
        # admitted setup before that first window starts.
        for path, row in rows:
            if not allowed(path):
                continue
            try:
                if finite(row.get('started_utc_ns')):
                    candidates.append(dt.datetime.fromtimestamp(row['started_utc_ns'] / 1e9, dt.timezone.utc))
                elif row.get('start_utc'):
                    candidates.append(timestamp(row['start_utc']))
            except (ValueError, TypeError, OverflowError, OSError):
                pass
        paths = [output, *output.rglob('native.log'), *output.rglob('rank*.log')]
        for path in paths:
            if allowed(path):
                birth = creation_time(path)
                if birth is not None:
                    candidates.append(birth)
    return min((t for t in candidates if start <= t <= end), default=None)


def wait_cause(row):
    """Only named coordination causes, never arbitrary log or environment text."""
    for key in ('admission_cause', 'cause', 'blocker'):
        value = row.get(key)
        if isinstance(value, dict):
            value = value.get('source')
        if value in ('hold-lane-B', 'active-lane-A.json', 'active-lane-B.json',
                     'teardown-state.json', 'lane-lock', 'host-memory'):
            return value
    return None


def queue_events(now, notes, holds=None, cards=None, waits=None, causes=None, observed=(), begin=None):
    """Split job lifetimes into admission waiting and device-backed occupancy."""
    starts, intervals, lanes = {}, [], {}
    if holds is None:
        holds = []
    if cards is None:
        cards = {}
    if waits is None:
        waits = []
    if causes is None:
        causes = {}
    root = OPS / 'lane-queue'
    scopes, jobs, attempts = {}, {}, []
    receipts = []
    for lane in ('A', 'B'):
        # Reviewed done files remain evidence after the live done file is rotated.
        for path in sorted(root.glob(f'done-{lane}*.txt')):
            receipts.extend(json_lines(path, notes))
    for path in sorted(root.glob('*.exit.json')):
        row = read_json(path)
        if row.get('start_utc') and row.get('end_utc'):
            receipts.append(row)
    for row in receipts:
        job = row.get('job', row)
        if not isinstance(job, dict) or not isinstance(job.get('name'), str):
            continue
        jobs[job['name']] = job
        cause = wait_cause(row) or wait_cause(job)
        if cause:
            causes['screen-' + job['name'] + '.service'] = cause
        scope = job_scope(row) or job_scope(job)
        if scope:
            scopes[job['name']] = scope
        identity = busy_cards(row) or busy_cards(job)
        if identity:
            cards['screen-' + job['name'] + '.service'] = identity
    # START events do not embed the job. Proposals provide scope for jobs whose
    # terminal receipt is not yet available, without counting unstarted plans.
    for path in sorted(root.glob('proposed-*.txt')):
        for job in json_lines(path, notes):
            if isinstance(job.get('name'), str):
                jobs.setdefault(job['name'], job)
            if isinstance(job.get('name'), str) and job['name'] not in scopes:
                scope = job_scope(job)
                if scope:
                    scopes[job['name']] = scope
            if isinstance(job.get('name'), str) and busy_cards(job):
                cards.setdefault('screen-' + job['name'] + '.service', busy_cards(job))

    def add(start, end, name, lane, kind, scope=None):
        if lane not in ('A', 'B') or end <= start:
            return
        unit = 'screen-' + name + '.service'
        intervals.append((start, end, unit, kind))
        lanes[unit] = lane
        if scope:
            scopes[name] = scope

    for row in receipts:
        try:
            job = row.get('job', row)
            attempts.append((timestamp(row['start_utc']), timestamp(row['end_utc']), job))
            add(timestamp(row['start_utc']), timestamp(row['end_utc']),
                job['name'], job['lane'], 'queue exit receipt', scope_of(row))
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
            notes.add('Malformed queue exit receipt skipped.')
    for lane in ('A', 'B'):
        for row in json_lines(root / f'events-{lane}.jsonl', notes):
            try:
                if row.get('lane') != lane or not row.get('name'):
                    continue
                name = row['name']
                unit = 'screen-' + name + '.service'
                stamp = timestamp(row['utc'])
                kind = row['event']
                lanes[unit] = lane
                cause = wait_cause(row)
                if cause:
                    causes[unit] = cause
                if scope_of(row):
                    scopes[name] = scope_of(row)
                if kind == 'START':
                    starts[unit] = (stamp, name, lane)
                elif (kind in ('DONE', 'REPORT-FAILED')
                      or kind.startswith(('REFUSED', 'FAILED'))) and unit in starts:
                    start, _, _ = starts.pop(unit)
                    add(start, stamp, name, lane, kind)
            except (ValueError, KeyError, TypeError, AttributeError):
                notes.add(f'Lane {lane}: malformed queue event skipped.')
    for unit, (start, name, lane) in starts.items():
        # A lost terminal event must not turn an archived completed job into an
        # open interval, especially if this unit name is reused later.
        if any(u == unit and s <= start <= e for s, e, u, _ in intervals):
            continue
        if active(unit):
            add(start, now, name, lane, 'still active')
        else:
            notes.add(f'{unit}: unfinished queue event; active state unconfirmed, end unknown.')
    busy = []
    for start, end, unit, kind in intervals:
        if begin is not None and (end <= begin or start >= now):
            continue
        name = unit[len('screen-'):-len('.service')]
        job = next((job for s, e, job in attempts if isinstance(job, dict)
                    and job.get('name') == name and s <= start <= e),
                   jobs.get(name, {'name': name}))
        first = first_device(job, start, end, observed)
        wait_end = first if first is not None else end
        if wait_end > start:
            waits.append((start, wait_end, unit, lanes[unit]))
        if first is None:
            notes.add(f'{unit}: device entry unobserved; lifetime is unconfirmed admission wait, not busy time.')
            continue
        if first < end:
            busy.append((first, end, unit, kind))
            if scopes.get(name) == 'whole-host' or len(cards.get(unit, ())) == 1:
                holds.append((first, end))
    return busy, lanes


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


def chain_windows(begin, now, notes, cards=None):
    """Count each completed chain window, excluding its admission wait.

    Older K receipts store clocks in the sibling lane-admission receipt's
    shared_drain: started is admission granted, completed is window release.
    Those monotonic clocks are valid only on the recorded boot.
    """
    intervals, lanes, holds = [], {}, []
    if cards is None:
        cards = {}
    try:
        boot = (PROC / 'sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        boot = None
    epoch = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=time.monotonic())
    paths = set()
    for root in (OPS.parent / 'stage2', RESULTS):
        for pattern in ('packet*/build/device-cards01-*/*/window.json',
                        'packet*/evidence/card*-*/**/window.json'):
            paths.update(p.resolve() for p in root.glob(pattern))
    for path in sorted(paths):
        row = read_json(path)
        if row.get('cpu_rehearsal') is True or row.get('device_executed') is False:
            continue
        admission = read_json(path.parent.with_name(path.parent.name + '-lane-admission.json'))
        scope = scope_of(row) or scope_of(admission)
        start = end = None
        try:
            if row.get('start_utc') and row.get('end_utc'):
                start, end = timestamp(row['start_utc']), timestamp(row['end_utc'])
            elif finite(row.get('started_utc_ns')) and finite(row.get('finished_utc_ns')):
                start, end = (dt.datetime.fromtimestamp(row[k] / 1e9, dt.timezone.utc)
                              for k in ('started_utc_ns', 'finished_utc_ns'))
            else:
                drain = admission.get('shared_drain', {})
                if not isinstance(drain, dict) or not boot or drain.get('boot_id') != boot:
                    continue
                first, last = drain.get('started_monotonic'), drain.get('completed_monotonic')
                if finite(first) and finite(last):
                    start, end = (epoch + dt.timedelta(seconds=t) for t in (first, last))
        except (ValueError, TypeError, OverflowError, OSError):
            notes.add(f'{path.parent}: invalid chain window clocks skipped.')
            continue
        if start is None or end is None or end <= start:
            continue
        start, end = max(start, begin), min(end, now)
        if end <= start:
            continue
        unit = str(path.parent)
        intervals.append((start, end, unit, 'chain window receipt'))
        identity = window_cards(row, path)
        lanes[unit] = ('A' if identity[0] < 2 else 'B') if identity else 'A'
        if identity:
            cards[unit] = identity
        if scope == 'whole-host' or identity and len(identity) == 1:
            holds.append((start, end))
    return intervals, lanes, holds


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


def device_evidence(begin, now, notes, cards=None):
    """Return (device intervals, lane map, actual whole-host spans, waits).

    Historical receipts lacking child exit clocks provide a conservative lower
    bound ending at the last proven device request. Never substitute window
    completion, drain completion, mtime, or an active unit for a missing clock.
    Monotonic receipts are usable only on their recorded boot.
    """
    intervals, lanes, holds, waits = [], {}, [], []
    if cards is None:
        cards = {}
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
        identity_cards = window_cards(row, path)
        if identity_cards:
            cards[unit] = identity_cards
            scope = 'whole-host'
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
    notes.add('Additional device evidence uses observed process/request clocks; '
              'queue lifetimes and chain windows are counted separately. Admission waits remain separate.')
    if unclocked:
        notes.add(f'{unclocked} device receipts lack child clocks; queue/window receipts may still establish busy time.')
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


def card_minutes(intervals, lanes, cards, begin, now):
    """Union assigned-card occupancy; held idle cards never earn busy credit."""
    spans = {card: [] for card in range(4)}
    unknown = []
    for start, end, unit, _ in intervals:
        if WAITERS.match(unit):
            continue
        identity = cards.get(unit) or {'A': (0, 1), 'B': (2, 3)}.get(lanes.get(unit))
        if identity is None:
            unknown.append((start, end))
            continue
        for card in identity:
            spans[card].append((start, end))
    busy = sum(accounting(rows, begin, now)[0] for rows in spans.values()) / 60
    available = (now - begin).total_seconds() * 4 / 60
    return busy, available, accounting(unknown, begin, now)[0] / 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=float, default=6)
    a = ap.parse_args()
    if not 0 < a.hours < float('inf'):
        ap.error('--hours must be positive and finite')
    intervals, now = parse(a.hours)
    begin = now - dt.timedelta(hours=a.hours)
    notes = set()
    queue_holds = []
    cards = {}
    wrappers = intervals
    intervals, receipt_lanes, holds, waits = device_evidence(begin, now, notes, cards)
    causes = {}
    queued, evidence = queue_events(now, notes, queue_holds, cards, waits, causes, intervals, begin)
    windows, window_lanes, window_holds = chain_windows(begin, now, notes, cards)
    intervals += queued + windows
    holds += queue_holds + window_holds
    evidence.update({u: lane for u, lane in receipt_lanes.items() if lane in ('A', 'B')})
    evidence.update(window_lanes)
    lanes = {u: unit_lane(u, evidence) for s, e, u, _ in intervals
             if e > begin and s < now and not WAITERS.match(u)}
    # Union rank pairs and duplicate receipt clocks before listing each source.
    intervals = [(s, e, u, 'busy/held evidence') for u in sorted({r[2] for r in intervals})
                 for s, e in union((s, e) for s, e, unit, _ in intervals if unit == u)]
    notes.add(f'{len(wrappers)} wrapper intervals retained for attribution only; '
              'queue jobs count only after first device evidence; completed chain windows also count.')
    spans = [(s, e) for s, e, u, _ in intervals if not WAITERS.match(u)]
    busy_s, gaps = accounting(spans + holds, begin, now)
    fmt = lambda t: t.strftime('%H:%M')
    print(f'Window: last {a.hours:g} h ({fmt(begin)}-{fmt(now)} UTC)')
    strict_s, _ = accounting([(s, e) for s, e, u, _ in intervals
                              if not WAITERS.match(u) and '-model-' not in u] + holds, begin, now)
    print(f'Device units in flight (union, excl. pure waiters): {busy_s/3600:.2f} h = {100*busy_s/(a.hours*3600):.0f}% of wall time')
    print(f'  ... also excluding *-model-* queues (they can sit waiting on a CPU oracle): {strict_s/3600:.2f} h = {100*strict_s/(a.hours*3600):.0f}%')
    print('NOTE: busy/held includes first-device-to-terminal queue intervals and chain windows; '
          'this is lane occupancy, not a GPU compute-utilization measurement.')
    card_busy, card_available, unknown = card_minutes(intervals, lanes, cards, begin, now)
    print(f'Busy card-minutes / available card-minutes: {card_busy:.1f} / '
          f'{card_available:.1f} = {100 * card_busy / card_available:.1f}% '
          '(assigned-card occupancy, not hardware compute counters)')
    print('  One-card windows hold cards 0–3; only the selected card earns busy time.')
    if unknown:
        print(f'  Card identity unknown for {unknown:.1f} minutes; no card credit inferred.')
    for lane, cards in (('A', '0+1'), ('B', '2+3')):
        lane_spans = [(s, e) for s, e, u, _ in intervals
                      if not WAITERS.match(u) and lanes.get(u) == lane]
        # Explicit whole-host jobs/windows hold both lanes; union removes overlaps.
        lane_spans += holds
        seconds, idle = accounting(lane_spans, begin, now)
        print(f'Lane {lane} (cards {cards}) busy/held: {seconds/3600:.2f} h = '
              f'{100*seconds/(a.hours*3600):.0f}% of wall time')
        print(f'  Lane {lane} idle gaps > 5 min (no attributed device unit or hold):')
        for s, e in idle:
            print(f'    {fmt(s)}-{fmt(e)} UTC  {(e-s).total_seconds()/60:.0f} min')
        if not idle:
            print('    none')
        lane_waits = [(max(s, begin), min(e, now)) for s, e, _, owner in waits
                      if owner == lane and e > begin and s < now]
        wait_s, _ = accounting(lane_waits, begin, now)
        print(f'  Lane {lane} admission_wait (including overlap with other work/holds): {wait_s/60:.1f} min')
        for cause in sorted({causes.get(unit, 'unknown') for _, _, unit, owner in waits if owner == lane}):
            cause_s, _ = accounting([(s, e) for s, e, unit, owner in waits
                                     if owner == lane and causes.get(unit, 'unknown') == cause], begin, now)
            print(f'    cause={cause}: {cause_s/60:.1f} min (union within cause)')
        admission_idle = subtract(lane_waits, lane_spans)
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
