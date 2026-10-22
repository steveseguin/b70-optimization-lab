#!/usr/bin/env python3
"""CPU rehearsal of the whole win-path waiter (chain/p182-win.sh) in a scratch repo root, dry run.

Nothing is launched, locked, paused or queued: P182_DRY_RUN=1 makes the waiter stop right
after `p182-chain.sh --check`, before it would take fn-run/onecard-hold.lock, set QUIET or
run the chain launcher; FN points at a scratch directory. Scratch root R (removed after):
stage2/ and ops/ hold symlinks to the real entries, except
  - stage2/packet182-onecard-kio-rebracket: a real byte copy (the synthetic bracket below is
    written into ITS evidence tree, never into the real packet, whose device output stays fresh);
  - stage2/suite-inputs-20261012: a real copy (oracle_inputs() needs bundles inside the root);
  - ops/lane-queue: real copies of lanequeue.py and pin_guard.py plus a scratch events-A.jsonl.
Cases (each a fresh R):
  win     synthetic summary = the real packet58as v5 summary (60 exact real requests) with the
          packet176 bracket rates/gain, synthetic window.json on the CURRENT boot (the waiter derives
          without --cpu-rehearsal, so verify_ready's same-boot rule is exercised), events DONE
          -> expect exit 0 and the log through 'dry run' (derive, script mode, predevice, closure,
          postnative logged, chain --check);
  below   same with rates giving +1.93% -> expect 'no chain (chain rule not met)', exit 0, no derive;
  failed  events FAILED -> expect exit 2, no derive;
  endpoints  the win case while the REAL owner unit qwen38-27b-fp8 is active (read-only is-active)
          -> expect exit 5 and no derive (skipped, and said so, if the unit is not active).
The win/below/failed cases point P182_ENDPOINT_UNITS at a unit name that does not exist.
Writes evidence/waiter-rehearsal.json.
"""
import copy, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
REPO = PACKET.parents[3]
X = 'experiments/own-xpu-runtime'
SCRATCH = Path('/tmp/claude-1000/-home-steve/1df77db8-272b-4a21-9a32-d0349da3fe39/scratchpad')
SOURCE = REPO / f'{X}/stage2/packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/summary.json'
P176_RATES = [34.20898070237056, 35.98180647418397, 34.62115621015788, 35.98079731582723, 34.64021031336306]
JOB = 'packet182-one-card-v5-A'


