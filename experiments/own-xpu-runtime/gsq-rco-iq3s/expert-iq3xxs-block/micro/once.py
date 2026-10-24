#!/usr/bin/env python3
"""One coordinator-admitted fixed real-weight micro; no application stop/restore or retry."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import argparse, importlib.util, signal
HERE=Path(__file__).resolve().parent
LANE=HERE.parents[1]
assert hashlib.sha256((LANE/"operating/observe.py").read_bytes()).hexdigest()=="fcd0740e64ab7701885f1b57f5bffb523219ed88b41202d9b2cee990c6e1dfef"
spec=importlib.util.spec_from_file_location("micro_observe",LANE/"operating/observe.py")
observe=importlib.util.module_from_spec(spec);spec.loader.exec_module(observe)

P = HERE
R = observe.ROOT
UNIT = 'gsq-iq3xxs-block-micro-a'
STAGE = Path('/home/steve/own-xpu-runtime-results/gsq-iq3xxs-block-micro-a')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def status():
    text = observe.command(['systemctl', '--user', 'show', UNIT+'.service',
        '--property=LoadState,ActiveState,SubState,MainPID,Result,ExecMainStatus,Restart,SendSIGKILL,KillMode,TimeoutStopUSec,LimitAS,LimitCORE,Nice'])
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


STOP=[]
MARKERS=tuple(Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')/n for n in ('active-lane-A.json','active-lane-B.json','hold-lane-B'))
BASELINE=LANE/'operating/host-after-model-stop.json'
BUILD=P/'evidence/native-build.json'
REVIEW=P/'evidence/independent-review.json'
SAFE={'Restart':'no','SendSIGKILL':'no','KillMode':'process','TimeoutStopUSec':'infinity','LimitAS':'infinity','LimitCORE':'0','Nice':'19'}
def coordination_clear():
    assert not any(os.path.lexists(p) for p in MARKERS),'coordination marker remains'
def build_plan():
    manifest=json.loads((P/'manifest.json').read_text())
    for p,h in manifest['authority'].items():assert sha(p)==h,p
    proof=json.loads(BUILD.read_text());review=json.loads(REVIEW.read_text())
    assert proof['passed'] and review['passed'] and sha(proof['binary'])==proof['binary_sha256']==review['binary_sha256'] and sha(BUILD)==review['native_build_sha256']
    for group in ('source_sha256','objects_reused','dependencies'):
        for p,h in proof[group].items():assert sha(p)==h,p
    for p,h in review['source_sha256'].items():assert sha(R/p)==h,p
    storage=LANE/'storage/evidence/complete.json';closed=json.loads(storage.read_text());assert closed['passed'] and len(closed['batches'])==27
    baseline=json.loads(BASELINE.read_text());assert baseline['known_fault_baseline_matches'] and not baseline['identity_races']
    assert baseline['holders']['3487303']['start_ticks']==63453537
    for name in ('qwen38-27b-fp8','qwen38-27b-fp8-tp1-test'):assert baseline['units'][name]['ActiveState']=='inactive'
    files=[P.parent/'selection.json',P.parent/'evidence/cpu-proof.json',P/'evidence/extraction.json',P.parent/'micro-plan.json',LANE/'qkv-q6-p33/micro/once.py',LANE/'qkv-q6-p33/micro/evidence/independent-wrapper-review.json',LANE/'qkv-q6-p33/micro/evidence/device-a/review.json',R/'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py',R/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py',LANE/'operating/host-before-stop.json',Path(__file__),LANE/'operating/observe.py',LANE/'operating/qualify_once.py',BASELINE,BUILD,REVIEW,P/'manifest.json',storage,LANE/'storage/evidence/post-archive-host.json']
    return dict(schema='gsq.iq3xxs-block-micro-once-plan.v1',unit=UNIT,stage=str(STAGE),binary=proof['binary'],binary_sha256=proof['binary_sha256'],source_sha256={str(p):sha(p) for p in files},target_bdf='0000:23:00.0',empty_bdf='0000:47:00.0',expected_vision=[3487303,63453537],safe_properties=SAFE,pairs=84,kernels=168,device_bytes=963610200,pinned_bytes=1048576,root_floor_bytes=27000000000,root_cache_forecast_bytes=134217728,minimum_available_memory=8*1024**3,no_retry=True,native_admitted=False)
def exact_result(result):
    assert result['schema']=='gsq.iq3xxs-block.native-micro.v1' and result['passed'] and result['safe_to_exit']
    assert result['completed_exact_pairs']==84 and result['attempted_kernel_submissions']==168 and result['device_bytes']==963610200 and result['transfer_bytes']==965690280
    assert result['warmup_cycles']==4 and result['measured_cycles']==24 and not result['error'] and not result['cleanup_error']
    t=result['teardown'];assert t['safe_to_exit'] and t['exit_code']==0 and t['in_flight']==0 and t['live_bytes']==0
    manifest=json.loads((P/'manifest.json').read_text());f=STAGE/'result/samples.jsonl';assert f.stat().st_size<=256*1024
    rows=[json.loads(line) for line in f.read_text().splitlines()];assert len(rows)==84
    for row,expected in zip(rows,manifest['schedule']):
        case=manifest['cases'][expected['case']];digest=case['fixtures']['expected']['sha256']
        assert row['warmup']==expected['warmup'] and row['cycle']==expected['cycle'] and row['layer']==case['layer'] and row['label']==case['label'] and row['order']==''.join(expected['order'])
        assert row['exact'] and row['A_sha256']==row['B_sha256']==row['expected_sha256']==digest
        assert row['A_status_sha256']==row['B_status_sha256']==row['expected_status_sha256']==case['fixtures']['status']['sha256']
        for arm in ('A','B'):assert row[arm+'_end_ns']>row[arm+'_start_ns']>0
    return True

def main(plan):
    assert plan==build_plan(),'source/plan drift'
    coordination_clear()
    signal.signal(signal.SIGTERM,lambda *_:STOP.append('SIGTERM'))
    signal.signal(signal.SIGINT,lambda *_:STOP.append('SIGINT'))
    before = observe.observe()
    assert before['known_fault_baseline_matches'] and before['root_free_bytes'] > 27_250_000_000
    assert before['memory']['MemAvailable'] > 8*1024**3
    assert before['units']['qwen38-27b-fp8']['ActiveState'] == 'inactive'
    target = observe.target_nodes(before, '0000:23:00.0')
    assert before['drm']['renderD130']['bdf'] == '0000:23:00.0'
    assert not before['identity_races']
    assert not any(x['node'] in target for x in before['inventory']['holders'])
    old = json.loads(BASELINE.read_text())
    assert before['boot']==old['boot']
    assert not any(x['node'] in observe.target_nodes(before,'0000:47:00.0') for x in before['inventory']['holders'])
    for unit in ('qwen38-27b-fp8', 'qwen38-27b-fp8-tp1-test', 'qwen38-27b-vision'):
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
    evidence = BUILD
    proof = json.loads(evidence.read_text())
    assert proof['passed'] and sha(proof['binary']) == proof['binary_sha256']
    for group in ('source_sha256', 'objects_reused', 'dependencies'):
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
        '--property=Nice=19', '--property=Restart=no', '--property=SendSIGKILL=no', '--property=KillMode=process',
        '--property=TimeoutStopSec=infinity', '--property=LimitAS=infinity', '--property=LimitCORE=0',
        '--property=UMask=0077', '--property=WorkingDirectory='+str(R),
        '/usr/bin/env', '-i', *[k+'='+v for k, v in env.items()], '/usr/bin/taskset', '-c', '0-3,16-19',
        proof['binary'], '--run', '--card', '0', '--output', str(STAGE/'result')]
    admission = dict(before=before, command=cmd, proof_sha256=sha(evidence), binary_sha256=proof['binary_sha256'],
        monitor_sha256=sha(__file__), observer_sha256=sha(observe.__file__), target=target, plan=plan, scope='fixed real-weight isolated IQ3_XXS gate/up AB/BA micro; not model throughput', retry=False)
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
        if STOP:raise RuntimeError('stop received before launch')
        subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, timeout=30)
    except BaseException as ex:
        latch('launch outcome uncertain: '+repr(ex))

    while True:
        state = None
        snapshot = None
        observation_complete = False
        native_holders = []
        try:
            if STOP:latch('cooperative parent stop: '+STOP[0])
            coordination_clear()
            state = status()
            if state.get('ActiveState') in ('active','activating','deactivating'):
                for k,v in SAFE.items():
                    if state.get(k)!=v:latch('unsafe unit property: '+k)
            snapshot = observe.observe()
            if snapshot['root_free_bytes'] < 27_000_000_000 or snapshot['memory']['MemAvailable'] < 8*1024**3:latch('continuous memory/disk floor')
            if snapshot['boot']!=before['boot']:latch('boot changed')
            if snapshot['identity_races']:
                raise RuntimeError('passive PID identity raced; sample inconclusive')
            if observe.target_nodes(snapshot, '0000:23:00.0') != target:
                raise RuntimeError('target alias/dev_t mapping changed')
            if not snapshot['known_fault_baseline_matches']:
                latch('kernel fault baseline changed; halt new work')
            if snapshot['queue'] != before['queue']:
                latch('coordination changed')
            for unit in ('qwen38-27b-fp8', 'qwen38-27b-fp8-tp1-test', 'qwen38-27b-vision'):
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
            if time.monotonic()-start > 900 and state.get('ActiveState') in ('active', 'activating', 'deactivating'):
                latch('micro exceeded900s; cooperative stop')
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
                    and result.get('passed') and result.get('safe_to_exit') and observed_native_target_fd and exact_result(result))
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
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--plan',action='store_true');group.add_argument('--run',type=Path);args=parser.parse_args()
    if args.plan:print(json.dumps(build_plan(),indent=2))
    else:raise SystemExit(main(json.loads(args.run.read_text())))
