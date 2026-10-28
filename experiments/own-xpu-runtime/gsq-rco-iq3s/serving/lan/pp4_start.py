#!/usr/bin/env python3
"""Start a fresh admitted PP4 262K endpoint; no plan/admission files are reused."""
import argparse, hashlib, importlib.util, json, os, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

P=Path(__file__).resolve().parent
R=P.parents[4]
import pp4_backend as B

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit',required=True)
    parser.add_argument('--qualification',action='store_true')
    parser.add_argument('--bind',default='192.168.2.44')
    parser.add_argument('--port',type=int,default=18161)
    parser.add_argument('--lifetime-hours',type=float,default=47.0)
    args=parser.parse_args()
    B.base.require(os.environ.get('SC117_PP4_SERVICE')=='1','SC117_PP4_SERVICE=1 required')
    B.base.require(os.environ.get('SC117_CONTEXT')=='262144','SC117_CONTEXT=262144 required')
    config_name='pp4-service-qualification.config.json' if args.qualification else 'pp4-service.config.json'
    config=json.loads((P/config_name).read_text())
    root=Path('/dev/shm/sc117-pp4-262k-qualification' if args.qualification else '/dev/shm/sc117-pp4-262k-lan')
    root.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix='control-',dir=root))
    output=run/'output'
    B.base.require(not output.exists(),'fresh PP4 output required')
    config['output']=str(output)
    runtime=run/'config.json'
    B.base.save(runtime,config)
    plan=run/'plan.json'
    subprocess.run([sys.executable,'-B',str(P/'pp4_service.py'),'--config',str(runtime),'--plan',str(plan)],check=True)
    observer=load(R/'experiments/own-xpu-runtime/gsq-rco-iq3s/operating/observe.py','pp4_start_observe')
    baseline=run/'baseline.json'
    B.base.save(baseline,observer.observe())
    admission=dict(schema='ownrt.pipeline-admission.v1',owner_authorized=True,
                   plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),baseline=str(baseline),
                   baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
                   expires_utc=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat())
    admission_path=run/'admission.json'
    B.base.save(admission_path,admission)
    B.base.require(not output.exists(),'PP4 output must remain absent before launch')
    os.execv(sys.executable,[sys.executable,'-B',str(P/'pp4_service.py'),'--run','--config',str(runtime),
             '--plan',str(plan),'--admission',str(admission_path),'--unit',args.unit,
             '--bind',args.bind,'--port',str(args.port),'--lifetime-hours',str(args.lifetime_hours)])

if __name__=='__main__':main()
