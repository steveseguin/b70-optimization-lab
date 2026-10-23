#!/usr/bin/env python3
"""Additive packet201 entry point; operational modes require root admission."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
OPS = ROOT/'experiments/own-xpu-runtime/ops/packet201-window'
STAGE = P/'evidence/planned-a'
REVIEW = P/'evidence/fault-review-device-a.json'
MANIFEST = P/'READY-FOR-DEVICE.json'
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


W = load('_p201_adapter_frozen_worker', P/'device_worker.py')
require, sha = W.require, W.sha


def required_sources():
    vectors=json.loads((P/'client-vectors.json').read_text())
    baseline=[ROOT/name for name in vectors['source_sha256']]
    return baseline+[P.parent/'packet200-bounded-serving/client-vectors.json']+[P/n for n in ('run.py','test_run.py','client_pilot.py','test_client_pilot.py','client-vectors.json','CLIENT.md','evidence/client-cpu-tests.json')] + [OPS/n for n in
        ('driver.py','helpers.py','restore_guard.py','test_driver.py','DRIVER.md',
         'window.py','test_window.py','helper-pins.json')]


def verify_manifest(expected_sha=None):
    """Source-only gate usable after output creation; never asserts fresh paths."""
    raw = MANIFEST.read_bytes()  # Deliberately before any host/queue/service operation.
    digest = hashlib.sha256(raw).hexdigest()
    require(expected_sha is None or digest == expected_sha, 'operational manifest changed')
    row = json.loads(raw)
    require(row.get('schema') == 'packet201.execution-admission.v1' and row.get('passed') is True
            and row.get('operational_launch_authorized') is True, 'root operational admission required')
    require(row.get('storage_admission_mode') == 'monitored-forecast' and row.get('storage_bound_proven') is False,
            'forecast is not a certified storage bound')
    sources = row.get('source_sha256', {})
    require(all(str(path.relative_to(ROOT)) in sources for path in required_sources()), 'adapter source closure incomplete')
    for name, value in sources.items():
        path = ROOT/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and path.resolve().is_relative_to(ROOT),
                'invalid admitted source path')
        require(sha(path) == value, 'admitted source drift: '+name)
    W.integration_origins()
    return row, digest


def plan():
    return W.cpu_plan(STAGE, activity_mode='launch')


def admitted_plan():
    row, digest = verify_manifest()
    contract=load('_p201_adapter_frozen_contract',OPS/'window.py')
    require(contract.staging_identity(STAGE)==row.get('controller',{}).get('staging_identity'),
            'root-admitted staging identity changed')
    value = plan()
    W.authorize(value, MANIFEST)
    require(row['plan_sha256'] == W.digest(value), 'admitted plan differs')
    return value, digest


def worker_argv():
    return [PYTHON,'-B',str(P/'run.py'),'--authorized-device-window','--staging-parent',str(STAGE),
            '--activity-mode','launch','--fault-review',str(REVIEW),'--output',str(STAGE/'output')]


def capture_fault_review(value):
    require(not os.path.lexists(REVIEW) and not os.path.lexists(REVIEW.with_suffix('.kernel.jsonl.gz')),
            'fresh fixed fault capture required; no retry')
    safety = W.Safety(value, REVIEW)  # Constructor/imports only; no model or preflight.
    safety.m['conditions'].cpu_gate()
    row, text = safety.parent.capture_review()
    log = REVIEW.with_suffix('.kernel.jsonl.gz')
    with log.open('xb') as file:
        file.write(gzip.compress(text.encode(),mtime=0))
    row['kernel_capture'] = str(log)
    with REVIEW.open('x') as file:
        json.dump(row,file,indent=2,ensure_ascii=False,allow_nan=False); file.write('\n')
    return dict(passed=True,device_executed=False,fault_count=row['fault_count'],output=str(REVIEW))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan',action='store_true')
    mode.add_argument('--capture-fault-review',action='store_true')
    mode.add_argument('--verify-admission',action='store_true')
    mode.add_argument('--authorized-device-window',action='store_true')
    parser.add_argument('--staging-parent',type=Path,default=STAGE)
    parser.add_argument('--activity-mode',choices=['launch'],default='launch')
    parser.add_argument('--fault-review',type=Path,default=REVIEW)
    parser.add_argument('--output',type=Path,default=STAGE/'output')
    args=parser.parse_args(argv)
    require(args.staging_parent==STAGE and args.fault_review==REVIEW and args.output==STAGE/'output',
            'fixed first-run private paths required')
    if args.plan:
        print(json.dumps(plan(),ensure_ascii=False)); return 0
    value, digest=admitted_plan()
    verify_manifest(digest)
    if args.verify_admission:
        print(json.dumps(value,ensure_ascii=False)); return 0
    if args.capture_fault_review:
        print(json.dumps(capture_fault_review(value))); return 0
    return W.execute(value,fault_review=REVIEW,manifest=MANIFEST)


if __name__=='__main__':
    raise SystemExit(main())
