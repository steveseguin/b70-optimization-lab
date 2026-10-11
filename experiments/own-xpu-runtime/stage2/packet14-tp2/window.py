#!/usr/bin/env python3
"""Coordinator only: bounded single child, cooperative stop and journal fault latch."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('packet2_window',HERE.parent/'packet2/tests/device_window.py')
p2=importlib.util.module_from_spec(spec);spec.loader.exec_module(p2)
sha=p2.sha

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorized-device-window',action='store_true',required=True)
    p.add_argument('--card',type=int,required=True);p.add_argument('--stage',choices=['layer','first-token'],required=True)
    p.add_argument('--cards',type=int,choices=[2],default=2);p.add_argument('--memory',choices=['tp2-streaming'],default='tp2-streaming')
    p.add_argument('--input',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--layer-gate',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeat-of',type=Path)
    p.add_argument('--seconds',type=int,default=600);a=p.parse_args()
    maximum={'layer':3600,'first-token':10800}[a.stage]
    if not 0<a.seconds<=maximum or a.card not in (2,3) or a.card+a.cards>4:raise SystemExit('window/card bounds')
    if (a.card,a.cards,a.memory)!=(2,2,'tp2-streaming'):raise SystemExit('memory/card mismatch')
    if os.environ.get('OMP_NUM_THREADS')!='2' or os.getpriority(os.PRIO_PROCESS,0)!=19:raise SystemExit('nice19 OMP_NUM_THREADS=2 required')
    if 'idle' not in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True):raise SystemExit('ionice -c3 required')
    build=HERE/'build';boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();latch=build/'FAULT.json'
    if latch.exists() and json.loads(latch.read_text()).get('boot_id')==boot:raise SystemExit('fault latch: coordinator recovery decision required')
    out=a.output.resolve()
    if build not in out.parents or out.exists():raise SystemExit('new directory under packet14-tp2 build required')
    receipt=json.loads((HERE/'build-receipt.json').read_text());binary=build/'device/own-rt-iq3'
    if not receipt['passed'] or sha(binary)!=receipt['artifacts_sha256']['device/own-rt-iq3']:raise SystemExit('build/binary mismatch')
    for name,digest in receipt['sources'].items():
        if sha(ROOT/name)!=digest:raise SystemExit('source changed: '+name)
    input_receipt=json.loads((a.input/'input.json').read_text())
    for name,digest in input_receipt['files'].items():
        if sha(a.input/name)!=digest:raise SystemExit('input changed: '+name)
    baseline,fixtures=baseline_gate(a.baseline,a.input,a.stage)
    if a.stage=='first-token':layer_gate(a.layer_gate,a.baseline,binary,a.input,boot)
    authority='iq3-p14-full-row-p13-tree-slot-order-v1'
    oracle_tokens=baseline.get('tokens',[])[:1]
    prior=None
    if a.repeat_of:
        prior=json.loads(a.repeat_of.read_text())
        if prior.get('input_sha256')!=sha(a.input/'tokens.txt') or not prior['passed'] or prior['boot_id']!=boot or prior['stage']!=a.stage or prior['card']!=a.card or prior.get('cards')!=a.cards or prior['binary_sha256']!=sha(binary):raise SystemExit('invalid fresh repeat anchor')
    pre,cursor=p2.journal();out.mkdir(parents=True);(out/'preflight-kernel.txt').write_text(pre)
    cmd=[str(binary),'--authorized-device-window','--card',str(a.card),'--cards',str(a.cards),'--memory',a.memory,'--input',str(a.input/'tokens.txt'),'--plan',str(a.input/'plan.tsv'),'--identity',str(a.input/'identity.tsv'),'--model-dir',input_receipt['model_dir'],'--output',str(out/'run'),'--seconds',str(a.seconds),'--tokens','1']
    if a.stage=='layer':cmd+=['--first-layer']
    record=dict(schema='own-runtime.iq3.packet14.window.v1',boot_id=boot,card=a.card,cards=a.cards,memory=a.memory,stage=a.stage,arithmetic=authority,real_model_qualified=False,binary_sha256=sha(binary),input_sha256=sha(a.input/'tokens.txt'),command=cmd,passed=False,external_idle_health_still_required=True,baseline_sha256=sha(a.baseline),oracle_hashes=fixtures)
    requested=[]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda s,f:requested.append('watcher stop '+str(s)))
    def persist(): (out/'window.json').write_text(json.dumps(record,indent=2)+'\n')
    with (out/'stdout.txt').open('w') as log,(out/'kernel-window.txt').open('w') as kernel:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);record['pid']=child.pid;start=time.monotonic();sent=False;persist()
        while True:
            try:
                fresh,cursor=p2.journal(cursor);kernel.write(fresh);kernel.flush()
                if p2.FAULT.search(fresh):
                    requested.append('new GPU fault');latch.write_text(json.dumps(dict(boot_id=boot,window=str(out),reason=requested[-1]))+'\n')
            except Exception as e:requested.append('journal failed: '+str(e))
            if time.monotonic()-start>a.seconds:requested.append('window deadline')
            if requested and not sent:
                record['stop_reason']=requested[0];persist()
                latch.write_text(json.dumps(dict(boot_id=boot,window=str(out),reason=requested[0]))+'\n')
                if child.poll() is None:child.send_signal(signal.SIGTERM)
                sent=True
            if child.poll() is not None:break
            time.sleep(.25)
        for _ in range(20):
            time.sleep(.25)
            try:
                fresh,cursor=p2.journal(cursor);kernel.write(fresh)
                if p2.FAULT.search(fresh):
                    requested.append('postflight GPU fault');latch.write_text(json.dumps(dict(boot_id=boot,window=str(out),reason=requested[-1]))+'\n')
            except Exception as e:requested.append('postflight journal failed: '+str(e))
        record.update(returncode=child.returncode,elapsed_seconds=time.monotonic()-start)
    try:run=json.loads((out/'run/receipt.json').read_text())
    except (OSError,ValueError) as error:
        run={};requested.append('missing or invalid native receipt: '+str(error))
    complete = len(run.get('tokens',[]))==1 if a.stage=='first-token' else not run.get('tokens')
    expected_layers=1 if a.stage=='layer' else 48
    expected_steps=1
    actual={}
    for step in range(1,expected_steps+1):
        for layer in range(expected_layers):
            rel=f'step{step}/layer-{layer:02}.bf16';f=out/'run'/rel
            if not f.exists() or f.stat().st_size!=20480:complete=False
            else:actual[rel]=sha(f)
    exact=None
    if fixtures:
        exact=complete and all(record['oracle_hashes'].get(k)==v for k,v in actual.items())
        if a.stage!='layer':exact=exact and run.get('tokens')==oracle_tokens
    tears=run.get('teardown',[])
    safe=len(tears)==a.cards and all(r.get('safe_to_exit') and r.get('live_bytes')==0 and r.get('in_flight')==0 for r in tears)
    passed=child.returncode==0 and not requested and run.get('passed') is True and safe and complete and exact is not False
    record.update(passed=passed,diagnostic_complete=complete,oracle_exact=exact,layer_hashes=actual,tokens=run.get('tokens',[]))
    record['fresh_repeat_passed']=bool(passed and prior and prior.get('layer_hashes')==actual and prior.get('tokens')==record['tokens'])
    if prior and not record['fresh_repeat_passed']:record['passed']=False
    if not safe:requested.append('unsafe or missing owner teardown')
    if requested:
        latch.write_text(json.dumps(dict(boot_id=boot,window=str(out),reason=requested[0]))+'\n')
    if requested:record['stop_reason']=requested[0]
    persist();raise SystemExit(0 if record['passed'] else 1)
def baseline_gate(path,input_dir,stage):
    record=json.loads(path.read_text())
    if not record.get('passed') or record.get('cards')!=1 or record.get('card')!=3 or record.get('arithmetic')!='iq3-p13-r234-sg32-split4-bf16-v1':
        raise SystemExit('passing packet13 single-card arithmetic receipt required')
    if record.get('input_sha256')!=sha(input_dir/'tokens.txt'):raise SystemExit('baseline prompt changed')
    if record.get('stage')!='first-token' or not record.get('tokens'):raise SystemExit('baseline token missing')
    run=json.loads((path.parent/'run/receipt.json').read_text())
    if not run.get('passed') or len(run.get('teardown',[]))!=1 or not all(t.get('safe_to_exit') and not t.get('live_bytes') and not t.get('in_flight') for t in run.get('teardown',[])):
        raise SystemExit('baseline native run/teardown failed')
    fixtures={}
    for layer in range(48):
        rel=f'step1/layer-{layer:02}.bf16';f=path.parent/'run'/rel
        if not f.is_file() or f.stat().st_size!=20480 or sha(f)!=record.get('layer_hashes',{}).get(rel):raise SystemExit('baseline fixture missing/changed')
        if stage!='layer' or layer==0:fixtures[rel]=sha(f)
    return record,fixtures

def layer_gate(path,baseline,binary,input_dir,boot):
    if path is None:raise SystemExit('first-token requires --layer-gate')
    r=json.loads(path.read_text())
    if not(r.get('passed') and r.get('oracle_exact') is True and r.get('stage')=='layer' and r.get('cards')==2 and r.get('card')==2 and r.get('baseline_sha256')==sha(baseline) and r.get('binary_sha256')==sha(binary) and r.get('input_sha256')==sha(input_dir/'tokens.txt') and r.get('boot_id')==boot):raise SystemExit('layer gate stale or failed')

if __name__=='__main__':main()
