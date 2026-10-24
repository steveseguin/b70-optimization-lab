#!/usr/bin/env python3
"""One coordinator-admitted synthetic run; no application stop/restore or retry."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import observe

P = Path(__file__).resolve().parent
R = observe.ROOT
UNIT = 'gsq-native-formats-a'
STAGE = Path('/home/steve/own-xpu-runtime-results/gsq-native-formats-a')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def status():
    text = observe.command(['systemctl', '--user', 'show', UNIT+'.service',
        '--property=LoadState,ActiveState,SubState,MainPID,Result,ExecMainStatus'])
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def main():
    before = observe.observe()
    assert before['known_fault_baseline_matches'] and before['root_free_bytes'] > 27_250_000_000
    assert before['memory']['MemAvailable'] > 8*1024**3
    assert before['units']['qwen38-27b-fp8']['ActiveState'] == 'inactive'
    target = observe.target_nodes(before, '0000:23:00.0')
    assert before['drm']['renderD130']['bdf'] == '0000:23:00.0'
    assert not before['identity_races']
    assert not any(x['node'] in target for x in before['inventory']['holders'])
    old = json.loads((P/'host-before-stop.json').read_text())
    for unit in ('qwen38-27b-fp8-tp1-test', 'qwen38-27b-vision'):
        assert before['units'][unit] == old['units'][unit]
    assert before['queue'] == old['queue']
    allowed_holders = {(x['pid'], before['holders'][str(x['pid'])]['start_ticks'], x['node'])
                       for x in before['inventory']['holders']}
    old_holders = {(x['pid'], old['holders'][str(x['pid'])]['start_ticks'], x['node'])
                   for x in old['inventory']['holders'] if x['node'] not in target}
    assert allowed_holders == old_holders
    assert status().get('LoadState') == 'not-found'
    assert not STAGE.exists() and not STAGE.is_symlink()
    assert not (Path('/home/steve')/'igdrcl.config').exists()
    assert not (R/'igdrcl.config').exists()
    evidence = R/'experiments/own-xpu-runtime/gsq-rco-iq3s/native-qualification/evidence/compile-only.json'
    proof = json.loads(evidence.read_text())
    assert proof['passed'] and sha(proof['binary']) == proof['binary_sha256']
    for group in ('sources', 'objects', 'dependencies'):
        assert all(sha(p) == h for p, h in proof[group].items())
    STAGE.mkdir(mode=0o700)
    for name in ('sycl', 'neo', 'xdg'):
        (STAGE/name).mkdir(mode=0o700)
    libraries = '/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
    env = dict(HOME='/home/steve', PATH='/usr/bin:/bin', OMP_NUM_THREADS='2', LD_LIBRARY_PATH=libraries,
        NEOReadDebugKeys='1', FilterBdfPath='0000:23:00.0', ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',
        ZE_AFFINITY_MASK='0', ONEAPI_DEVICE_SELECTOR='level_zero:0',
        SYCL_CACHE_DIR=str(STAGE/'sycl'), NEO_CACHE_DIR=str(STAGE/'neo'), XDG_CACHE_HOME=str(STAGE/'xdg'))
    cmd = ['systemd-run', '--user', '--quiet', '--unit='+UNIT,
        '--property=Restart=no', '--property=SendSIGKILL=no', '--property=KillMode=process',
        '--property=TimeoutStopSec=infinity', '--property=LimitAS=infinity', '--property=LimitCORE=0',
        '--property=UMask=0077', '--property=WorkingDirectory='+str(R),
        '/usr/bin/env', '-i', *[k+'='+v for k, v in env.items()], '/usr/bin/taskset', '-c', '0-3,16-19',
        proof['binary'], '--run', '--card', '0', '--output', str(STAGE/'result')]
    admission = dict(before=before, command=cmd, proof_sha256=sha(evidence), binary_sha256=proof['binary_sha256'],
        monitor_sha256=sha(__file__), observer_sha256=sha(observe.__file__), target=target, scope='synthetic format correctness only; no model or benchmark', retry=False)
    (STAGE/'admission.json').write_text(json.dumps(admission, indent=2)+'\n')
    # From this point a failed/timeout launcher may still have created the unit.
    # No exception may abandon monitoring or start another owner.
    signalled = False
    first_error = None
    native_identity = None
    observed_native_target_fd = False
    start = time.monotonic()
    last_report = start
    samples = []

    def latch(error):
        nonlocal first_error
        if first_error is None:
            first_error = str(error) or type(error).__name__

    try:
        subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, timeout=30)
    except BaseException as ex:
        latch('launch outcome uncertain: '+repr(ex))

    while True:
        state = None
        snapshot = None
        observation_complete = False
        native_holders = []
        try:
            state = status()
            snapshot = observe.observe()
            if snapshot['identity_races']:
                raise RuntimeError('passive PID identity raced; sample inconclusive')
            if observe.target_nodes(snapshot, '0000:23:00.0') != target:
                raise RuntimeError('target alias/dev_t mapping changed')
            if not snapshot['known_fault_baseline_matches']:
                latch('kernel fault baseline changed; halt new work')
            if snapshot['queue'] != before['queue']:
                latch('coordination changed')
            for unit in ('qwen38-27b-fp8-tp1-test', 'qwen38-27b-vision'):
                if snapshot['units'][unit] != before['units'][unit]:
                    latch('preserved application identity/state changed: '+unit)
            pid = int(state.get('MainPID', 0))
            if pid:
                identity = observe.process_identity(pid)
                if identity is None:
                    raise RuntimeError('native process disappeared during sample')
                current = (pid, identity['start_ticks'])
                if native_identity is None:
                    native_identity = current
                elif native_identity != current:
                    latch('native PID/start ticks changed')
            for holder in snapshot['inventory']['holders']:
                identity = snapshot['holders'][str(holder['pid'])]
                key = (holder['pid'], identity['start_ticks'])
                if native_identity is not None and key == native_identity:
                    native_holders.append(holder)
                    if holder['node'] not in target:
                        latch('unexpected native physical device contact')
                    else:
                        observed_native_target_fd = True
                elif (key[0], key[1], holder['node']) not in allowed_holders:
                    latch('unexpected competing device holder')
            if time.monotonic()-start > 180 and state.get('ActiveState') in ('active', 'activating', 'deactivating'):
                latch('synthetic qualification exceeded180s; cooperative stop')
            observation_complete = True
        except BaseException as ex:
            latch('monitor failure: '+repr(ex))
            # A partial/inconclusive observation cannot establish drain.

        try:
            samples.append(dict(elapsed=time.monotonic()-start, state=state,
                snapshot=snapshot, observation_complete=observation_complete,
                native_holders=native_holders, first_error=first_error))
            if first_error is not None and not (STAGE/'first-error.json').exists():
                (STAGE/'first-error.json').write_text(json.dumps(samples[-1], indent=2)+'\n')
            # Retained owners may wait indefinitely; bound monitor RAM/disk.
            samples = samples[-256:]
            (STAGE/'monitor.json').write_text(json.dumps(dict(samples=samples,
                single_term_attempted=signalled, first_error=first_error,
                native_identity=native_identity, observed_native_target_fd=observed_native_target_fd), indent=2)+'\n')
        except BaseException as ex:
            latch('monitor evidence failure: '+repr(ex))

        if first_error is not None and not signalled:
            # Mark BEFORE calling: even a timeout/error must not cause a retry.
            signalled = True
            try:
                subprocess.run(['systemctl', '--user', 'kill', '--kill-whom=main',
                    '--signal=SIGTERM', UNIT+'.service'], check=True, timeout=30,
                    stdin=subprocess.DEVNULL)
            except BaseException as ex:
                try:
                    (STAGE/'signal-error.json').write_text(json.dumps({'error':repr(ex), 'first_error':first_error})+'\n')
                except BaseException:
                    pass

        try:
            ended = state is not None and (state.get('ActiveState') in ('inactive', 'failed')
                or state.get('LoadState') == 'not-found') and int(state.get('MainPID', 0)) == 0
            clear = observation_complete and not any(x['node'] in target for x in snapshot['inventory']['holders'])
            if ended and clear:
                result_path = STAGE/'result/result.json'
                result = None
                if result_path.exists():
                    try:
                        result = json.loads(result_path.read_text())
                    except (OSError, ValueError) as ex:
                        latch('terminal result unavailable: '+repr(ex))
                passed = bool(first_error is None and not signalled and state.get('Result') == 'success'
                    and state.get('ExecMainStatus') == '0' and result
                    and result.get('passed') and result.get('safe_to_exit'))
                final = dict(passed=passed, result=result, status=state,
                    target_descriptors_empty=clear, after=snapshot,
                    single_term_attempted=signalled, first_error=first_error,
                    native_identity=native_identity, observed_native_target_fd=observed_native_target_fd,
                    qualification_limit=None if observed_native_target_fd else
                        'Native target FD not observed; short-run physical identity is not independently attested.',
                    duration=time.monotonic()-start)
                (STAGE/'terminal.json').write_text(json.dumps(final, indent=2)+'\n')
                try:
                    print(json.dumps(dict(passed=passed, terminal=str(STAGE/'terminal.json'),
                        duration=final['duration'], observed_native_target_fd=observed_native_target_fd)), flush=True)
                except BaseException:
                    pass
                return 0 if passed else 1
        except BaseException as ex:
            latch('terminal evidence failure: '+repr(ex))
        try:
            if time.monotonic()-last_report > 20:
                print(json.dumps(dict(elapsed=time.monotonic()-start, state=state,
                    first_error=first_error, single_term_attempted=signalled)), flush=True)
                last_report=time.monotonic()
            time.sleep(0.5)
        except BaseException as ex:
            latch('monitor wait/report failure: '+repr(ex))


if __name__ == '__main__':
    if sys.argv[1:] != ['--run']:
        raise SystemExit('Explicit --run required; coordinator admission only')
    raise SystemExit(main())
