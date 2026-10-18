#!/usr/bin/env python3
"""CPU-only final packet58 seal. Refuses stale builds and stale source-bound gates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def require(value,message):
    if not value:raise ValueError(message)
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(path.read_text())
def verify_files(root,items):
    require(bool(items),'missing source/artifact hashes')
    for rel,digest in items.items():
        path=(root/rel).resolve();require(path.is_relative_to(ROOT) and sha(path)==digest,'stale source/artifact: '+rel)
def create():
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    require(set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32)),'restricted CPU affinity')
    sources={};artifacts={};gates={}
    for mode in ('gnu-host','device'):
        path=HERE/f'build-{mode}-receipt.json';row=read(path)
        require(row.get('passed') is True and row.get('device_executed') is False,'build failed')
        verify_files(ROOT,row['sources_sha256']);verify_files(HERE,row['binaries'])
        sources.update(row['sources_sha256']);artifacts.update(row['binaries']);gates[path.name]=sha(path)
    for leaf in ('evidence/cache-cpu-gates.json','evidence/copy-queue-cpu.json','request-reset-cpu.json','evidence/python-cpu-gates.json','evidence/postload-allocation-cpu.json'):
        path=HERE/leaf;row=read(path)
        require(row.get('passed') is True and row.get('device_executed') is False,'CPU gate failed '+leaf)
        pins=row.get('sources',row.get('dependencies',row.get('source_sha256',{})))
        if leaf=='evidence/postload-allocation-cpu.json':
            require(row['binary_sha256']==sha(HERE/'build/gnu-host/own-rt-iq3'),'stale postload allocation binary')
            require(row['postload_allocations']==3 and row['negative_cases']==2,'incomplete postload allocation gate')
        if leaf=='request-reset-cpu.json':
            require(row['binary_sha256']==sha(HERE/'build/gnu-host/own-rt-iq3'),'stale request-reset binary')
            pins={str((HERE/'test_engine_reset.py').relative_to(ROOT)):sha(HERE/'test_engine_reset.py')}
        require(isinstance(pins,dict),'CPU gate source pins missing')
        verify_files(ROOT,pins);sources.update(pins);gates[leaf]=sha(path)
    for name in ('build.py','seal.py','suite_driver.py','packet58_submission.py','record-threshold.json',
                 'window.py','queue_runner.py','memory_plan.py','memory-plan.json','selection.json','dispatch-speed6.json',
                 'oracle-binding.json','MEMORY.md','WINDOW.md','SUBMISSION.md','README.md',
                 'parent58-source-manifest.json','parent58b-source-manifest.json','evidence/root-cause.json',
                 'evidence/sensor-replay.json', 'evidence/queue-plan.txt', 'evidence/storage-admission.json',
                 'parent58c-source-manifest.json','ALLOCATION-AUDIT.md',
                 'evidence/native-delta.patch','evidence/native-identity.json',
                 'evidence/failed-K1a-native.log','evidence/failed-K1a-window.json',
                 'CPU-BUILD.md','CPU-PREPARATION-CLOSEOUT.md','DO-NOT-REPEAT.md'):
        path=HERE/name;sources[str(path.relative_to(ROOT))]=sha(path)
    for path in sorted([*(HERE/'evidence/58b-kd').rglob('*'), *(HERE/'evidence/58c-kd').rglob('*')]):
        if path.is_file():sources[str(path.relative_to(ROOT))]=sha(path)
    replay=read(HERE/'evidence/sensor-replay.json')
    require(replay.get('passed') is True and replay.get('device_executed') is False,'sensor replay failed')
    verify_files(ROOT,replay['source_sha256']);verify_files(ROOT,replay['source_files_sha256'])
    sources.update(replay['source_sha256']);sources.update(replay['source_files_sha256'])
    # Pin inherited passive supervision and exact metrics/checker, never alter them.
    for rel in ('packet56-draft-prefix/p56_head_support.py','packet56-draft-prefix/suite_metrics.py',
                'packet34-replay-bench/window.py','packet49-integrate/oracle/suite_check.py'):
        path=HERE.parent/rel;sources[str(path.relative_to(ROOT))]=sha(path)
    golden=HERE/'k1-cpu.json';row=read(golden)
    require(row.get('passed') is True and row.get('device_executed') is False,'K1 CPU golden missing')
    require(row.get('binary_sha256')==sha(HERE/'build/gnu-host/p58-cache-fixtures'),'K1 CPU golden binary changed')
    gates['k1-cpu.json']=sha(golden)
    plan=read(HERE/'memory-plan.json')
    for rel,digest in {**plan['allocation_inventory']['sources'],plan['census']['source_path']:plan['census']['source_sha256']}.items():
        require(sha(ROOT/rel)==digest,'memory census changed');sources[rel]=digest
    for name in ('rope.bf16','base-source-manifest.json','CACHE-POLICY.md','cache-policy-replay.json'):
        path=HERE/name;sources[str(path.relative_to(ROOT))]=sha(path)
    total=sum(p.stat().st_size for p in (HERE/'build').rglob('*') if p.is_file())
    require(total<=1_500_000_000,'build exceeds1.5GB')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,
        runtime_revision=revision,arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',
        sources=sources,artifacts=artifacts,gates=gates,retained_build_bytes=total,
        qualification='CPU preparation only; coordinator device windows pending')
    (HERE/'build-receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
    return row

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');args=ap.parse_args()
    if args.verify:
        row=read(HERE/'build-receipt.json')
        verify_files(ROOT,row['sources']);verify_files(HERE,row['artifacts']);verify_files(HERE,row['gates'])
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,build_bytes=row['retained_build_bytes'],source_count=len(row['sources']))))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as error:print('REFUSED: '+str(error),file=sys.stderr);sys.exit(1)
