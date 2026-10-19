"""One-time CPU-only chain reseal; preserve the completed screen's exact seal."""
import hashlib,json,os,resource,subprocess
from pathlib import Path
O=Path(__file__).resolve().parent
ROOT=O.parents[3]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident'
B=P/'lineage/packet58ajc-before'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,row):p.write_text(json.dumps(row,indent=2)+'\n')
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert not (P/'READY-FOR-DEVICE.json').exists() and not (O/'READY-FOR-DEVICE.json').exists()
    assert not (P/'evidence/card0-58aj-a').exists()
    old=read(B/'build-receipt.json');row=read(B/'build-receipt.json')
    changes={}
    for name,digest in old['sources'].items():
        path=ROOT/name;current=sha(path)
        if current!=digest:
            snapshot=B/path.resolve().name
            assert path.resolve().parent==P and snapshot.is_file() and sha(snapshot)==digest, name
            changes[name]=dict(before=digest,after=current)
            row['sources'][name]=current
    for name,digest in row['artifacts'].items():assert sha(P/name)==digest,name
    # No completed screen source, summary, receipt or binary is rewritten.
    for path in B.rglob('*'):
        if path.is_file():row['sources'][str(path.relative_to(ROOT))]=sha(path)
    for name in ('evidence/python-cpu-gates.json','evidence/submission-rehearsal.json'):
        gate=read(P/name);assert gate['passed'] and gate['device_executed'] is False
        if gate.get('sources'):
            for n,h in gate['sources'].items():assert sha(ROOT/n)==h,n
        row['gates'][name]=sha(P/name)
    for n,h in row['gates'].items():assert sha(P/n)==h,n
    entry=read(O/'58ajc-entry-rehearsal.json');assert entry['passed']
    assert all(j['report']['passed'] for j in entry['jobs'])
    row.update(native_recompiled=False,
        runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),
        qualification='58ajc post-result readiness amendment only; native artifacts and completed 58ajb screen unchanged.',
        readiness_amendment=dict(changes=changes,prior_build_sha256=sha(B/'build-receipt.json'),
            completed_screen_build_sha256=sha(P/'screen/build-receipt.json')))
    save(P/'build-receipt.json',row)
    pins=read(B/'submission-pins.json');pins['build_receipt_sha256']=sha(P/'build-receipt.json')
    pins['sources']={n:sha(ROOT/n) for n in pins['sources']}
    save(P/'submission-pins.json',pins)
    save(O/'58ajc-reseal.json',dict(passed=True,device_executed=False,native_recompiled=False,
        changed_sources=changes,native_artifacts=row['artifacts'],
        screen_build_sha256=sha(P/'screen/build-receipt.json'),
        new_build_sha256=sha(P/'build-receipt.json')))
    print('Minimal chain reseal; completed screen and all native artifacts unchanged')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000));main()
