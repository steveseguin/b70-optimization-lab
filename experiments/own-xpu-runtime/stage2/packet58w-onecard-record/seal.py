#!/usr/bin/env python3
"""Seal a fresh 58w chain, reused 58v artifacts and finished CPU launch gates."""
import argparse,hashlib,json,os,resource,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
GATES=('k1-cpu.json','evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json',
       'evidence/startup-cpu.json','evidence/argument-gate.json','evidence/python-cpu-gates.json',
       'evidence/budget-cpu.json','evidence/drain-fix.json','evidence/oracle-gate.json','evidence/literal-audit.json')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,why):
    if not ok:raise ValueError(why)
def verify_files(root,files):
    require(bool(files),'empty input closure')
    for name,digest in files.items():
        path=(root/name).resolve()
        require(path.is_relative_to(ROOT) and sha(path)==digest,'changed immutable input: '+name)
def create():
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    require(set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'helper cores required')
    require(shutil.disk_usage('/').free>=25_000_000_000,'root free below 25 GB')
    require(not (P/'evidence/card0-58w-a').exists(),'never reseal a started chain')
    parent=read(P/'lineage/58v-build-receipt.json')
    require(parent==read(P.parent/'packet58v-async-cache/build-receipt.json'),'parent build changed')
    verify_files(ROOT,parent['sources']);verify_files(P,parent['artifacts']);verify_files(P.parent/'packet58v-async-cache',parent['gates'])
    # Retain the complete native/host source closure from the reused engine.
    sources=dict(parent['sources']);artifacts=dict(parent['artifacts']);gates={}
    for name,digest in parent['gates'].items():
        f=P.parent/'packet58v-async-cache'/name
        require(read(f).get('passed') is True and read(f).get('device_executed') is False,'inherited CPU gate failed')
        sources[str(f.relative_to(ROOT))]=digest
    sources[str((P.parent/'packet58v-async-cache/build-receipt.json').relative_to(ROOT))]=sha(P/'lineage/58v-build-receipt.json')
    for name in GATES:
        r=read(P/name)
        require(r.get('passed') is True and r.get('device_executed') is False,'CPU gate failed: '+name)
        if r.get('sources'):verify_files(ROOT,r['sources']);sources.update(r['sources'])
        gates[name]=sha(P/name)
    args=read(P/'evidence/argument-gate.json')
    order=['K1a','K1b','KD','W2m','WS','WS128x','WS128']
    require([r['window'] for r in args['records']]==order,'all seven actual entries required')
    require(all(r['real_queue_entry'] and r['real_unit_and_environment_gates'] and r['topology'] and r['host_admission_logic_real'] and r['native_exec_intercepted'] and r['resource_limits_unchanged'] and not r['finite_address_space_limit'] for r in args['records']),'launch path gate incomplete')
    require({(r['window'],r['entry'],r['negative']) for r in args['negative_records']}=={(w,e,n) for w in order for e in ('queue','window') for n in ('unit','env')} and all(r['refused'] for r in args['negative_records']),'wrong unit/env must fail for every entry')
    full=read(P/'evidence/fullshape-submit-cpu.json');startup=read(P/'evidence/startup-cpu.json')
    for row in (full,startup):
        require(row['checks']==5 and [r['window'] for r in row['records']]==order[2:],'full model window coverage')
    require(full['binary_sha256']==artifacts['build/gnu-host/fullshape-submit'],'wrong fullshape binary')
    require(startup['binary_sha256']==artifacts['build/gnu-host/own-rt-iq3'] and startup['fullshape_receipt_sha256']==sha(P/'evidence/fullshape-submit-cpu.json'),'parser proof identity')
    k=read(P/'k1-cpu.json')
    require(k['binary_sha256']==artifacts['build/gnu-host/p58-cache-fixtures'] and all(k[x] for x in ('mixed_bytes_equal','zero_copy_bytes_equal','streamed_bytes_equal')),'K1 byte equality missing')
    from views import validate,digest
    validate('down-tile16');require(sha(P/'selection.json')==digest('down-tile16'),'selection alias differs')
    from shared_oracle import completed_binding
    oracle=completed_binding();require(oracle==read(P/'evidence/oracle-gate.json'),'oracle binding differs')
    files=[*P.glob('*.py'),*P.glob('*.json')]
    for folder in ('lineage','selections','host-admission','screen-reader','evidence/58c-kd','evidence/58c-supervisor'):
        files += [f for f in (P/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
    for f in files:
        if f.parent==P and f.name in ('build-receipt.json','submission-pins.json','ready.json'):continue
        require(not f.is_symlink() or f.resolve().is_relative_to(ROOT),'external oracle must be checked through shared_oracle')
        sources[str(f.relative_to(ROOT))]=sha(f)
    sources.update(read(P/'oracle-binding.json')['files_sha256'])
    for name in ('scripts/submit_localmaxxing_results.py','scripts/packet49_submission.py'):
        if (ROOT/name).exists():sources[name]=sha(ROOT/name)
    verify_files(ROOT,sources)
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file())
    require(size<=300_000_000,'build exceeds 300 MB')
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,gates=gates,
        arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',cache_maintenance='overlap',view='down-tile16',
        runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),
        parent_build_sha256=sha(P/'lineage/58v-build-receipt.json'),native_recompiled=False,retained_build_bytes=size,oracle=oracle,
        qualification='CPU preparation only; exact smoke and winning v5 bracket required before fresh chain')
    (P/'build-receipt.json').write_text(json.dumps(row,indent=2)+'\n')
    pins={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('packet58_submission.py','submission_cli.py','suite_metrics.py','submission-policy.json','record-threshold.json')}
    (P/'submission-pins.json').write_text(json.dumps(dict(schema='packet58w.submission-pins.v1',build_receipt_sha256=sha(P/'build-receipt.json'),sources=pins,artifacts=artifacts,finalized_before_chain=True),indent=2)+'\n')
    return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.verify:
        row=read(P/'build-receipt.json');verify_files(ROOT,row['sources']);verify_files(P,row['artifacts']);verify_files(P,row['gates'])
        pins=read(P/'submission-pins.json');verify_files(ROOT,pins['sources'])
        require(pins['build_receipt_sha256']==sha(P/'build-receipt.json') and pins['artifacts']==row['artifacts'],'submission pins stale')
        from shared_oracle import completed_binding
        require(completed_binding()==row['oracle'],'oracle binding changed')
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']),build_bytes=row['retained_build_bytes'])))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
