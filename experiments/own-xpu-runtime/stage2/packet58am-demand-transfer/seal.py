"""Bind CPU proofs and private source identity; never release a device run."""
import json,shutil
from pathlib import Path
from prepare import P,ROOT,AH,sha,save
from build_engine import limits
from admit import plan
def main():
    limits()
    build=json.loads((P/'evidence/build.json').read_text())
    assert build['passed'] and not build['device_executed']
    for name,digest in build['sources'].items():
        if name.startswith(('native/','build/native/','vendor/')):
            assert sha(P/name)==digest,'compiled source changed: '+name
    for name,digest in build['artifacts'].items():assert sha(P/name)==digest
    closure=json.loads((P/'lineage/source-closure.json').read_text())
    for row in closure['files']:
        assert sha(ROOT/row['source'])==row['before'],'frozen parent changed'
        assert sha(P/row['destination'])==row['after'],'private closure changed'
    override=json.loads((P/'lineage/coordinator-override.json').read_text())
    assert sha(P.parent/'packet58al-demand-transfer-prep/DECISION.md')==override['decision_sha256']
    assert sha(P/'oracle-binding.json')==sha(AH/'oracle-binding.json')
    proofs={}
    for name in ('build','bytes','ownership','preparation','parent-replay','python-tests'):
        path=P/f'evidence/{name}.json';row=json.loads(path.read_text());assert row['passed'],name
        assert row.get('device_executed',False) is False,name
        if name=='bytes':
            for source,digest in row['sources'].items():assert sha(P/source)==digest,'byte proof source changed'
        proofs[str(path.relative_to(P))]=sha(path)
    prep=json.loads((P/'evidence/preparation.json').read_text())
    proposals={}
    for kind,record in zip(('smoke','v5'),prep['records']):
        path=P/f'proposals/{kind}.json';proposal=json.loads(path.read_text());plan(proposal)
        assert record['proposal_sha256']==sha(path)
        assert record['real_argv']==proposal['native_argv']
        assert record['binary_sha256']==sha(Path(proposal['native_argv'][0]))
        assert record['no_model_or_device_open'] and sha(P/record['syscall_trace'])==record['syscall_trace_sha256']
        proposals[str(path.relative_to(P))]=sha(path)
    for name in ('allocation-plan.json','storage-budget.json'):
        assert json.loads((P/name).read_text())['passed'];proofs[name]=sha(P/name)
    proofs['wait-budget.json']=sha(P/'wait-budget.json')
    artifacts=build['artifacts']|{'build/device/p58-cache-fixtures':sha(P/'build/device/p58-cache-fixtures')}
    evidence={str(f.relative_to(P)):dict(sha256=sha(f),bytes=f.stat().st_size) for f in sorted((P/'evidence').rglob('*')) if f.is_file() and f.name!='inventory.json'}
    save(P/'evidence/inventory.json',dict(device_executed=False,files=evidence))
    sources={str(f.relative_to(P)):sha(f) for f in sorted(P.rglob('*')) if f.is_file() and
             (f.parent==P and f.suffix in ('.py','.md') or f.relative_to(P).parts[0] in ('native','inputs','proposals') or str(f.relative_to(P)).startswith('build/native/'))}
    footprint=sum(f.stat().st_size for f in P.rglob('*') if f.is_file());assert footprint<300000000
    receipt=dict(schema='packet58am.build.v1',passed=True,cpu_prepared=True,ready_for_device=False,
        conditional_smoke_ready=False,v5_ready=False,device_executed=False,variant='bcs-demand-retained32x2',
        parent='packet58ah chain b',parent_tok_s=31.66271941826957,oracle='iq3-p49-split32-v1',
        release_condition='packet58ai census bound >= 1.000 ms/token',
        source_closure_sha256=sha(P/'lineage/source-closure.json'),sources=sources,artifacts=artifacts,
        proofs=proofs,proposals=proposals,evidence_inventory_sha256=sha(P/'evidence/inventory.json'),
        footprint_bytes=footprint,root_free_bytes=shutil.disk_usage('/').free,
        coordinator_entry='inert native command specifications; coordinator whole-host wrapper required',
        pending=['complete valid census release','actual device oracle parity and event clocks','same-parent overlap smoke before v5','v5 storage refresh from actual smoke'])
    save(P/'build-receipt.json',receipt)
    save(P/'seal.json',dict(schema='packet58am.seal.v1',passed=True,device_executed=False,
         build_receipt_sha256=sha(P/'build-receipt.json'),proofs=proofs,proposals=proposals,artifacts=artifacts,
         frozen_decision_sha256=override['decision_sha256']))
    print('CPU seal PASS; device readiness remains false; footprint',footprint)
if __name__=='__main__':main()
