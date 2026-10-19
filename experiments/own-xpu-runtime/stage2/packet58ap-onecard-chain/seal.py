"""Seal the vendored candidate and CPU evidence; readiness is a separate gate."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,r):Path(p).write_text(json.dumps(r,indent=2)+'\n')
def require(ok,why):
    if not ok:raise ValueError(why)
def verify_files(root,files):
    require(bool(files),'empty closure')
    for n,h in files.items():require(sha(root/n)==h,'changed sealed input: '+n)
verify=verify_files
GATES=('k1-cpu.json','evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json','evidence/argument-gate.json','evidence/cpu-sequence.json','evidence/python-cpu-gates.json','evidence/submission-rehearsal.json')
def create():
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    require(not (P/'READY-FOR-DEVICE.json').exists(),'READY written last')
    require(not (P/'evidence/card0-58ap-a').exists(),'output must be fresh')
    parent=read(P/'parent-binding.json');verify_files(P,parent['sources'])
    require(sha(P/'build/device/p58-cache-fixtures-core')==parent['artifacts']['build/device/p58-cache-fixtures'],'inherited K1 core changed')
    adapter=read(P/'evidence/k1-adapter-build.json')
    require(adapter['binary_sha256']==sha(P/'build/device/p58-cache-fixtures') and adapter['source_sha256']==sha(P/'native/k1_cli.cpp'),'K1 adapter identity changed')
    archive=read(P/'native-artifacts.json');require(sha(P/archive['archive'])==archive['archive_sha256'],'vendored native archive changed');verify_files(P,archive['files'])
    artifacts=dict(parent['artifacts'])
    for leaf in ('build/device/p58-cache-fixtures','build/device/p58-cache-fixtures-core'):artifacts[leaf]=sha(P/leaf)
    verify_files(P,artifacts)
    gates={}
    for name in GATES:
        row=read(P/name);require(row.get('passed') is True and row.get('device_executed') is False,'CPU gate failed: '+name);gates[name]=sha(P/name)
        for source,digest in row.get('sources',{}).items():
            root=ROOT if source.startswith('experiments/') else P
            require(sha(root/source)==digest,'CPU proof source changed: '+source)
        if row.get('source_file'):require(sha(P/row['source_file'])==row['original_sha256'],'inherited proof changed: '+name)
        if row.get('evidence'):require(sha(P/row['evidence'])==row['evidence_sha256'],'inherited K1 proof changed')
    excluded={'build-receipt.json','submission-pins.json','ready.json','READY-FOR-DEVICE.json'}
    files=[f for f in P.glob('*') if f.is_file() and f.suffix in ('.py','.json','.md','.snapshot') and f.name not in excluded]
    for folder in ('host-admission','selections','lineage','native','screen-reader'):
        files += [f for f in (P/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
    sources={str(f.relative_to(ROOT)):sha(f) for f in files};sources.update(read(P/'oracle-binding.json')['files_sha256'])
    from shared_oracle import completed_binding
    from composition import DIMENSIONS
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,gates=gates,oracle=completed_binding(),arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',hc='p60fusion',**DIMENSIONS,lookups='resident',demand='bcs-demand-retained32x2',cache_maintenance='overlap',cache_cap='max',cache_allocation_bytes=21552729600,runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),retained_build_bytes=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file()),native_candidate_recompiled=False)
    save(P/'build-receipt.json',row)
    names=('packet58_submission.py','composition.py','submission_cli.py','shared_submission_cli.py','suite_metrics.py','submission-policy.json','record-threshold.snapshot')
    save(P/'submission-pins.json',dict(build_receipt_sha256=sha(P/'build-receipt.json'),sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in names},artifacts=artifacts))
    return row
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.verify:
        row=read(P/'build-receipt.json');verify_files(ROOT,row['sources']);verify_files(P,row['artifacts']);verify_files(P,row['gates']);pins=read(P/'submission-pins.json');verify_files(ROOT,pins['sources']);require(pins['build_receipt_sha256']==sha(P/'build-receipt.json'),'stale pins')
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']))))
if __name__=='__main__':main()
