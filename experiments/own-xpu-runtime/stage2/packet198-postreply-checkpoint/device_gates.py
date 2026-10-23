#!/usr/bin/env python3
"""CPU-only production argv interception, host parser refusal and readiness seal.

Never runs the device executable. The already-compiled GNU host binary must
refuse authorization, then (with only that flag removed) reach the final nice
gate. It cannot reach loading at the required nice19 helper placement.
"""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import device_worker as W


def verify_host_proof(plans):
    require = W.require
    proof = W.read(W.P / 'evidence/host-probe.json')
    require(proof['passed'] is True and proof['device_executed'] is False and proof['host_native_executed'] is True
            and proof['protocol_probe_passed'] is True
            and proof['binary_sha256'] == plans['host']['binary_sha256']
            and proof['harness_sha256'] == W.sha(W.P / 'host_probe.py'), 'host binary/harness proof drift')
    life = proof['lifecycle']
    require(life['passed'] is True and life['model_loads'] == 1 and len(life['requests']) == len(life['controls']) == 8,
            'eight-request/eight-disposition host proof required')
    require([row['id'] for row in life['requests']] == W.IDS, 'host request order differs')
    require(sum(row['event'] == 'checkpoint-saved' for row in life['controls']) == 6
            and sum(row['event'] == 'request-released' for row in life['controls']) == 2,
            'host proof must cover six SAVE/two RELEASE, independently of device five/three sequence')
    for key in ('save_resume_exact', 'append_repeat_fresh_state_exact', 'parent_immediate_save_state_exact'):
        require(life[key] is True, 'host state proof missing: ' + key)
    require(life['stopped']['safe_to_exit'] is True and life['stopped']['completed_requests'] == 8
            and life['stopped']['completed_controls'] == 8 and life['stopped']['discarded_pending'] is False
            and life['stopped']['pending_request_id'] == '', 'host final SAVE/drain proof missing')
    cases = {'wrong-history', 'next-run-pending', 'stale-request', 'existing-checkpoint', 'duplicate-operation'}
    require(len(proof['native_refusals']) == 5 and {row['case'] for row in proof['native_refusals']} == cases
            and all(row['returncode'] == 1 and row['safe_to_exit'] is True for row in proof['native_refusals']),
            'five actual native refusal proofs required')
    require(proof['pending_quit']['safe_to_exit'] is True and proof['pending_quit']['discarded_pending'] is True
            and proof['pending_quit']['completed_controls'] == 0, 'pending QUIT proof required')
    artifacts = W.read(W.P / 'evidence/host-probe-artifacts.json')
    require(artifacts['passed'] is True and artifacts['device_executed'] is False
            and artifacts['host_receipt_sha256'] == W.sha(W.P / 'evidence/host-probe.json')
            and artifacts['build_receipt_sha256'] == W.sha(W.P / 'evidence/build-compile-only.json')
            and artifacts['harness_sha256'] == W.sha(W.P / 'host_probe.py'), 'host artifact manifest identity')
    run = Path(proof['run_directory'])
    require(run.is_relative_to(W.P / 'build') and str(run) == artifacts['run_directory'], 'host artifacts outside fixed packet')
    actual = set()
    for path in run.rglob('*'):
        require(not path.is_symlink(), 'host evidence symlink refused')
        if path.is_file(): actual.add(str(path.relative_to(W.ROOT)))
    require(actual == set(artifacts['files_sha256']) == set(artifacts['file_sizes']), 'host artifact file set changed')
    for name, digest in artifacts['files_sha256'].items():
        path = W.ROOT / name
        require(W.sha(path) == digest and path.stat().st_size == artifacts['file_sizes'][name], 'host artifact drift: ' + name)
    require(len(actual) == artifacts['file_count'], 'host artifact count')
    return dict(passed=True, requests=8, controls=8, host_save_count=6, host_release_count=2,
                native_refusal_count=5, artifact_files=len(actual), artifact_manifest_sha256=W.sha(W.P / 'evidence/host-probe-artifacts.json'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seal', action='store_true')
    args = ap.parse_args()
    require = W.require
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
            set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32)), 'nice19 helper cores required')
    W.storage()
    # Refuse stale compilation/host receipts before any executable is chosen.
    build = W.read(W.P / 'evidence/build-compile-only.json')
    require(build['passed'] and build['device_executed'] is False and build['native_executed'] is False, 'compile-only proof')
    require(build['source_overlay_sha256'] == W.sha(W.P / 'evidence/source-overlay.json') and
            build['parent_pins_sha256'] == W.sha(W.P / 'parent-pins.json'), 'compiled overlay changed')
    for name, digest in W.read(W.P / 'parent-pins.json')['sources'].items():
        require(W.sha(W.ROOT / name) == digest, 'host/native source pin changed: ' + name)
    for name, digest in W.read(W.P / 'evidence/source-overlay.json')['outputs'].items():
        require(W.sha(W.P / name) == digest, 'overlay source drift: ' + name)
    plans = {row['target']: row for row in build['plans']}
    for row in build['plans']:
        require(W.sha(row['binary']) == row['binary_sha256'], 'compiled binary changed')
        for name, digest in row['repository_dependencies'].items():
            require(W.sha(W.ROOT / name) == digest, 'compiled dependency changed: ' + name)
    host_proof = verify_host_proof(plans)
    require('-DOWN_RT_HOST_ONLY' in plans['host']['commands'][0] and plans['host']['commands'][0][0] == '/usr/bin/g++',
            'GNU host binary required for actual parser probes')
    env = W.parent_modules()['native_env'].environment('A')
    calls = []
    class Intercept(Exception): pass
    def intercept(argv, **kwargs):
        calls.append(dict(argv=argv, environment=kwargs['env'], stdin_pipe=kwargs['stdin'] == subprocess.PIPE,
                          stdout_pipe=kwargs['stdout'] == subprocess.PIPE, device_executed=False))
        raise Intercept('native child intercepted before exec')
    try:
        W.start_owner(W.native_argv(), env, io.BytesIO(), popen=intercept)
    except Intercept as error:
        interception = dict(passed=True, error=str(error), calls=calls)
    else:
        raise ValueError('native child was not intercepted')
    require(len(calls) == 1 and calls[0]['argv'] == W.native_argv(), 'wrong launch interception')
    host_argv = W.native_argv()
    host_argv[2] = str(W.P / 'build/host/own-rt-iq3')
    require(host_argv[2] == plans['host']['binary'], 'wrong host-only executable')
    require(not os.path.lexists(W.OUTPUT), 'fixed device output already exists; no preparation replay')
    refusal_rows = []
    for name, omit, expected in (
            ('production-authorization', False, 'host binary cannot authorize device execution'),
            ('production-front-final-priority', True, 'native priority differs from declared --native-nice')):
        argv = list(host_argv)
        if omit: argv.remove('--authorized-device-window')
        cp = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
        require(cp.returncode == 1 and expected in cp.stderr, 'wrong real parser refusal: ' + name + ': ' + cp.stderr)
        require(not os.path.lexists(W.OUTPUT), 'parser touched device output')
        refusal_rows.append(dict(case=name, argv=argv, returncode=cp.returncode, stdout=cp.stdout,
                                 stderr=cp.stderr, expected_refusal=expected, output_created=False))
    cp = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(W.P / 'tests'),
                         '-p', 'test_device_worker.py', '-v'], stdin=subprocess.DEVNULL, capture_output=True,
                        text=True, timeout=60, env=dict(os.environ, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2'))
    (W.P / 'evidence/device-worker-tests.log').write_text(cp.stdout + cp.stderr)
    require(cp.returncode == 0, 'device worker CPU tests failed: ' + cp.stderr)
    row = dict(passed=True, device_executed=False, native_device_executed=False, host_parser_executed=True,
               host_lifecycle_proof=host_proof,
               production_launch_interception=interception, parser_refusals=refusal_rows,
               tests_returncode=cp.returncode, tests_log_sha256=W.sha(W.P / 'evidence/device-worker-tests.log'),
               host_binary_sha256=plans['host']['binary_sha256'], device_binary_sha256=plans['device']['binary_sha256'],
               scope='CPU readiness only; real model arithmetic and lifecycle remain unqualified until one-shot device receipt.')
    target = W.P / 'evidence/device-cpu-gates.json'
    if target.exists():
        destination = W.P / 'lineage' / ('device-cpu-gates-before-' + time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '.json')
        destination.write_bytes(target.read_bytes())
    W.save(target, row)
    if args.seal:
        require(not W.READY.exists(), 'existing READY must be preserved/revoked explicitly before resealing')
        pins = {str(path.relative_to(W.ROOT)): W.sha(path) for path in W.source_paths()}
        W.save(W.READY, dict(passed=True, device_executed=False, schema='packet198.cpu-device-ready.v1',
               files_sha256=pins, native_argv=W.native_argv(), gates_sha256=W.sha(target),
               qualification='CPU-only request-front pilot; no performance or serving qualification'))
        W.verify_ready()
    print(json.dumps(dict(passed=True, device_executed=False, sealed=args.seal, actual_parser_refusals=2,
                         production_argv_intercepted=True)))


if __name__ == '__main__': main()
