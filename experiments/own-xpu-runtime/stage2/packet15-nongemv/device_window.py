#!/usr/bin/env python3
"""Coordinator-only, two fresh card-3 owners. --check never queries a device."""
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
BUILD=HERE/'build'
ROOT=HERE.parents[3]
LATCH=BUILD/'device-fault-latch.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def check(mode,output,exactness=None):
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise ValueError('nice19 / OMP_NUM_THREADS=2 required')
    out=output.resolve()
    if BUILD.is_symlink() or BUILD not in out.parents or out.exists():raise ValueError('fresh output under packet15/build required')
    if LATCH.exists():raise ValueError('fault/exactness latch: coordinator review required')
    m=json.loads((BUILD/'prepared.json').read_text())
    if not m['compiled'] or m['device_executed']:raise ValueError('invalid preparation')
    for path,digest in m['hashes'].items():
        if sha(ROOT/path)!=digest:raise ValueError('identity changed: '+path)
    lines=(BUILD/'fixtures/cases.txt').read_text().splitlines()
    if lines!=[c['name'] for c in m['fixtures']['cases']]:raise ValueError('fixture coverage')
    if not lines:raise ValueError('empty coverage')
    if mode=='timing':
        if not m['cpu_exactness_passed']:raise ValueError('CPU exactness failed; no timing admission')
        if not exactness:raise ValueError('timing needs --exactness')
        e=json.loads(exactness.read_text())
        if e.get('passed') is not True or e.get('prepared_sha256')!=sha(BUILD/'prepared.json') or len(e.get('runs',[]))!=2:raise ValueError('two fresh exact owners for same prepared identity required')
        for index,run in enumerate(e['runs']):
            folder=exactness.parent/f'owner{index}'
            if not teardown_ok(run.get('device',{})) or run['device'].get('checks')!=2*len(lines) or run.get('watch',{}).get('returncode')!=0 or run['watch'].get('stop_reason'):raise ValueError('incomplete exactness owner')
            if sha(folder/'device.json')!=run.get('device_sha256') or json.loads((folder/'device.json').read_text())!=run['device']:raise ValueError('exactness bytes changed')
            if sha(folder/'watch.json')!=run.get('watch_sha256'):raise ValueError('watch evidence changed')
    return m,out

def teardown_ok(v):
    t=v.get('teardown',{})
    return not v.get('error') and t.get('safe_to_exit') is True and t.get('idle_marker_complete') is True and t.get('live_bytes')==t.get('in_flight')==t.get('exit_code')==0 and t.get('status')=='complete' and not t.get('error') and 'context-released' in t.get('sequence',[])

def watch(command,out,journal,fault,seconds=120):
    # Journal reader is the repository's packet2 implementation. No GPU API here.
    pre,cursor=journal();out.mkdir();(out/'preflight-kernel.txt').write_text(pre)
    result=dict(returncode=None,stop_reason=None,fault_lines=[],external_idle_health_still_required=True)
    requested=[];old={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
    for sig in old:signal.signal(sig,lambda s,f:requested.append('watcher signal '+str(s)))
    try:
        with (out/'stdout.txt').open('w') as log,(out/'kernel-window.txt').open('w') as kernel:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);result['pid']=child.pid
            started=time.monotonic();sent=False
            while True:
                try:
                    fresh,cursor=journal(cursor);kernel.write(fresh);kernel.flush()
                    matches=[line for line in fresh.splitlines() if fault.search(line)]
                    if matches:result['fault_lines']+=matches;requested.append('new GPU fault')
                except Exception as e:requested.append('journal lost: '+str(e))
                if time.monotonic()-started>seconds:requested.append('deadline')
                if requested and not sent:
                    result['stop_reason']=requested[0];save(LATCH,dict(result,output=str(out)))
                    if child.poll() is None:child.send_signal(signal.SIGTERM)
                    sent=True
                if child.poll() is not None:break
                time.sleep(.25)
            result['returncode']=child.returncode
            for _ in range(20):
                time.sleep(.25)
                try:
                    fresh,cursor=journal(cursor);kernel.write(fresh)
                    matches=[line for line in fresh.splitlines() if fault.search(line)]
                    if matches:result['fault_lines']+=matches;requested.append('post-exit GPU fault')
                except Exception as e:requested.append('postflight journal lost: '+str(e))
            result['elapsed_seconds']=time.monotonic()-started
    finally:
        for sig,handler in old.items():signal.signal(sig,handler)
    if requested:result['stop_reason']=requested[0];save(LATCH,dict(result,output=str(out)))
    save(out/'watch.json',result);return result

