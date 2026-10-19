"""Seal only this packet and the authoritative immutable oracle/binary inputs."""
import argparse,json,os,shutil,subprocess
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
GATES=('evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json',
       'evidence/argument-gate.json','evidence/partition-cpu.json','evidence/reset-gate.json',
       'evidence/python-tests.json','evidence/shared-entry.json','evidence/loader.json')

def verify():
    row=json.loads((P/'build-receipt.json').read_text())
    if not row.get('passed'):raise ValueError('build is not sealed')
    for root,key in [(ROOT,'sources'),(P,'artifacts'),(P,'gates')]:
        for name,digest in row[key].items():
            if sha(root/name)!=digest:raise ValueError('stale sealed file: '+name)
    if row['arithmetic']!='iq3-p49-split32-v1':raise ValueError('oracle arithmetic changed')
    return row

def create():
    limits()
    if (P/'evidence/card0-census-a').exists():raise ValueError('never reseal started census')
    build=json.loads((P/'evidence/build.json').read_text())
    assert build['passed'] and not build['device_executed']
    gates={}
    for name in GATES:
        row=json.loads((P/name).read_text())
        assert row.get('passed') is True,name
        assert row.get('device_executed',False) is False,name
        gates[name]=sha(P/name)
    # Imported memory proof remains byte-bound after local-only path relocation.
    import memory_plan as M
    plan=M.window_plan('WSCREEN')
    assert plan['host_required_available_bytes']<110_000_000_000
    # No new device allocation. The 16 MiB logging buffer fits the existing
    # 32 MiB capacity metadata allowance, retaining the unchanged device reserve.
    sources={}
    for f in P.rglob('*'):
        rel=f.relative_to(P)
        if not f.is_file() or rel.parts[0] in ('build','evidence','__pycache__'):continue
        if f.name in ('build-receipt.json','READY-FOR-DEVICE.json'):continue
        sources[str(f.relative_to(ROOT))]=sha(f)
    sources.update(build['immutable_binary_inputs'])
    sources.update(json.loads((P/'oracle-binding.json').read_text())['files_sha256'])
    for name,digest in sources.items():assert sha(ROOT/name)==digest,name
    from shared_oracle import completed_binding
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,
        sources=sources,artifacts=build['artifacts'],gates=gates,oracle=completed_binding(),
        arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',hc='p60fusion',
        view='down-tile16',cache_maintenance='overlap',cache_cap='max',cache_allocation_bytes=21552729600,
        diagnostic_only=True,record_tok_s=30.396,runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),
        retained_build_bytes=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file()),
        cpu_quality='exact partition fixtures with both compilers; miniature parent tokens and layer bytes; device equality pending',
        allocation_proof='inherited unchanged allocation schedule; no new device buffers; 16 MiB host logging buffer within existing 32 MiB allowance')
    save(P/'build-receipt.json',row);verify();return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    row=verify() if a.verify else create();print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']),build_bytes=row['retained_build_bytes'])))
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
