"""Pinned engine verification and isolated trial worker; no server management."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ENGINE=HERE.parent/'history_v1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_engine():
    pins=json.loads((HERE/'pinned-engine.json').read_bytes())
    actual={p.name:sha(p) for p in ENGINE.glob('*.py') if not p.name.startswith('test_')}
    if actual!=pins['source_sha256']:raise ValueError('frozen history engine source drift')
    return pins


def compiler():
    verify_engine()
    spec=importlib.util.spec_from_file_location('history_study_pinned_task_compiler',ENGINE/'tasks.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--arm',choices=('archive','quoted'),required=True)
    parser.add_argument('--retrieval-mode',choices=('source-only','history'),required=True)
    parser.add_argument('--stub',action='store_true');parser.add_argument('--endpoint');parser.add_argument('--model')
    parser.add_argument('--identity',type=Path)
    args=parser.parse_args();verify_engine()
    if not args.stub and (not args.endpoint or not args.model or not args.identity):parser.error('live worker needs explicit endpoint/model/identity')
    # This is a fresh Python process: the pinned engine's absolute imports cannot
    # collide with the wrapper's modules or a previously imported task compiler.
    sys.path.insert(0,str(ENGINE))
    import live
    task=json.loads(args.task.read_bytes())
    client=live.StubClient(task) if args.stub else live.HTTPClient(args.endpoint,args.model)
    identity=None if args.stub else {'endpoint':args.endpoint,'model':args.model,'launch_sha256':sha(args.identity)}
    live.run_trial(task,args.arm,args.out,client,identity,retrieval_mode=args.retrieval_mode)
    verify_engine()


if __name__=='__main__':main()
