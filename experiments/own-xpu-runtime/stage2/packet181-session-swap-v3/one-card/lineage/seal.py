#!/usr/bin/env python3
"""Seal the private chain and screen after all new CPU gates; never launch."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];Q=P/'screen'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,r):p.write_text(json.dumps(r,indent=2)+'\n')
def require(ok,why):
    if not ok:raise ValueError(why)
def verify_files(root,files):
    require(bool(files),'empty closure')
    for n,h in files.items():require(sha(root/n)==h,'changed sealed input: '+n)
verify=verify_files
ROOT_GATES=('k1-cpu.json','evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json',
    'evidence/argument-gate.json','evidence/python-cpu-gates.json','evidence/submission-rehearsal.json',
    'evidence/native-parser.json','evidence/resident-copy-cpu.json','evidence/resident-engine-cpu.json',
    'evidence/entry-gates.json','evidence/packet58ajb-preparation.json')
SCREEN_GATES=('evidence/argument-gate.json','evidence/python-cpu-gates.json','evidence/fullshape-submit-cpu.json',
    'evidence/postload-allocation-cpu.json','evidence/report-gate.json','evidence/entry-gates.json')
def gates(root,names):
    result={}
    for name in names:
        row=read(root/name)
        require(row.get('passed') is True and row.get('device_executed') is False,'CPU gate failed: '+name)
        if row.get('sources'):verify_files(ROOT,row['sources'])
        result[name]=sha(root/name)
    return result

def create():
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    require(set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'helper cores required')
    require(shutil.disk_usage('/').free>=27_000_000_000,'root below 27 GB')
    require(not (P/'READY-FOR-DEVICE.json').exists(),'READY is written last; no reseal')
    require(not (P/'evidence/card0-58aj-a').exists() and not (Q/'evidence/card0-58ajb-screen-a').exists(),'never reseal started outputs')
    history=read(P/'evidence/packet58ajb-diagnosis.json');verify_files(ROOT,history['failed_evidence_sha256'])
    built=read(P/'evidence/build.json');require(built['passed'] and not built['device_executed'],'native builds missing')
    artifacts=built['artifacts'];verify_files(P,artifacts)
    require(len(artifacts)==6 and 'build/intel-host/own-rt-iq3' in artifacts,'all six native artifacts required')
    for name in ('resident-copy-cpu','resident-engine-cpu'):
        require(read(P/'evidence'/f'{name}.json')['passed'],'lookup proof failed')
    exact=read(P/'evidence/resident-engine-cpu.json')
    require(exact['frozen58ah_output_equal'] and exact['cross_compiler_equal'] and exact['bracket_reset_equal'] and exact['wrong_oracle_refused'],'exact output/reset gates incomplete')
    rg=gates(P,ROOT_GATES);sg=gates(Q,SCREEN_GATES)
    # These inherited shape probes execute unchanged fullshape-submit bytes;
    # new host copy paths have their own GNU/Intel and engine reset proofs.
    for leaf in ('fullshape-submit-cpu','postload-allocation-cpu'):
        row=read(P/'evidence'/f'{leaf}.json')
        require(row['binary_sha256'] in artifacts.values(),'inherited shape binary changed')
    from shared_oracle import completed_binding
    oracle=completed_binding()
    from composition import DIMENSIONS
    from views import validate
    validate('down-tile16')
    excluded={'build-receipt.json','submission-pins.json','ready.json','READY-FOR-DEVICE.json'}
    files=[f for f in P.glob('*') if f.is_file() and f.suffix in ('.py','.json','.md','.snapshot') and f.name not in excluded]
    for folder in ('host-admission','selections','native','frozen-inputs','lineage'):
        files.extend(f for f in (P/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts)
    screen_files=[f for f in Q.glob('*') if f.is_file() and f.suffix in ('.py','.json','.txt') and f.name not in excluded]
    sources={str(f.relative_to(ROOT)):sha(f) for f in files+screen_files}
    sources.update(read(P/'oracle-binding.json')['files_sha256'])
    # Every local dependency is hashed, including symlink-target object bytes.
    for f in (P/'build').rglob('*'):
        if f.is_file() and f.suffix in ('.o','.hpp','.cpp'):sources[str(f.relative_to(ROOT))]=sha(f)
    verify_files(ROOT,sources)
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());require(size<=300_000_000,'build over 300 MB')
    common=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,
        arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',hc='p60fusion',**DIMENSIONS,
        lookups='resident',cache_maintenance='overlap',cache_cap='max',cache_allocation_bytes=21552729600,
        retained_build_bytes=size,oracle=oracle,native_recompiled=True,
        runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),
        qualification='New exact lookup copies and request resets on GNU/Intel; unchanged inherited full-shape probes. Device parity/performance pending.')
    save(Q/'build-receipt.json',dict(common,gates=sg,view='resident',bracket_profiles=['mapped','resident']))
    chain_sources=dict(sources);chain_sources[str((Q/'build-receipt.json').relative_to(ROOT))]=sha(Q/'build-receipt.json')
    save(P/'build-receipt.json',dict(common,sources=chain_sources,gates=rg,view='down-tile16'))
    names=('packet58_submission.py','composition.py','submission_cli.py','shared_submission_cli.py','suite_metrics.py','submission-policy.json','record-threshold.snapshot')
    save(P/'submission-pins.json',dict(schema='packet58aj.submission-pins.v1',build_receipt_sha256=sha(P/'build-receipt.json'),sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in names},artifacts=artifacts,finalized_before_chain=True))
    return common

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');args=ap.parse_args()
    if args.verify:
        for root in (P,Q):
            row=read(root/'build-receipt.json')
            # Completed 58ajb screen retains its original seal and comparator.
            # Historical root sources changed by 58ajc have exact saved bytes;
            # the chain seal above binds both those bytes and current sources.
            for name,digest in row['sources'].items():
                historical=P/'lineage/packet58ajc-before'/(ROOT/name).resolve().name
                direct=(ROOT/name).resolve().parent==P
                if root==Q and direct and historical.is_file():
                    require(sha(historical)==digest,'historical screen source changed: '+name)
                else:require(sha(ROOT/name)==digest,'changed sealed input: '+name)
            for where,key in ((root,'artifacts'),(root,'gates')):verify_files(where,row[key])
        pins=read(P/'submission-pins.json');verify_files(ROOT,pins['sources']);require(pins['build_receipt_sha256']==sha(P/'build-receipt.json'),'stale submission pins')
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']),build_bytes=row['retained_build_bytes'])))
if __name__=='__main__':main()
