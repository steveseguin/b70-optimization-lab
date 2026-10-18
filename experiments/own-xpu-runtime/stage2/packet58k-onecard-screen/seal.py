#!/usr/bin/env python3
"""Seal a wrapper around byte-identical 58j binaries; no compile or device load."""
import argparse
import hashlib
import json
import os
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
PARENT=P.parent/'packet58j-onecard-port'
GATES=('evidence/postload-allocation-cpu.json','evidence/fullshape-submit-cpu.json','evidence/python-cpu-gates.json')

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def require(v,s):
    if not v:raise ValueError(s)
def verify(root,items):
    require(bool(items),'empty pins')
    for n,h in items.items():
        path=(root/n).resolve()
        require(path.is_relative_to(ROOT) and sha(path)==h,'changed input: '+n)

def create():
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    require(set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'helper cores required')
    parent=read(P/'parent-build-receipt.json')
    require(parent['passed'] is True and parent['device_executed'] is False,'parent CPU build failed')
    require(sha(P/'parent-build-receipt.json')==sha(PARENT/'build-receipt.json'),'parent snapshot changed')
    verify(ROOT,parent['sources']);verify(PARENT,parent['gates'])
    sources=dict(parent['sources'])
    for n,h in parent['gates'].items():sources[str((PARENT/n).relative_to(ROOT))]=h
    artifacts={n:parent['artifacts'][n] for n in ('build/device/own-rt-iq3','build/device/p58-cache-fixtures')}
    verify(P,artifacts)
    require(read(P/'evidence/fullshape-submit-cpu.json')['checks']==80,'parent full-shape gate incomplete')
    gates={}
    for leaf in GATES:
        r=read(P/leaf)
        require(r.get('passed') is True and r.get('device_executed') is False,'CPU gate failed: '+leaf)
        if 'sources' in r:verify(ROOT,r['sources']);sources.update(r['sources'])
        gates[leaf]=sha(P/leaf)
    verify(ROOT,read(P/'copy-manifest.json'))
    for f in [*P.glob('*.py'),*P.glob('*.json'),*(P/'selections').glob('*.json'),*(P/'evidence/58c-supervisor').glob('*')]:
        if f.name!='build-receipt.json':sources[str(f.relative_to(ROOT))]=sha(f)
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file())
    require(size<=150_000_000,'150 MB build cap')
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,
        sources=sources,artifacts=artifacts,gates=gates,retained_build_bytes=size,
        native_recompiled=False,native_byte_identical_to='packet58j-onecard-port',
        parent_build_sha256=sha(P/'parent-build-receipt.json'),evidence_label='screen',submission_eligible=False)
    (P/'build-receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
    return row

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');args=ap.parse_args()
    if args.verify:
        row=read(P/'build-receipt.json');verify(ROOT,row['sources']);verify(P,row['artifacts']);verify(P,row['gates'])
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,build_bytes=row['retained_build_bytes'],sources=len(row['sources']))))
if __name__=='__main__':main()
