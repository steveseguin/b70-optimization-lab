#!/usr/bin/env python3
"""CPU rehearsal of packet182's win-path chain derivation in a scratch repo root.

Nothing here writes into the real stage2/ or ops/ trees except this packet's
evidence/chain-rehearsal.json; nothing launches, queues or touches a device
(the device binary runs only with --help inside ops/entry_sandbox.py, as the
generator's help gate always does).

Scratch root R (removed afterwards; under the session scratchpad by default):
  R/experiments/own-xpu-runtime/stage2 and ops are real directories whose entries
  are symlinks to the real ones, except
  - ops/lane-queue: a real directory with real copies of lanequeue.py and
    pin_guard.py, so the generator's temporary lanequeue plan and pin guard
    resolve their root to R and check R's packets;
  - stage2/packet176c-chain: a real byte copy (checks below write scratch
    output into a packet's own evidence/ directory).
Steps (each recorded):
  1. script_argv_check on the R copy of packet176c-chain: MUST FAIL (no chain
     flag reaches the native argv: the chain-176-a defect).
  2. chain/derive_chain.py in R with the production names (packet182c-chain,
     packet182c-orchestration, unit packet58-onecard-182-a, evidence/card0-182-a),
     this packet's device/host binaries, flags wait-policy=spin and
     foreground-io=kernel, --cpu-rehearsal and a STAND-IN winning bracket (the
     tracked packet58as v5 summary; packet182's own bracket is the device output
     this rehearsal cannot have). The real packet58as summary bytes are placed in a
     scratch-only fake packet R/stage2/packet182zz-standin with a SYNTHETIC window
     receipt (passed, returncode 0, no stop reasons, current boot): the original
     packet58as window.json was removed with the untracked files on 2026-10-19
     21:42 EDT. Synthetic receipts never leave R. The generator runs its bracket, help, parser,
     pin-relocation, seal, verify_ready, pin-audit, closure, pre-device and
     temporary-plan gates; the post-native gate is the derive_chain.py carry.
  3. On the derived packet: script_argv_check (MUST PASS on all five windows);
     ops/onecard_chain_derive.py --predevice-check, --closure-check and
     --postnative-check (the last is expected to refuse: no completed one-card
     chain evidence exists on this host; recorded, not hidden).
"""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
REPO = PACKET.parents[3]
X = 'experiments/own-xpu-runtime'
STAND_IN = f'{X}/stage2/packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/summary.json'
FLAGS = {'--wait-policy': 'spin', '--foreground-io': 'kernel'}
REAL_COPIES = ('suite-inputs-20261012',)
STAND_IN_PACKET = 'packet182zz-standin'
STAND_IN_DIR = f'{X}/stage2/{STAND_IN_PACKET}/screen/evidence/card0-standin-v5-a/resident/WSCREEN'
SCRATCH = Path('/tmp/claude-1000/-home-steve/1df77db8-272b-4a21-9a32-d0349da3fe39/scratchpad')


def run(argv, cwd, timeout=3600):
    t = time.monotonic()
    cp = subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
                        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return dict(argv=[str(a).replace(str(cwd), '<R>') for a in argv], returncode=cp.returncode,
                seconds=round(time.monotonic() - t, 1),
                stdout_tail=cp.stdout[-3000:].replace(str(cwd), '<R>'), stderr_tail=cp.stderr[-3000:].replace(str(cwd), '<R>'))


