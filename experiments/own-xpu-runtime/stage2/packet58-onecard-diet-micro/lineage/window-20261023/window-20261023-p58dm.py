#!/usr/bin/env python3
"""Lane-B micro window (2026-10-23): packet58-onecard-diet-micro (one-card p58ag diet vs production, cold / warm, both orders) on card 2, no model load, no waiter.

Sequence (halts on any failure; never retries, never restarts the host or drivers):
 1. rewrite ops/lane-queue/queue-B.txt from proposed-p58-dietmicro-micro-B.txt (under edit-B.lock);
 2. live `lanequeue.py plan --lane B` must pass every row (pin guard included);
 3. stop the three daily endpoints gracefully; wait until inactive; require MemAvailable;
 4. archive + remove PAUSE-B (PAUSE-A stays: two-card rows are whole-host); arm the packet183
    win-path waiter unit p183-win; launch the runner as transient unit lanequeue-B41;
 5. watch events-B.jsonl until both rows are DONE or any failure/stop; wait for the waiter
    (chain path, 2.5 h deadline); then STOP-B, wait for the unit, remove STOP-B, re-create PAUSE-B;
 6. restore the endpoints (restore-endpoints-20261021.py <suffix>).
Receipts: <scratch>/window-20261023-p58dm/.
"""
import fcntl, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
Q = ROOT / 'experiments/own-xpu-runtime/ops/lane-queue'
SCRATCH = Path(__file__).resolve().parent
OUT = SCRATCH / 'window-20261023-p58dm'
OUT.mkdir(exist_ok=True)
LANE = 'B'
UNIT = 'lanequeue-B41'
WAITER = 'p183-win'
WAITER_LOG = '/tmp/claude-1000/-home-steve/fn-run/p183-win.log'
WAITER_SH = ROOT / 'experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/chain/p183-win.sh'
PROPOSALS = ['proposed-p58-dietmicro-micro-B.txt']
ROWS = ['packet58-onecard-diet-micro-B']
REQUIRED_MEM = 108797048558 + 1024 ** 3  # k3 rows' host admission + the queue's 1 GiB
ENDPOINTS = ['qwen38-27b-vision', 'qwen38-27b-fp8-tp1-test', 'qwen38-27b-fp8']
RESTORE_SUFFIX = sys.argv[1] if len(sys.argv) > 1 else '20261023-restore23'
PY = ['nice', '-n', '19', 'taskset', '-c', '8-15,24-31', '/usr/bin/python3', '-B']
TERMINAL = ('FAILED', 'FAILED-status', 'FAILED-postflight', 'REFUSED-fast', 'REFUSED-PREDEVICE',
            'REPORT-FAILED', 'STOP', 'SKIPPED-DEPENDENCY', 'SKIPPED')


def now():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    line = f'{now()} {msg}'
    print(line, flush=True)
    with (OUT / 'driver.log').open('a') as f:
        f.write(line + '\n')


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def is_active(unit):
    return sh(['systemctl', '--user', 'is-active', unit + '.service']).stdout.strip()


def mem_available():
    for line in open('/proc/meminfo'):
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024


def step1_queue():
    rows = []
    for prop in PROPOSALS:
        for line in (Q / prop).read_text().splitlines():
            if line.startswith('{'):
                rows.append(json.loads(line))
    names = [r['name'] for r in rows]
    if names != ROWS:
        raise SystemExit(f'proposal rows {names} != expected {ROWS}')
    if any(r.get('lane') != LANE for r in rows):
        raise SystemExit('proposal row lane mismatch')
    with (Q / f'edit-{LANE}.lock').open('a+') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        tmp = Q / f'queue-{LANE}.txt.tmp'
        tmp.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        os.replace(tmp, Q / f'queue-{LANE}.txt')
    log(f'queue-{LANE}.txt rewritten with {len(rows)} rows from {PROPOSALS}')
    (OUT / f'queue-{LANE}.snapshot.txt').write_text((Q / f'queue-{LANE}.txt').read_text())


