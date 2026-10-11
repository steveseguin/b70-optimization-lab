#!/usr/bin/env python3
"""Coordinator only; one admitted native child, no restart/kill/reset path."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from plan import HERE, ROOT, make_plan, sha
from receipt import summary, validate_receipt

spec = importlib.util.spec_from_file_location('packet2_window', HERE.parent/'packet2/tests/device_window.py')
packet2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(packet2)
journal, FAULT = packet2.journal, packet2.FAULT

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--authorized-device-window', action='store_true', required=True)
    p.add_argument('--card', type=int, required=True)
    p.add_argument('--admitted-cards', type=int, nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=120)
    a = p.parse_args()
    if (not 1 <= a.seconds <= 120 or len(a.admitted_cards) not in (1,2)
        or len(set(a.admitted_cards)) != len(a.admitted_cards) or a.card not in a.admitted_cards
        or any(not 0 <= c < 4 for c in a.admitted_cards)):
        raise SystemExit('one/two distinct admitted cards and <=120 seconds required')
    if os.environ.get('OMP_NUM_THREADS') != '2' or os.getpriority(os.PRIO_PROCESS,0) != 19:
        raise SystemExit('nice 19 and OMP_NUM_THREADS=2 required')
    if any(os.environ.get(k) for k in ('ONEAPI_DEVICE_SELECTOR','SYCL_DEVICE_FILTER','ZE_AFFINITY_MASK')):
        raise SystemExit('remove selector masks; admitted indices use unmasked Level Zero ordering')
    out = a.output.resolve()
    if HERE/'build' not in out.parents or out.exists(): raise SystemExit('new output under packet build/ required')
    build = json.loads((HERE/'build-receipt.json').read_text())
    if not build['passed'] or build['native_executed']: raise SystemExit('CPU build receipt required')
    for name,digest in build['source_sha256'].items():
        if sha(ROOT/name) != digest: raise SystemExit('source changed: '+name)
    binary = HERE/'build/compile/h2d-native'; tsv = HERE/'build/plan.tsv'
    if sha(binary) != build['binary_sha256'] or sha(tsv) != build['plan_tsv_sha256'] or sha(HERE/'plan.json') != build['plan_json_sha256']:
        raise SystemExit('binary/plan identity mismatch')
    plan = make_plan()
    if json.loads((HERE/'plan.json').read_text()) != plan: raise SystemExit('plan mismatch')
    peer = next((c for c in a.admitted_cards if c != a.card), -1)
    pre,cursor = journal(); out.mkdir(parents=True); (out/'preflight-kernel.txt').write_text(pre)
    record = dict(schema='own-runtime.h2d.window.v1', passed=False, stop_reason=None,
        start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        cards=[a.card]+([peer] if peer>=0 else []), seconds=a.seconds, binary_sha256=sha(binary),
        build_receipt_sha256=sha(HERE/'build-receipt.json'),
        environment={k:v for k,v in os.environ.items() if k.startswith(('SYCL_','UR_','ZE_','IGC_')) or k in ('OMP_NUM_THREADS','EnableDeferBacking')},
        external_idle_health_still_required=True)
    (out/'meminfo-before.txt').write_text(Path('/proc/meminfo').read_text())
    requested=[]
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,lambda s,f:requested.append('watcher signal '+str(s)))
    def save(): (out/'window.json').write_text(json.dumps(record,indent=2)+'\n')
    with (out/'stdout.txt').open('w') as log, (out/'kernel-window.txt').open('w') as kernel:
        started=time.monotonic()
        child=subprocess.Popen([str(binary),'--authorized-device-window',str(a.card),str(peer),str(tsv),str(out/'native.json'),str(out/'STOP')],stdout=log,stderr=subprocess.STDOUT)
        record['pid']=child.pid; save(); sent=False
        while True:
            try:
                fresh,cursor=journal(cursor); kernel.write(fresh); kernel.flush()
                if FAULT.search(fresh): requested.append('new GPU fault signature')
            except Exception as e: requested.append('kernel journal: '+str(e))
            if time.monotonic()-started>a.seconds: requested.append('window deadline')
            if requested and not sent:
                record['stop_reason']=requested[0];(out/'STOP').write_text(requested[0]+'\n');save()
                if child.poll() is None: child.send_signal(signal.SIGTERM)
                sent=True
            if child.poll() is not None: break
            time.sleep(.25)
        record['returncode']=child.returncode
        for _ in range(20):
            time.sleep(.25)
            try:
                fresh,cursor=journal(cursor);kernel.write(fresh)
                if FAULT.search(fresh): requested.append('post-exit GPU fault')
            except Exception as e: requested.append('postflight journal: '+str(e))
    record['elapsed_seconds']=time.monotonic()-started
    (out/'meminfo-after.txt').write_text(Path('/proc/meminfo').read_text())
    try:
        receipt=summary(json.loads((out/'native.json').read_text()),plan)
        validate_receipt(receipt)
        receipt['window_passed']=child.returncode==0 and not requested
        receipt['external_idle_health_still_required']=True
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
        record['passed']=receipt['window_passed']
    except Exception as e: requested.append('receipt validation: '+str(e))
    if requested: record['stop_reason']=requested[0]
    save(); return 0 if record['passed'] else 1
if __name__ == '__main__': raise SystemExit(main())