def build_root(base):
    R = base / 'repo'
    for rel in (f'{X}/stage2', f'{X}/ops'):
        (R / rel).mkdir(parents=True)
        for e in (REPO / rel).iterdir():
            if e.name in ('lane-queue', PACKET.name, 'suite-inputs-20261012'):
                continue
            (R / rel / e.name).symlink_to(e)
    lq = R / f'{X}/ops/lane-queue'; lq.mkdir()
    for n in ('lanequeue.py', 'pin_guard.py'):
        shutil.copy2(REPO / f'{X}/ops/lane-queue' / n, lq / n)
    shutil.copytree(REPO / f'{X}/stage2/suite-inputs-20261012', R / f'{X}/stage2/suite-inputs-20261012')
    shutil.copytree(PACKET, R / f'{X}/stage2' / PACKET.name, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', 'preparation-sequence', 'preparation182'))
    for e in REPO.iterdir():
        if e.name not in ('experiments', '.git'):
            (R / e.name).symlink_to(e)
    for e in (REPO / 'experiments').iterdir():
        if e.name != 'own-xpu-runtime':
            (R / 'experiments' / e.name).symlink_to(e)
    for e in (REPO / X).iterdir():
        if e.name not in ('stage2', 'ops'):
            (R / X / e.name).symlink_to(e)
    return R


def bracket(R, rates, gain):
    d = R / f'{X}/stage2' / PACKET.name / 'screen/evidence/card0-182-v5-a/resident/WSCREEN'
    d.mkdir(parents=True)
    s = json.loads(SOURCE.read_text())
    s.update(rates=rates, minimum_gain_vs_best_control=gain, candidate_beats_all_controls=True, control_drift_passed=True,
             control_drift_fraction=0.0005503601061015261, passed=True, device_executed=True,
             synthetic_rehearsal_summary='real packet58as v5 requests (60 exact) with packet176 bracket rates; scratch only')
    (d / 'summary.json').write_text(json.dumps(s, indent=1))
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    (d / 'window.json').write_text(json.dumps(dict(passed=True, returncode=0, stop_reasons=[], boot_id=boot, synthetic_rehearsal_receipt=True)))


def case(name, rates, gain, event, endpoints='p182-rehearsal-no-such-unit'):
    base = Path(tempfile.mkdtemp(prefix=f'p182-waiter-{name}-', dir=SCRATCH if SCRATCH.is_dir() else None))
    try:
        R = build_root(base)
        fn = base / 'fn'; fn.mkdir()
        if rates:
            bracket(R, rates, gain)
        ev = R / f'{X}/ops/lane-queue/events-A.jsonl'
        ev.write_text(json.dumps(dict(event='START', lane='A', name=JOB, utc='rehearsal')) + '\n' +
                      json.dumps(dict(event=event, lane='A', name=JOB, utc='rehearsal', rc=0 if event == 'DONE' else 1)) + '\n')
        env = dict(os.environ, P182_REPO=str(R), P182_DRY_RUN='1', FN=str(fn), LOG=str(fn / 'p182-win.log'), PYTHONDONTWRITEBYTECODE='1',
                   P182_ENDPOINT_UNITS=endpoints)
        t = time.monotonic()
        # The waiter sleeps 30 s after the terminal event before reading the summary (as on the device day).
        cp = subprocess.run(['/usr/bin/bash', str(R / f'{X}/stage2' / PACKET.name / 'chain/p182-win.sh')], cwd=R,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3600, env=env)
        log = (fn / 'p182-win.log').read_text() if (fn / 'p182-win.log').is_file() else ''
        derived = (R / f'{X}/stage2/packet182c-chain/READY-FOR-DEVICE.json').is_file()
        quiet_or_lock = (fn / 'QUIET').exists() or (fn / 'onecard-hold.lock').exists()
        argv_ok = None
        sa = R / f'{X}/stage2/packet182c-chain/evidence/script-argv-check.json'
        if sa.is_file():
            argv_ok = json.loads(sa.read_text())['passed']
        lines = [l.split(' ', 1)[1].replace(str(R), '<R>') for l in log.splitlines() if ' p182-' in l]
        return dict(case=name, returncode=cp.returncode, seconds=round(time.monotonic() - t, 1), derived_packet=derived,
                    script_argv_check=argv_ok, quiet_or_lock_touched=quiet_or_lock, log=lines[-14:],
                    stderr_tail=cp.stderr[-400:].replace(str(R), '<R>'))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000
    win = case('win', P176_RATES, 0.03870031360482287, 'DONE')
    below = case('below', [34.2, 35.30, 34.62, 35.31, 34.64], 0.0193, 'DONE')
    failed = case('failed', None, None, 'FAILED')
    # Endpoint guard on the REAL owner unit (read-only systemctl is-active): while it runs, no chain.
    live = subprocess.run(['systemctl', '--user', 'is-active', 'qwen38-27b-fp8'], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL).stdout.strip()
    endpoints = case('endpoints', P176_RATES, 0.03870031360482287, 'DONE', endpoints='qwen38-27b-fp8') if live == 'active' else \
        dict(case='endpoints', skipped=True, reason='qwen38-27b-fp8 not active during the rehearsal')
    ok = (win['returncode'] == 0 and win['derived_packet'] and win['script_argv_check'] is True and not win['quiet_or_lock_touched']
          and any('dry run' in l for l in win['log']) and not any('ALERT' in l for l in win['log'])
          and below['returncode'] == 0 and not below['derived_packet'] and any('chain rule not met' in l for l in below['log'])
          and failed['returncode'] == 2 and not failed['derived_packet']
          and (endpoints.get('skipped') or (endpoints['returncode'] == 5 and not endpoints['derived_packet']
                                            and any('endpoint qwen38-27b-fp8 is active' in l for l in endpoints['log']))))
    import hashlib
    def h(f):
        with open(f, 'rb') as s:
            return hashlib.file_digest(s, 'sha256').hexdigest()
    row = dict(schema='packet182.waiter-rehearsal.v1', passed=bool(ok), device_executed=False, dry_run=True,
               launched=False, lock_or_quiet_touched=False, pause_files_touched=False, cases=[win, below, failed, endpoints],
               tools=[dict(relpath=str(f.relative_to(REPO)), digest=h(f)) for f in (HERE / 'p182-win.sh', HERE / 'p182-chain.sh', HERE / 'chain_gate.py',
                      HERE / 'derive_chain.py', HERE / 'script_argv_check.py', HERE / 'rehearse_waiter.py', REPO / f'{X}/ops/onecard_chain_derive.py')])
    (PACKET / 'evidence/waiter-rehearsal.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=row['passed'], win=[win['returncode'], win['derived_packet'], win['script_argv_check']],
                          below=below['returncode'], failed=failed['returncode'], endpoints=endpoints.get('returncode', 'skipped'))))
    return 0 if row['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