def scratch_root(base):
    R = base / 'repo'
    for rel in (f'{X}/stage2', f'{X}/ops'):
        (R / rel).mkdir(parents=True)
        for entry in (REPO / rel).iterdir():
            if rel.endswith('ops') and entry.name == 'lane-queue':
                continue
            if rel.endswith('stage2') and entry.name in ('packet176c-chain', *REAL_COPIES):
                continue
            (R / rel / entry.name).symlink_to(entry)
    for name in REAL_COPIES:  # oracle_inputs() requires the input bundles to resolve inside its root
        shutil.copytree(REPO / f'{X}/stage2' / name, R / f'{X}/stage2' / name, symlinks=False)
    lq = R / f'{X}/ops/lane-queue'
    lq.mkdir()
    for name in ('lanequeue.py', 'pin_guard.py'):
        shutil.copy2(REPO / f'{X}/ops/lane-queue' / name, lq / name)
    shutil.copytree(REPO / f'{X}/stage2/packet176c-chain', R / f'{X}/stage2/packet176c-chain', symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    for entry in REPO.iterdir():
        if entry.name not in ('experiments', '.git'):
            (R / entry.name).symlink_to(entry)
    (R / 'experiments').joinpath('own-xpu-runtime')  # real dirs created above
    for entry in (REPO / 'experiments').iterdir():
        if entry.name != 'own-xpu-runtime':
            (R / 'experiments' / entry.name).symlink_to(entry)
    for entry in (REPO / X).iterdir():
        if entry.name not in ('stage2', 'ops'):
            (R / X / entry.name).symlink_to(entry)
    stand = R / STAND_IN_DIR
    stand.mkdir(parents=True)
    shutil.copy2(REPO / STAND_IN, stand / 'summary.json')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    (stand / 'window.json').write_text(json.dumps(dict(passed=True, returncode=0, stop_reasons=[], boot_id=boot,
                                                       synthetic_rehearsal_receipt=True, device_executed=False)) + '\n')
    return R


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop: 27 GB root floor'
    base = Path(tempfile.mkdtemp(prefix='p182-chain-rehearsal-', dir=SCRATCH if SCRATCH.is_dir() else None))
    record = dict(schema='packet182.chain-rehearsal.v1', device_executed=False, flags=FLAGS,
                  stand_in_bracket=dict(summary_bytes_from=STAND_IN, placed_at='<R>/' + STAND_IN_DIR,
                                        window_receipt='synthetic, scratch only (original removed 2026-10-19 21:42 EDT)'),
                  scratch_root='<R> (removed)', production_names=dict(packet='packet182c-chain', out='packet182c-orchestration',
                  unit='packet58-onecard-182-a', output='evidence/card0-182-a'))
    try:
        R = scratch_root(base)
        S = R / f'{X}/stage2'
        old = S / 'packet176c-chain'
        check = [sys.executable, '-B', str(HERE / 'script_argv_check.py')]
        r1 = run(check + [str(old), '--flags', json.dumps(FLAGS), '--json', str(base / 'old.json')], R)
        old_row = json.loads((base / 'old.json').read_text()) if (base / 'old.json').is_file() else None
        record['packet176c_script_mode'] = dict(run=r1, expected='refuse', refused=r1['returncode'] == 3,
                                                failures=old_row and old_row['failures'],
                                                argv_example=old_row and old_row['windows'] and old_row['windows'][-1]['native_argv'][-8:])
        derive = [sys.executable, '-B', str(HERE / 'derive_chain.py'),
                  '--parent-orch', str(R / f'{X}/ops/packet58aj-orchestration'),
                  '--packet', str(S / 'packet182c-chain'), '--out', str(R / f'{X}/ops/packet182c-orchestration'),
                  '--unit', 'packet58-onecard-182-a', '--output', 'evidence/card0-182-a',
                  '--binary', str(PACKET / 'build/device/own-rt-iq3'), '--host-binary', str(PACKET / 'build/gnu-host/own-rt-iq3'),
                  '--bracket-summary', str(R / STAND_IN_DIR / 'summary.json'), '--threshold-file', str(R / 'scripts/packet58_onecard_record_threshold.json'),
                  '--cpu-rehearsal', '--flag', 'wait-policy=spin', '--flag', 'foreground-io=kernel']
        r2 = run(derive, R)
        record['derive'] = dict(run=r2, passed=r2['returncode'] == 0)
        P = S / 'packet182c-chain'
        O = R / f'{X}/ops/packet182c-orchestration'
        if r2['returncode'] == 0:
            ready = json.loads((O / 'READY-FOR-DEVICE.json').read_text())
            post = json.loads((O / 'postnative-rehearsal.json').read_text())
            sd = (P / 'suite_driver.py').read_text()
            record['derived'] = dict(
                ready_for_device_chain=ready['ready_for_device_chain'], chain_binary_sha256=ready['chain_binary_sha256'],
                chain_flags=ready['chain_flags'], pin_audit=ready['pin_audit'], predevice_rehearsal=ready['predevice_rehearsal'],
                runtime_closure_check=ready['runtime_closure_check'], postnative_rehearsal=ready['postnative_rehearsal'],
                postnative_carried=post.get('carried'), confirmation_run=ready['confirmation_run'],
                confirmation_note='stand-in bracket packet is scratch-only (not the ledger record packet) and the binary differs from '
                                  'packet58as: not a confirmation, as on the device day',
                flag_block_before_entry=sd.index('# >>> onecard_chain_derive generated chain flags') < sd.index("if __name__=='__main__':"),
                chain_command_unit_ok='--unit=packet58-onecard-182-a ' in ready['chain_command'])
            r3 = run(check + [str(P), '--json', str(base / 'new.json')], R)
            new_row = json.loads((base / 'new.json').read_text()) if (base / 'new.json').is_file() else None
            record['derived_script_mode'] = dict(run=r3, expected='pass', passed=r3['returncode'] == 0,
                                                 windows=new_row and [dict(window=w['window'], flags_present=w['flags_present'],
                                                                           argv_tail=w['native_argv'][-6:]) for w in new_row['windows']])
            gen = [sys.executable, '-B', str(REPO / f'{X}/ops/onecard_chain_derive.py')]
            checks = {}
            for mode in ('--predevice-check', '--closure-check', '--postnative-check'):
                checks[mode] = run(gen + [mode, str(P)], R)
            record['generator_checks'] = dict(
                predevice=dict(passed=checks['--predevice-check']['returncode'] == 0, run=checks['--predevice-check']),
                closure=dict(passed=checks['--closure-check']['returncode'] == 0, run=checks['--closure-check']),
                postnative=dict(passed=checks['--postnative-check']['returncode'] == 0, run=checks['--postnative-check'],
                                expected='refuse without completed one-card chain evidence on this host; derive_chain carries packet176c instead'))
        ok = (record['packet176c_script_mode']['refused'] and record['derive']['passed']
              and record.get('derived', {}).get('flag_block_before_entry') is True
              and record.get('derived_script_mode', {}).get('passed') is True
              and record.get('generator_checks', {}).get('predevice', {}).get('passed') is True
              and record.get('generator_checks', {}).get('closure', {}).get('passed') is True
              and record.get('derived', {}).get('postnative_carried') is not None)
        record['passed'] = bool(ok)
        import hashlib
        def h(f):
            with open(f, 'rb') as s:
                return hashlib.file_digest(s, 'sha256').hexdigest()
        record['tools'] = [dict(relpath=str(f.relative_to(REPO)), digest=h(f)) for f in (
            HERE / 'derive_chain.py', HERE / 'script_argv_check.py', HERE / 'rehearse_chain.py',
            REPO / f'{X}/ops/onecard_chain_derive.py', REPO / f'{X}/ops/lane-queue/pin_guard.py', REPO / f'{X}/ops/lane-queue/lanequeue.py',
            PACKET / 'build/device/own-rt-iq3', PACKET / 'build/gnu-host/own-rt-iq3')]
    finally:
        shutil.rmtree(base, ignore_errors=True)
    (PACKET / 'evidence').mkdir(exist_ok=True)
    (PACKET / 'evidence/chain-rehearsal.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=record['passed'], derive=record['derive']['passed'],
                          old_refused=record['packet176c_script_mode']['refused'],
                          new_script_mode=record.get('derived_script_mode', {}).get('passed'),
                          checks={k: v['passed'] for k, v in record.get('generator_checks', {}).items()})))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