def step2_plan():
    cp = sh(PY + [str(Q / 'lanequeue.py'), 'plan', '--lane', LANE], cwd=str(ROOT), stdin=subprocess.DEVNULL)
    (OUT / 'live-plan.log').write_text(cp.stdout + cp.stderr)
    results = [json.loads(l) for l in cp.stdout.splitlines() if l.startswith('{')]
    bad = [r for r in results if r.get('plan') != 'passed']
    if cp.returncode != 0 or len(results) != len(ROWS) or bad:
        raise SystemExit('live plan failed: rc=%d rows=%d bad=%s' % (cp.returncode, len(results),
                         [(r.get('name'), str(r.get('reason'))[:300]) for r in bad]))
    log('live plan passed for all %d rows' % len(results))


def step3_stop_endpoints():
    active = [u for u in ENDPOINTS if is_active(u) == 'active']
    log(f'stopping endpoints: {active}')
    if active:
        cp = sh(['systemctl', '--user', 'stop', *[u + '.service' for u in active]])
        log(f'stop rc={cp.returncode} {cp.stderr.strip()}')
    deadline = time.monotonic() + 600
    while any(is_active(u) in ('active', 'deactivating') for u in ENDPOINTS):
        if time.monotonic() > deadline:
            raise SystemExit('endpoints did not stop within 600 s; halting (no escalation)')
        time.sleep(5)
    time.sleep(10)
    avail = mem_available()
    log(f'endpoints stopped; MemAvailable={avail} required={REQUIRED_MEM}')
    if avail < REQUIRED_MEM:
        raise SystemExit(f'MemAvailable {avail} < required {REQUIRED_MEM}; halting')
    users = sh(['bash', '-c', 'for p in /proc/[0-9]*; do ls -l $p/fd 2>/dev/null | grep -q renderD && echo $(basename $p); done']).stdout.split()
    if users:
        raise SystemExit(f'render-node users still present: {users}; halting')


def step4_launch():
    if not (Q / 'PAUSE-A').exists():
        raise SystemExit('PAUSE-A missing; two-card rows need lane A paused')
    pause = Q / f'PAUSE-{LANE}'
    if pause.exists():
        shutil.copy2(pause, OUT / f'PAUSE-{LANE}.archived')
        pause.unlink()
        log(f'PAUSE-{LANE} archived and removed for the approved window (PAUSE-A untouched)')
    if (Q / f'STOP-{LANE}').exists():
        raise SystemExit(f'STOP-{LANE} present; not launching')
    if is_active(UNIT) in ('active', 'activating'):
        raise SystemExit(f'{UNIT} already active')
    log('no waiter (packet58-diet-micro runs no chain; a chain-rule win derives its record bundle as a new packet)')
    cmd = ['systemd-run', '--user', f'--unit={UNIT}', f'--working-directory={ROOT}', '--property=Restart=no',
           '/usr/bin/python3', '-B', 'experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py', 'run', '--lane', LANE]
    cp = sh(cmd)
    log(f'runner launch rc={cp.returncode} {cp.stdout.strip()} {cp.stderr.strip()}')
    if cp.returncode != 0:
        raise SystemExit('runner launch failed')


