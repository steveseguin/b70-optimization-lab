"""Bind finished packet58ab outputs read-only; no build, device or model reads."""
import hashlib,json,os,resource,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[4]
P=R/'experiments/own-xpu-runtime/stage2/packet58ad-onecard-record'
A=P.parent/'packet58ab-onecard-hcfusion'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,row):p.write_text(json.dumps(row,indent=2)+'\n')
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert not (P/'parent-binding.json').exists(),'binding is immutable; never silently repin'
    marker=read(A/'READY-FOR-DEVICE.json');build=read(A/'build-receipt.json')
    assert marker['build_receipt_sha256']==sha(A/'build-receipt.json')
    assert build['passed'] and build['device_executed'] is False
    assert build['hc']==['production','p60fusion'] and build['cache_maintenance']=='overlap'
    assert build['cache_allocation_bytes']==21552729600 and build['arithmetic']=='iq3-p49-split32-v1'
    names=['READY-FOR-DEVICE.json','build-receipt.json','selections/tile16.json','views.py','suite_driver.py','suite_metrics.py','compare_bracket.py','exec_limits.py','oracle-binding.json','k1-cpu.json','dispatch-speed6.json','library-path.json','native_source.py','hc_source.py','sources/main.cpp','native/bracket_table.hpp']
    gates=['fullshape-submit-cpu','postload-allocation-cpu','startup-cpu','hc-gates','protocol-gates','k1-async-cpu']
    names += ['evidence/'+n+'.json' for n in gates]
    pins={str((A/n).relative_to(R)):sha(A/n) for n in names}
    for n in ('oracle-binding.json','dispatch-speed6.json'):
        assert (P/n).read_bytes()==(A/n).read_bytes(),'shared identity differs: '+n
    assert read(P/'library-path.json')['LD_LIBRARY_PATH']==read(A/'library-path.json')['LD_LIBRARY_PATH'],'loader environment differs'
    # The shared guard admits parent ELF bytes, not live mutable sibling source
    # pins. Vendor the finished outputs and pin the exact copied bytes instead.
    snapshots={}
    for n in names:
        dst=P/'lineage/58ab-snapshot'/n;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(A/n,dst)
        assert sha(dst)==pins[str((A/n).relative_to(R))]
        snapshots[str(dst.relative_to(R))]=sha(dst)
    artifacts={n:h for n,h in build['artifacts'].items() if n in ('build/gnu-host/own-rt-iq3','build/device/own-rt-iq3','build/gnu-host/fullshape-submit','build/gnu-host/p58-cache-fixtures','build/device/p58-cache-fixtures')}
    assert len(artifacts)==5
    size=sum((A/n).stat().st_size for n in artifacts)
    assert size<300_000_000 and shutil.disk_usage('/').free-size>=25_000_000_000
    for n,h in artifacts.items():
        assert sha(A/n)==h
        dest=P/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(A/n,dest);assert sha(dest)==h
    for n in ('READY-FOR-DEVICE.json','build-receipt.json'):
        shutil.copy2(A/n,P/'lineage'/('58ab-'+n))
    for n in gates:
        src=A/'evidence'/f'{n}.json';row=read(src)
        assert row['passed'] is True and row['device_executed'] is False
        assert build['gates']['evidence/'+n+'.json']==sha(src)
        shutil.copy2(src,P/'lineage'/('58ab-'+n+'.json'))
        if n in gates[:3]:
            save(P/'evidence'/f'{n}.json',dict(passed=True,device_executed=False,inherited=True,
                original_sha256=sha(src),source_file='lineage/58ab-'+n+'.json',binary_sha256=row['binary_sha256']))
    reader=P/'screen-reader';reader.mkdir(exist_ok=True)
    for n in ('views.py','suite_driver.py','suite_metrics.py','compare_bracket.py','exec_limits.py','oracle-binding.json'):
        raw=(A/n).read_text()
        if n=='suite_driver.py':raw=raw.replace('ROOT = HERE.parents[3]','ROOT = HERE.parents[4]').replace("ORACLE = HERE.parent /", "ORACLE = HERE.parents[1] /")
        (reader/n).write_text(raw)
    (reader/'selections').mkdir(exist_ok=True)
    for dest in (reader/'selections/tile16.json',P/'selection.json',P/'selections/down-tile16.json'):
        shutil.copy2(A/'selections/tile16.json',dest)
    k1=read(A/'k1-cpu.json');local_sources={}
    for name,digest in k1['sources'].items():
        source=R/name;relative=source.relative_to(A)
        dest=P/'lineage/58ab-k1-inputs'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        assert sha(source)==digest;shutil.copy2(source,dest);assert sha(dest)==digest
        local_sources[str(dest.relative_to(R))]=digest
    k1['sources']=local_sources
    k1['inherited_original_sha256']=sha(A/'k1-cpu.json')
    save(P/'k1-cpu.json',k1)
    for n,h in pins.items():assert sha(R/n)==h,'parent changed during binding'
    save(P/'copy-manifest.json',dict(native_source=str(A.relative_to(R)),native_artifacts=artifacts,native_recompiled=False,template='packet58z-onecard-record'))
    save(P/'parent-binding.json',dict(schema='packet58ad.parent-binding.v1',sources=snapshots,
        origin_packet=str(A.relative_to(R)),binding_mode='Exact final output snapshots; no mutable sibling source pins or imports',
        parent_ready_for_device_at_binding=marker.get('ready_for_device'),
        parent_build_sha256=sha(A/'build-receipt.json'),parent_ready_sha256=sha(A/'READY-FOR-DEVICE.json'),
        selection_sha256=sha(A/'selections/tile16.json'),runtime_hc='p60fusion',
        evidence_root=str((A/'evidence/card0-hcfusion-a').relative_to(R)),native_artifacts=artifacts))
    print('Bound packet58ab READY, build, selection, CPU proofs and five binaries by hash; no launch')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
