#!/usr/bin/env python3
"""Pin exact early packet91 receipts and register a fresh destination, CPU only.

Never imports a parent packet's receipts or clears/changes a stopped output.
The engine, topology, draft and miss selection stay identical.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from storage import B, digest
from build_engine import save
from resume_chain import EARLY, file_inventory
from write_paths import inside
P=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--destination',type=Path,required=True)
    a=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32))
    source,dest=a.source.absolute(),a.destination.absolute()
    assert source.parent==dest.parent==B and source!=dest and not dest.exists()
    assert re.fullmatch(r'device-cards01-[a-z][a-z0-9-]*',dest.name)
    from chain_seal import verify
    seal=verify();old_hash=digest(P/'build-receipt.json')
    from queue_runner import validate_success
    from window import prerequisites
    first=json.loads((source/'K0/window.json').read_text())
    for name in EARLY:
        inside(source/name,source,tree=True)
        validate_success(name,source,0)
        row=prerequisites(source/name/'window.json',name,first)
        assert row['schema']=='packet97.window.v1' and row['build_receipt_sha256']==old_hash
        assert row['artifacts_sha256']==seal['artifacts_sha256']
        assert row['screen_seal_sha256']==seal['screen_seal_sha256']
        assert row['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    saved=P/'evidence'/('resume-source-seal-'+old_hash+'.json')
    if not saved.exists():saved.write_bytes((P/'build-receipt.json').read_bytes())
    pin=dict(source=str(source),windows=list(EARLY),boot_id=first['boot_id'],
        old_seal_path=str(saved.relative_to(P)),old_seal_sha256=old_hash,
        screen_seal_sha256=seal['screen_seal_sha256'],artifacts_sha256=seal['artifacts_sha256'],
        candidate_dispatch_sha256=digest(P/'dispatch-p45.json'),
        dispatch_sha256=digest(source/'K2/run0/dispatch-measured.json'),files=file_inventory(source))
    save(P/'resume-pins.json',pin)
    save(P/'chain-registration.json',dict(output=dest.name))
    # A fresh interpreter reads the new registration; checked() revalidates all
    # engine/selection inputs. Only source bindings change in this wrapper seal.
    code="from chain_seal import P,checked;from build_engine import save;save(P/'build-receipt.json',checked());from packet56_submission import pin_resealed_packet56;pin_resealed_packet56()"
    subprocess.run([sys.executable,'-B','-c','import sys;sys.path.insert(0,sys.argv[1]);'+code,str(P)],check=True)
    cmd=[sys.executable,'-B',str(P/'queue_runner.py'),'--phase','model','--output-root',str(dest),'--resume-from',str(source),'--prepare-resume']
    subprocess.run(cmd,check=True)
    print(json.dumps(dict(passed=True,device_executed=False,source=str(source),destination=str(dest),next_window='KD')))

if __name__=='__main__':main()