def step5_watch():
    events = Q / f'events-{LANE}.jsonl'
    offset = events.stat().st_size if events.exists() else 0
    done, seen_start, last_log = set(), set(), 0
    deadline = time.monotonic() + 3 * 3600
    while True:
        if events.exists() and events.stat().st_size > offset:
            with events.open() as f:
                f.seek(offset)
                chunk = f.read()
                offset = f.tell()
            for line in chunk.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                log('EVENT ' + line.strip()[:300])
                ev = row.get('event')
                if ev == 'START':
                    seen_start.add(row['name'])
                elif ev == 'DONE':
                    done.add(row['name'])
                elif ev in TERMINAL:
                    return dict(done=sorted(done), terminal=row)
                elif ev == 'ALERT' and 'lane stopped' in row.get('reason', ''):
                    return dict(done=sorted(done), terminal=row)
        if len(done) == len(ROWS):
            return dict(done=sorted(done), terminal=None)
        state = is_active(UNIT)
        if state not in ('active', 'activating'):
            return dict(done=sorted(done), terminal=dict(event='UNIT-EXIT', state=state))
        if time.monotonic() > deadline:
            return dict(done=sorted(done), terminal=dict(event='WATCH-DEADLINE'))
        if time.monotonic() - last_log > 600:
            log(f'watching: started={sorted(seen_start)} done={sorted(done)} unit={state}')
            last_log = time.monotonic()
        time.sleep(5)


def step5a_wait_waiter():
    deadline = time.monotonic() + 2.5 * 3600
    last = 0
    while is_active(WAITER) in ('active', 'activating'):
        if time.monotonic() > deadline:
            log('waiter still active after 2.5 h; proceeding to close the window (no kill)')
            break
        if time.monotonic() - last > 300:
            try:
                tail = Path(WAITER_LOG).read_text().strip().splitlines()[-1]
            except Exception:
                tail = ''
            log(f'waiting for {WAITER} (confirmation path): {tail[:200]!r}')
            last = time.monotonic()
        time.sleep(15)
    try:
        log('waiter log tail: ' + ' | '.join(Path(WAITER_LOG).read_text().strip().splitlines()[-5:])[:900])
    except Exception as e:
        log(f'waiter log unreadable: {e}')
    log(f'waiter final state: {is_active(WAITER)}')


def step5b_stop_runner():
    if is_active(UNIT) in ('active', 'activating'):
        (Q / f'STOP-{LANE}').write_text(f'window driver stop {now()}\n')
        log(f'STOP-{LANE} written; waiting for the runner to exit at its boundary')
        deadline = time.monotonic() + 900
        while is_active(UNIT) in ('active', 'activating', 'deactivating'):
            if time.monotonic() > deadline:
                log('runner did not exit within 900 s after STOP; leaving it (no kill)')
                break
            time.sleep(5)
    if (Q / f'STOP-{LANE}').exists():
        (Q / f'STOP-{LANE}').unlink()
    (Q / f'PAUSE-{LANE}').write_text('owner pause 2026-10-19T12:02Z: inference server on the cards; no campaign jobs (coordinator)\n'
                                    f'# re-armed by window driver {now()} after the 2026-10-22 packet58-diet-micro window\n')
    log(f'runner unit state: {is_active(UNIT)}; STOP-{LANE} removed; PAUSE-{LANE} re-armed')
    (OUT / 'runner-journal.log').write_text(sh(['journalctl', '--user', '-u', UNIT + '.service', '--no-pager', '-o', 'cat']).stdout)


def step6_restore():
    cmd = ['/usr/bin/python3', '-u', str(SCRATCH / 'restore-endpoints-20261021.py'), RESTORE_SUFFIX]
    log('restoring endpoints: ' + ' '.join(cmd))
    with (OUT / 'restore.out').open('w') as f:
        cp = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, cwd='/home/steve/inference')
    log(f'restore rc={cp.returncode}')
    return cp.returncode


def main():
    log('window start')
    step1_queue()
    step2_plan()
    step3_stop_endpoints()
    result = None
    try:
        step4_launch()
        result = step5_watch()
        log(f'watch result: {json.dumps(result)[:400]}')
    finally:
        try:
            step5b_stop_runner()
        finally:
            rc = step6_restore()
    (OUT / 'window-result.json').write_text(json.dumps(dict(at=now(), result=result, restore_rc=rc), indent=2))
    log('window end')
    return 0 if result and not result['terminal'] and rc == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
