"""Seal this CPU-qualified copy; refuse mutable outputs and any source drift."""
import argparse,json,os,subprocess
from pathlib import Path
from build_engine import sha,save,limits
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
GATES=('evidence/build.json','evidence/lookup-inventory.json','evidence/resident-copy-cpu.json','evidence/resident-engine-cpu.json','evidence/postload-allocation-cpu.json','evidence/fullshape-submit-cpu.json','evidence/startup-cpu.json','evidence/budget-cpu.json','evidence/python-cpu-gates.json','evidence/argument-gate.json','evidence/screen-argument-gate.json','evidence/drain-fix.json','evidence/teardown-integration.json','k1-cpu.json')
def verify_files(root,files):
    for name,digest in files.items():
        p=(root/name).resolve();assert p.is_relative_to(ROOT) and sha(p)==digest,'changed sealed input: '+name

def create():
    limits()
    assert not (P/'evidence/card0-58t-a').exists() and not (P/'evidence/card0-resident-a').exists(),'never reseal a started experiment'
    sources={};gates={}
    built=json.loads((P/'evidence/build.json').read_text())
    for leaf in GATES:
        r=json.loads((P/leaf).read_text());assert r['passed'] is True and r['device_executed'] is False,leaf
        pins=r.get('sources',{});verify_files(ROOT,pins);sources.update(pins);gates[leaf]=sha(P/leaf)
    for leaf,n in [('argument-gate.json',12),('screen-argument-gate.json',4)]:
        r=json.loads((P/'evidence'/leaf).read_text());assert r['checks']==n
        assert all(x['native_exec_intercepted'] and x['resource_limits_unchanged'] and not x['finite_address_space_limit'] for x in r['records'])
    assert json.loads((P/'evidence/fullshape-submit-cpu.json').read_text())['checks']==12
    assert len(json.loads((P/'evidence/budget-cpu.json').read_text())['records'])==8
    assert json.loads((P/'evidence/resident-engine-cpu.json').read_text())['frozen58p_output_equal']
    artifacts=dict(built['artifacts'])
    parent=json.loads((P/'copy-manifest.json').read_text())
    for mode in ('device','gnu-host'):
        name=f'build/{mode}/p58-cache-fixtures';original=str((P.parent/'packet58p-onecard-record'/name).relative_to(ROOT))
        assert sha(P/name)==parent[original] and os.access(P/name,os.X_OK);artifacts[name]=sha(P/name)
    for f in [*P.glob('*.py'),*P.glob('*.json'),*P.glob('native/*'),*P.glob('sources/*'),*P.glob('selections/*')]:
        if f.name in ('build-receipt.json','ready.json'):continue
        sources[str(f.relative_to(ROOT))]=sha(f)
    sources.update(json.loads((P/'oracle-binding.json').read_text())['files_sha256'])
    for folder in ('evidence/58c-supervisor','evidence/58c-kd'):
        for f in (P/folder).rglob('*'):
            if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
    assert not any('/ops/' in name or name.endswith('/ready.json') for name in sources)
    verify_files(ROOT,sources);verify_files(P,artifacts)
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());assert size<=200_000_000
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,gates=gates,
        runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),retained_build_bytes=size,
        arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',native_recompiled=True,
        resident_lookup_bytes=29321610240,immutable_inputs_only=True,qualification='CPU only; full-size resident load, packet49 device equality and speed pending')
    save(P/'build-receipt.json',row);return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.verify:
        row=json.loads((P/'build-receipt.json').read_text())
        for root,key in ((ROOT,'sources'),(P,'artifacts'),(P,'gates')):verify_files(root,row[key])
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']),build_bytes=row['retained_build_bytes'])))
if __name__=='__main__':main()