def summarize(rows):
    import statistics
    out=[]
    for kind in ('gdn','qsa'):
        for M in (1,87):
            subset=[r for r in rows if r.get('kind')=='layer_census' and r['layer_type']==kind and r['M']==M and r['repeat']>0]
            if len(subset)!=10:raise ValueError('need five timed repeats in each of two fresh owners')
            out.append(dict(layer=kind,M=M,non_gemv_device_ms=statistics.median(r['non_gemv_device_ms'] for r in subset),wall_ms=statistics.median(r['wall_ms'] for r in subset),samples=10,kernel_submissions=subset[0]['kernel_submissions']))
    return dict(scope='synthetic non-GEMV operator sequence; GEMVs/transfers/real layer dependencies excluded',measured=True,rows=out)

def execute(mode,output,exactness=None):
    m,out=check(mode,output,exactness);out.mkdir()
    p=HERE.parent/'packet2/tests/device_window.py';spec=importlib.util.spec_from_file_location('packet2_watch',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    receipt=dict(schema='own-runtime.packet15.window.v1',mode=mode,card=3,passed=False,device_executed=True,prepared_sha256=sha(BUILD/'prepared.json'),cpu_exactness_passed=m['cpu_exactness_passed'],runs=[])
    try:
        for repeat in range(2):
            destination=out/('owner'+str(repeat))
            command=[str(BUILD/'native/device-test'),'--authorized-device-window','3',str(BUILD/'fixtures'),str(destination),mode]
            w=watch(command,destination,module.journal,module.FAULT)
            raw=json.loads((destination/'device.json').read_text()) if (destination/'device.json').exists() else {}
            receipt['runs'].append(dict(watch=w,device=raw,device_sha256=sha(destination/'device.json') if (destination/'device.json').exists() else None,watch_sha256=sha(destination/'watch.json')))
            expected=len(m['fixtures']['cases'])*(6 if mode=='timing' else 2)
            if w['returncode']!=0 or w['stop_reason'] or not teardown_ok(raw) or raw.get('checks')!=expected:
                save(LATCH,dict(reason='failed window, exactness, coverage or teardown',output=str(out)))
                raise ValueError('failed child; no retry')
        if mode=='timing':
            rows=[]
            for repeat in range(2):rows.extend(json.loads(line) for line in (out/f'owner{repeat}/timings.jsonl').read_text().splitlines())
            save(out/'summary.json',summarize(rows))
        receipt['passed']=True
    except Exception as e:
        receipt['passed']=False;receipt['error']=str(e)
        save(LATCH,dict(reason=str(e),output=str(out)))
    finally:save(out/'window.json',receipt)
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorized-device-window',action='store_true');p.add_argument('--check',action='store_true');p.add_argument('--card',type=int,required=True);p.add_argument('--mode',choices=('exactness','timing'),required=True);p.add_argument('--exactness',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.card!=3:raise SystemExit('card3 only')
    if a.check:check(a.mode,a.output,a.exactness);print('Identity checks passed; no device queried.');return
    if not a.authorized_device_window:raise SystemExit('coordinator device admission required')
    raise SystemExit(0 if execute(a.mode,a.output,a.exactness)['passed'] else 1)
if __name__=='__main__':main()
