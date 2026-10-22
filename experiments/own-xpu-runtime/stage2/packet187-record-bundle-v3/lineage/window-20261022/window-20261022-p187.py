#!/usr/bin/env python3
"""Two-card record-chain window (2026-10-22): packet187 (bundle 8 + V3 + static) on lane A (cards 0+1).

Sequence (halts on any failure; never retries, never restarts the host or drivers):
 1. require PAUSE-B present, no lane/window/chain units active, no lane markers;
 2. stop the three daily endpoints gracefully; wait until inactive; require MemAvailable and root free;
 3. archive + remove PAUSE-A (PAUSE-B stays); `launch_chain.sh --dry-run` must pass; then `launch_chain.sh`
    (it runs ready.json's exact systemd-run command, unit packet187-chain-a);
 4. wait until the unit is no longer active (deadline 3 h), logging queue-state.json progress;
 5. re-create PAUSE-A; restore the endpoints (restore-endpoints-20261021.py <suffix>).
Receipts: <scratch>/window-20261022-p187/.
"""
import json, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
Q = ROOT / 'experiments/own-xpu-runtime/ops/lane-queue'
O = ROOT / 'experiments/own-xpu-runtime/ops/packet187-orchestration'
OUTDIR = ROOT / 'experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/build/device-cards01-p187-a'
SCRATCH = Path(__file__).resolve().parent
OUT = SCRATCH / 'window-20261022-p187'
OUT.mkdir(exist_ok=True)
UNIT = 'packet187-chain-a'
ENDPOINTS = ['qwen38-27b-vision', 'qwen38-27b-fp8-tp1-test', 'qwen38-27b-fp8']
RESTORE_SUFFIX = sys.argv[1] if len(sys.argv) > 1 else '20261022-restore11'
REQUIRED_MEM = 107667817956 + 1024 ** 3
REQUIRED_ROOT = 25000000000 + 3324718708
CHAIN_DEADLINE_S = 3 * 3600


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


def root_free():
    st = shutil.disk_usage('/')
    return st.free


def step1_preconditions():
    if not (Q / 'PAUSE-B').exists():
        raise SystemExit('PAUSE-B missing; the chain needs lane B paused')
    busy = sh(['systemctl', '--user', 'list-units', '--no-legend', '--plain', '--state=active,activating',
               'lanequeue-*', 'window-*', 'packet187-chain-a*']).stdout.split()
    busy = [u for u in busy if u.endswith('.service') and not u.startswith('window-p187-driver')]
    if busy:
        raise SystemExit(f'active lane/window/chain units: {busy}')
    markers = [p for p in Q.glob('inflight-*.json')] + [p for p in Q.glob('active-lane-*.json')]
    if markers:
        raise SystemExit(f'lane markers present: {markers}')
    if OUTDIR.exists():
        raise SystemExit(f'chain output {OUTDIR} exists; never reuse')
    log('preconditions ok (PAUSE-B present, no busy units, no markers, fresh output)')


def step2_stop_endpoints():
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
    avail, free = mem_available(), root_free()
    log(f'endpoints stopped; MemAvailable={avail} required={REQUIRED_MEM}; root free={free} required={REQUIRED_ROOT}')
    if avail < REQUIRED_MEM:
        raise SystemExit(f'MemAvailable {avail} < required {REQUIRED_MEM}; halting')
    if free < REQUIRED_ROOT:
        raise SystemExit(f'root free {free} < required {REQUIRED_ROOT}; halting')
    users = sh(['bash', '-c', 'for p in /proc/[0-9]*; do ls -l $p/fd 2>/dev/null | grep -q renderD && echo $(basename $p); done']).stdout.split()
    if users:
        raise SystemExit(f'render-node users still present: {users}; halting')


