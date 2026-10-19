#!/usr/bin/env python3
"""Seal the vendored chain and reused native bytes; never run native/full-shape gates."""
import argparse,hashlib,json,os,shutil,subprocess,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
GATES=('k1-cpu.json','evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json','evidence/startup-cpu.json','evidence/argument-gate.json','evidence/python-cpu-gates.json','evidence/submission-rehearsal.json','evidence/native-entry.json','evidence/native-parser.json')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,why):
    if not ok:raise ValueError(why)
def verify_files(root,files):
    require(bool(files),'empty closure')
    for name,digest in files.items():
        require(sha(root/name)==digest,'changed input: '+name)
def create():
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    require(set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'helper cores required')
    require(shutil.disk_usage('/').free>=25_000_000_000,'root below 25 GB')
    require(not (P/'evidence/card0-58ah-b').exists(),'never reseal started chain')
    artifacts=read(P/'copy-manifest.json')['native_artifacts'];verify_files(P,artifacts)
    parent=read(P/'lineage/58ag-build-receipt.json')
    require(all(parent['artifacts'][n]==h for n,h in artifacts.items()),'58ag artifact differs')
    gates={}
    for n in GATES:
        row=read(P/n)
        require(row.get('passed') is True and row.get('device_executed') is False,'gate failed: '+n)
        if row.get('sources'):verify_files(ROOT,row['sources'])
        gates[n]=sha(P/n)
    binding=read(P/'parent-binding.json');verify_files(ROOT,binding['sources'])
    for name in ('fullshape-submit-cpu','postload-allocation-cpu','startup-cpu'):
        inherited=read(P/f'evidence/{name}.json')
        original=read(P/inherited['source_file'])
        require(sha(P/inherited['source_file'])==inherited['original_sha256'],'inherited proof changed')
        require(original['passed'] is True and original['device_executed'] is False,'inherited proof failed')
        require(original['binary_sha256']==inherited['binary_sha256'] and inherited['binary_sha256'] in artifacts.values(),'inherited binary differs')
    args=read(P/'evidence/argument-gate.json')
    order=['K1a','K1b','KD','W2m','WS','WS128x','WS128']
    require([r['window'] for r in args['records']]==order,'seven entries required')
    require(len(args['negative_records'])==28 and all(r['refused'] for r in args['negative_records']),'entry refusals required')
    require(all(r['native_exec_intercepted'] and r['real_unit_and_environment_gates'] and r['resource_limits_unchanged'] for r in args['records']),'real entry proof missing')
    from views import validate
    validate('down-tile16')
    from shared_oracle import completed_binding
    oracle=completed_binding()
    files=[*P.glob('*.py'),*P.glob('*.json'),P/'record-threshold.snapshot',*P.glob('*.md')]
    for directory in ('host-admission','screen-reader','selections','lineage'):
        files += [f for f in (P/directory).rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name!='58ad-chain-a-rehearsal.json.gz']
    sources={str(f.relative_to(ROOT)):sha(f) for f in files if f.name not in ('build-receipt.json','submission-pins.json','ready.json') or f.parent!=P}
    sources.update(read(P/'oracle-binding.json')['files_sha256'])
    sources.update(binding['sources'])
    verify_files(ROOT,sources)
    size=sum((P/n).stat().st_size for n in artifacts);require(size<=300_000_000,'build over 300 MB')
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,gates=gates,arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',hc='p60fusion',hc_geometry='hc-wide',experts='wide64+halfcache',other_fusion='fused',retirement='ordered-foreground',cache_maintenance='overlap',cache_cap='max',cache_allocation_bytes=21552729600,view='down-tile16',runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),native_recompiled=False,retained_build_bytes=size,oracle=oracle,parent_build_sha256=sha(P/'lineage/58ag-build-receipt.json'),qualification='Inherited hash-bound 58ag native CPU gates; new seven-window entry replay and policy tests. Device chain pending.')
    (P/'build-receipt.json').write_text(json.dumps(row,indent=2)+'\n')
    pins={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('packet58_submission.py','composition.py','submission_cli.py','shared_submission_cli.py','suite_metrics.py','submission-policy.json','record-threshold.snapshot')}
    (P/'submission-pins.json').write_text(json.dumps(dict(schema='packet58ah.submission-pins.v1',build_receipt_sha256=sha(P/'build-receipt.json'),sources=pins,artifacts=artifacts,finalized_before_chain=True),indent=2)+'\n')
    return row
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.verify:
        row=read(P/'build-receipt.json')
        for root,key in [(ROOT,'sources'),(P,'artifacts'),(P,'gates')]:verify_files(root,row[key])
        pins=read(P/'submission-pins.json');verify_files(ROOT,pins['sources'])
        require(pins['build_receipt_sha256']==sha(P/'build-receipt.json'),'submission pins stale')
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']),build_bytes=row['retained_build_bytes'])))
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
