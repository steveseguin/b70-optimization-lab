#!/usr/bin/env python3
"""Future authorized window ONLY. This file is not invoked by validate.py.

One bounded native child, no server, retries, forced kills, reset or reboot.
SIGTERM requests cooperative drain; a stuck child retains its owner for the
coordinator, and this watcher keeps collecting journal evidence.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[3]
FAULT=re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|devcoredump|device coredump|GPU.*coredump|GuC.*(?:hang|lockup)|timed.out.*(?:job|fence)',re.I)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def journal(cursor=None):
    args=['journalctl','-k','--no-pager','--show-cursor']
    args+=['--after-cursor',cursor] if cursor else ['-n','200']
    p=subprocess.run(args,capture_output=True,text=True,timeout=2)
    if p.returncode or p.stderr.strip():raise RuntimeError('kernel journal unavailable: '+p.stderr)
    lines=p.stdout.splitlines();cursors=[s[len('-- cursor: '):] for s in lines if s.startswith('-- cursor: ')]
    if not cursors and not cursor:raise RuntimeError('missing journal boundary')
    return '\n'.join(s for s in lines if not s.startswith('-- cursor: '))+'\n',cursors[-1] if cursors else cursor

def main():
    p=argparse.ArgumentParser();p.add_argument('--authorized-device-window',action='store_true',required=True);p.add_argument('--card',type=int,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=120);a=p.parse_args()
    if not 1<=a.seconds<=120 or not 0<=a.card<4:raise SystemExit('bounded window/card required')
    if os.environ.get('OMP_NUM_THREADS')!='2':raise SystemExit('OMP_NUM_THREADS=2 required')
    out=a.output.resolve()
    if HERE/'build' not in out.parents or out.exists():raise SystemExit('new output directory under packet build/ required')
    build=json.loads((HERE/'build-receipt.json').read_text());cpu=json.loads((HERE/'cpu-receipt.json').read_text())
    if not build['passed'] or not cpu['passed'] or sha(HERE/'cpu-receipt.json')!=build['cpu_receipt_sha256']:raise SystemExit('CPU/build receipt mismatch')
    for name,digest in build['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise SystemExit('source differs: '+name)
    binary=HERE/'build/device/device-test'
    if sha(binary)!=build['artifacts_sha256']['device/device-test']:raise SystemExit('native binary hash mismatch')
    fixtures=HERE/'build/fixtures/device-fixtures';known={r['label']+'.fixture':r['fixture_sha256'] for r in cpu['fixtures']}
    present=list(fixtures.glob('*.fixture'))
    required={name for name in known if name.startswith(('random','real-'))}
    if {f.name for f in present}!=required:raise SystemExit('fixture coverage mismatch')
    for f in present:
        if sha(f)!=known.get(f.name):raise SystemExit('fixture hash mismatch')
    pre,cursor=journal();out.mkdir(parents=True);(out/'preflight-kernel.txt').write_text(pre)
    record=dict(schema='own-runtime.iq3.packet2.device-window.v1',start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),card=a.card,binary_sha256=sha(binary),fixtures={f.name:sha(f) for f in present},passed=False,stop_reason=None)
    # The coordinator supplies exclusive-card and fresh health admission before
    # this command. Old journal faults are retained, not mistaken for new ones.
    requested=[]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda s,f:requested.append('watcher signal '+str(s)))
    with (out/'stdout.txt').open('w') as log,(out/'kernel-window.txt').open('w') as kernel:
        child=subprocess.Popen([str(binary),'--authorized-device-window',str(a.card),str(fixtures),str(out/'device.json'),str(out/'census.json')],stdout=log,stderr=subprocess.STDOUT)
        record['pid']=child.pid;started=time.monotonic();sent=False
        (out/'window.json').write_text(json.dumps(record,indent=2)+'\n')
        while True:
            try:
                fresh,cursor=journal(cursor);kernel.write(fresh);kernel.flush()
                if FAULT.search(fresh):requested.append('new GPU fault signature')
            except Exception as e:requested.append(str(e))
            if time.monotonic()-started>a.seconds:requested.append('window deadline')
            if requested and not sent:
                record['stop_reason']=requested[0];(out/'window.json').write_text(json.dumps(record,indent=2)+'\n')
                if child.poll() is None:child.send_signal(signal.SIGTERM)
                sent=True
            if child.poll() is not None:break
            time.sleep(.25)
        record['returncode']=child.returncode
        # Preserve a bounded post-exit journal window; no device queries.
        for _ in range(20):
            time.sleep(.25)
            try:
                fresh,cursor=journal(cursor);kernel.write(fresh)
                if FAULT.search(fresh):requested.append('post-exit GPU fault')
            except Exception as e:requested.append('postflight journal: '+str(e))
        record['elapsed_seconds']=time.monotonic()-started
    receipt=json.loads((out/'device.json').read_text()) if (out/'device.json').exists() else {}
    record['passed']=child.returncode==0 and not requested and receipt.get('checks')==len(present)*4 and receipt.get('teardown',{}).get('safe_to_exit') is True
    record['external_idle_health_still_required']=True
    if requested:record['stop_reason']=requested[0]
    (out/'window.json').write_text(json.dumps(record,indent=2)+'\n')
    raise SystemExit(0 if record['passed'] else 1)
if __name__=='__main__':main()