def step3_launch():
    pause = Q / 'PAUSE-A'
    if pause.exists():
        shutil.copy2(pause, OUT / 'PAUSE-A.archived')
        pause.unlink()
        log('PAUSE-A archived and removed for the approved chain window (PAUSE-B untouched)')
    cp = sh(['bash', str(O / 'launch_chain.sh'), '--dry-run'], cwd=str(ROOT))
    (OUT / 'launch-dry-run.log').write_text(cp.stdout + cp.stderr)
    log(f'launch_chain.sh --dry-run rc={cp.returncode} {(cp.stdout + cp.stderr).strip()[-300:]!r}')
    if cp.returncode != 0:
        raise SystemExit('dry run refused; not launching')
    cp = sh(['bash', str(O / 'launch_chain.sh')], cwd=str(ROOT))
    (OUT / 'launch.log').write_text(cp.stdout + cp.stderr)
    log(f'launch_chain.sh rc={cp.returncode} {(cp.stdout + cp.stderr).strip()[-300:]!r}')
    if cp.returncode != 0:
        raise SystemExit('launch refused or unit not active; no retry')
    log(f'unit {UNIT} state={is_active(UNIT)}')


def step4_wait_chain():
    deadline = time.monotonic() + CHAIN_DEADLINE_S
    last_log, last_completed = 0, None
    while True:
        state = is_active(UNIT)
        completed = None
        try:
            qs = json.loads((OUTDIR / 'queue-state.json').read_text())
            completed = qs.get('completed')
        except Exception:
            pass
        if completed != last_completed:
            log(f'queue-state completed={completed}')
            last_completed = completed
        if state not in ('active', 'activating'):
            log(f'unit {UNIT} state={state}')
            break
        if time.monotonic() > deadline:
            log('chain deadline (3 h) reached; leaving the unit alone (no kill) and closing the window')
            break
        if time.monotonic() - last_log > 600:
            log(f'waiting: unit={state} completed={completed}')
            last_log = time.monotonic()
        time.sleep(15)
    done = (OUTDIR / 'queue-all-complete.json').exists()
    log(f'queue-all-complete.json present: {done}')
    (OUT / 'chain-journal.log').write_text(sh(['journalctl', '--user', '-u', UNIT + '.service', '--no-pager', '-o', 'cat']).stdout)
    return dict(state=is_active(UNIT), all_complete=done, completed=last_completed)


def step5_rearm_and_restore():
    if is_active(UNIT) in ('active', 'activating'):
        log('chain unit still active; not restoring endpoints under it (no kill); PAUSE-A re-armed only')
        (Q / 'PAUSE-A').write_text('owner pause 2026-10-19T12:02Z: inference server on the cards; no campaign jobs (coordinator)\n'
                                  f'# re-armed by window driver {now()} after the 2026-10-22 packet187 chain window (unit still active)\n')
        return 3
    (Q / 'PAUSE-A').write_text('owner pause 2026-10-19T12:02Z: inference server on the cards; no campaign jobs (coordinator)\n'
                              f'# re-armed by window driver {now()} after the 2026-10-22 packet187 chain window\n')
    log('PAUSE-A re-armed')
    cmd = ['/usr/bin/python3', '-u', str(SCRATCH / 'restore-endpoints-20261021.py'), RESTORE_SUFFIX]
    log('restoring endpoints: ' + ' '.join(cmd))
    with (OUT / 'restore.out').open('w') as f:
        cp = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, cwd='/home/steve/inference')
    log(f'restore rc={cp.returncode}')
    return cp.returncode


def main():
    log('window start')
    step1_preconditions()
    step2_stop_endpoints()
    result = None
    try:
        step3_launch()
        result = step4_wait_chain()
        log(f'chain result: {json.dumps(result)}')
    finally:
        rc = step5_rearm_and_restore()
    (OUT / 'window-result.json').write_text(json.dumps(dict(at=now(), result=result, restore_rc=rc), indent=2))
    log('window end')
    return 0 if result and result.get('all_complete') and rc == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
