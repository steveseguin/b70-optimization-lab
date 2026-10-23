#!/usr/bin/env python3
"""Seal reviewed CPU readiness; native launch is intercepted, never executed."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import device_worker as W

OPS = W.ROOT / 'experiments/own-xpu-runtime/ops/packet199-window'
GATE = W.P / 'evidence/device-cpu-gates.json'


def review(path):
    row = W.read(path)
    W.require(row.get('passed') is True, 'independent review not passed: ' + str(path))
    hashes = row.get('source_sha256', row.get('sources_sha256', {}))
    W.require(hashes, 'review must bind source bytes')
    for name, digest in hashes.items():
        W.require(W.sha(W.ROOT / name) == digest, 'reviewed source changed: ' + name)
    return dict(path=str(path.relative_to(W.ROOT)), sha256=W.sha(path))


def finish_seal():
    """A failed post-seal check must leave an explicitly invalid admission."""
    try:
        W.verify_ready()
        command = [str(W.PYTHON), '-B', str(W.P / 'device_worker.py'), '--plan']
        cp = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            cwd=W.ROOT, timeout=60, env=dict(os.environ, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2'))
        W.require(cp.returncode == 0, 'fresh interpreter plan refused: ' + cp.stderr[-1000:])
        W.require(json.loads(cp.stdout) == W.plan(), 'fresh interpreter plan differs from sealed in-process plan')
        W.save(W.P / 'evidence/fresh-plan-proof.json', dict(passed=True, native_executed=False, device_executed=False,
            command=command, plan=json.loads(cp.stdout), ready_sha256=W.sha(W.READY)))
    except BaseException as error:
        originals = {source: source.read_bytes() for source in (W.READY, GATE)}
        ready = json.loads(originals[W.READY])
        ready.update(passed=False, final_admission_error=str(error))
        W.save(W.READY, ready)  # Invalidate before attempting archival bookkeeping.
        lineage = W.P / 'lineage/fresh-plan-refusal'
        lineage.mkdir(parents=True, exist_ok=False)
        for source, original in originals.items():
            (lineage / source.name).write_bytes(original)
        gate = W.read(GATE)
        gate.update(passed=False, final_admission_error=str(error))
        W.save(GATE, gate)
        ready.update(passed=False, final_admission_error=str(error), gates_sha256=W.sha(GATE))
        W.save(W.READY, ready)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', action='store_true', required=True)
    parser.parse_args()
    W.require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
              set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'helper placement required')
    W.require_interpreter()
    W.require(not any(os.path.lexists(p) for p in (W.READY, GATE, W.OUTPUT, W.CHECKPOINTS, W.REVIEW)),
              'fresh readiness and operational paths required; preserve prior attempts')
    W.parent().verify_ready()
    config, vectors = W.configuration()
    W.storage(W.PLANNED_WRITES)
    reviews = [review(W.P / 'evidence/independent-cpu-readiness.json'), review(OPS / 'independent-review.json')]
    for name in ('independent-chat-codec-review.json', 'independent-chat-service-review.json',
                 'independent-chat-http-review.json', 'independent-checkpoint-engine-host-result.json'):
        reviews.append(review(W.INTEGRATION / 'receipts' / name))
    original, actual = W.parent().native_argv(), W.native_argv()
    W.require(len(actual) == len(original), 'native argv length changed')
    changes = {'--output': str(W.OUTPUT / 'owner'), '--request-front-checkpoints': str(W.CHECKPOINTS),
               '--request-front-max-requests': '6'}
    allowed = {original.index(flag) + 1 for flag in changes}
    W.require({i for i, (a, b) in enumerate(zip(original, actual)) if a != b} == allowed,
              'native argv differs beyond three approved values')
    W.require(all(actual[original.index(flag) + 1] == value for flag, value in changes.items()), 'native argv values')
    calls = []
    class Intercept(Exception):
        pass
    def intercept(argv, **kwargs):
        calls.append(dict(argv=argv, environment=kwargs['env'],
                          stdin_pipe=kwargs['stdin'] == subprocess.PIPE, stdout_pipe=kwargs['stdout'] == subprocess.PIPE))
        raise Intercept('native child intercepted before exec')
    environment = W.parent_modules()['native_env'].environment('A')
    try:
        W.start_owner(actual, environment, io.BytesIO(), popen=intercept)
    except Intercept:
        pass
    else:
        raise ValueError('native process was not intercepted')
    W.require(len(calls) == 1 and calls[0]['argv'] == actual, 'wrong intercepted owner launch')
    tests = []
    for name, directory, pattern in (('worker', W.P / 'tests', 'test_device_worker.py'),
                                      ('seal', W.P / 'tests', 'test_device_gates.py'),
                                      ('controller', OPS, 'test_window.py')):
        command = [str(W.PYTHON), '-B', '-m', 'unittest', 'discover', '-s', str(directory), '-p', pattern, '-v']
        log = W.P / 'evidence' / ('gate-' + name + '-tests.log')
        W.require(not log.exists(), 'existing gate test log; preserve and review')
        with log.open('xb') as stream:
            cp = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                cwd=W.ROOT, timeout=60, env=dict(os.environ, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2'))
        W.require(cp.returncode == 0, 'CPU tests failed; inspect ' + str(log))
        tests.append(dict(command=command, returncode=cp.returncode, log=str(log.relative_to(W.ROOT)), sha256=W.sha(log)))
    W.require([review(W.ROOT / row['path']) for row in reviews] == reviews,
              'review receipt or reviewed source changed during tests')
    row = dict(schema='packet199.cpu-readiness-gates.v1', passed=True, device_executed=False, native_executed=False,
               parent_ready_sha256=W.sha(W.P198 / 'READY-FOR-DEVICE.json'), native_argv=actual,
               production_launch_interception=calls, changed_argument_values=changes,
               independent_reviews=reviews, tests=tests, request_count=6, save_count=5, release_count=1,
               maximum_output_tokens=896, disk_floor_bytes=W.DISK_FLOOR, planned_write_bytes=W.PLANNED_WRITES,
               scope='CPU integration and source admission only; no native/device HTTP execution or performance qualification')
    W.save(GATE, row)
    W.save(W.READY, dict(schema='packet199.cpu-device-ready.v1', passed=True, device_executed=False,
                        files_sha256={str(p.relative_to(W.ROOT)): W.sha(p) for p in W.source_paths()},
                        external_files_sha256={str(p): W.sha(p) for p in W.external_dependencies()},
                        native_argv=actual, gates_sha256=W.sha(GATE), qualification=row['scope']))
    finish_seal()
    print(json.dumps(dict(passed=True, sealed=True, native_executed=False, device_executed=False,
                         source_files=len(W.source_paths()), external_files=len(W.external_dependencies()))))


if __name__ == '__main__':
    main()
