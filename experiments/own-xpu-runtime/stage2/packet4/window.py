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
    p.add_argument('--card',type=int,required=True);p.add_argument('--stage',choices=['layer','token','eight'],required=True)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--oracle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--previous-window',type=Path)
    p.add_argument('--repeat-of',type=Path)
    p.add_argument('--seconds',type=int,default=600);a=p.parse_args()
    maximum={'layer':600,'token':3600,'eight':10800}[a.stage]
    if not 0<a.seconds<=maximum or not 0<=a.card<=3:raise SystemExit('window/card bounds')
    if os.environ.get('OMP_NUM_THREADS')!='2' or os.getpriority(os.PRIO_PROCESS,0)!=19:raise SystemExit('nice19 OMP_NUM_THREADS=2 required')
    if 'idle' not in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True):raise SystemExit('ionice -c3 required')
    build=HERE/'build';boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();latch=build/'FAULT.json'
    if latch.exists() and json.loads(latch.read_text()).get('boot_id')==boot:raise SystemExit('fault latch: coordinator recovery decision required')
    out=a.output.resolve()
    if build not in out.parents or out.exists():raise SystemExit('new directory under packet4 build required')
    receipt=json.loads((HERE/'build-receipt.json').read_text());binary=build/'device/own-rt-iq3'
    if not receipt['passed'] or sha(binary)!=receipt['artifacts_sha256']['device/own-rt-iq3']:raise SystemExit('build/binary mismatch')
    for name,digest in receipt['sources'].items():
        if sha(ROOT/name)!=digest:raise SystemExit('source changed: '+name)
    input_receipt=json.loads((a.input/'input.json').read_text())
    for name,digest in input_receipt['files'].items():
        if sha(a.input/name)!=digest:raise SystemExit('input changed: '+name)
    oracle_input=json.loads((a.oracle.parent/'input.json').read_text())
    if oracle_input['tokens']!=input_receipt['tokens']:raise SystemExit('oracle input mismatch')
    expected_layers=1 if a.stage=='layer' else 48
    fixtures=[a.oracle/f'layer-{i:02}.bf16' for i in range(expected_layers)]
    if any(not f.is_file() for f in fixtures):raise SystemExit('incomplete oracle fixtures')
    if a.stage!='layer':
        if not a.previous_window:raise SystemExit('previous passing stage receipt required')
        previous=json.loads(a.previous_window.read_text())
        if previous.get('input_sha256')!=sha(a.input/'tokens.txt') or not previous['passed'] or not previous.get('fresh_repeat_passed') or previous['boot_id']!=boot or previous['card']!=a.card or previous['binary_sha256']!=sha(binary) or previous['stage']!=('layer' if a.stage=='token' else 'token'):raise SystemExit('previous stage gate failed')
    if a.stage!='layer':
        expected=json.loads((a.oracle.parent/'result.json').read_text()).get('tokens',[])
        if len(expected)<(8 if a.stage=='eight' else 1):raise SystemExit('oracle token coverage missing')
    prior=None
    if a.repeat_of:
        prior=json.loads(a.repeat_of.read_text())
        if prior.get('input_sha256')!=sha(a.input/'tokens.txt') or not prior['passed'] or prior['boot_id']!=boot or prior['stage']!=a.stage or prior['card']!=a.card or prior['binary_sha256']!=sha(binary):raise SystemExit('invalid fresh repeat anchor')
    pre,cursor=p2.journal();out.mkdir(parents=True);(out/'preflight-kernel.txt').write_text(pre)
    cmd=[str(binary),'--authorized-device-window','--card',str(a.card),'--cards','1','--input',str(a.input/'tokens.txt'),'--plan',str(a.input/'plan.tsv'),'--identity',str(a.input/'identity.tsv'),'--model-dir',input_receipt['model_dir'],'--oracle',str(a.oracle),'--output',str(out/'run'),'--seconds',str(a.seconds),'--tokens','8' if a.stage=='eight' else '1']
    if a.stage=='layer':cmd+=['--first-layer']
    record=dict(schema='own-runtime.iq3.packet4.window.v1',boot_id=boot,card=a.card,stage=a.stage,binary_sha256=sha(binary),input_sha256=sha(a.input/'tokens.txt'),command=cmd,passed=False,external_idle_health_still_required=True,oracle_hashes={f.name:sha(f) for f in fixtures})
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
    run=json.loads((out/'run/receipt.json').read_text()) if (out/'run/receipt.json').exists() else {}
    exact_tokens=None
    if a.stage!='layer':
        expected=json.loads((a.oracle.parent/'result.json').read_text()).get('tokens',[])
        n=8 if a.stage=='eight' else 1
        exact_tokens=len(expected)>=n and run.get('tokens')==expected[:n]
    record.update(token_exact=exact_tokens,passed=child.returncode==0 and not requested and run.get('oracle_exact') is True and all(r['safe_to_exit'] for r in run.get('teardown',[])) and (a.stage=='layer' or exact_tokens))
    record['fresh_repeat_passed']=bool(record['passed'] and prior and prior['oracle_hashes']==record['oracle_hashes'])
    if requested:record['stop_reason']=requested[0]
    persist();raise SystemExit(0 if record['passed'] else 1)
if __name__=='__main__':main()
