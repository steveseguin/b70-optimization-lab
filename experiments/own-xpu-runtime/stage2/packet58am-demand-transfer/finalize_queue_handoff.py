"""Seal the CPU-qualified resident-parent screen; write READY only after gates."""
import ast,json,subprocess,shutil
from pathlib import Path
from packet_io import P,ROOT,sha,save
from build_engine import limits
RELEASE='coordinator direct-screen release (RELEASE-AMENDMENT.md)'

def read(name):return json.loads((P/name).read_text())
def main():
    limits()
    old=read('lineage/p58amc-before/READY-FOR-DEVICE.json')
    assert sha(P/'lineage/DECISION.md')==old['frozen_decision_sha256']
    assert sha(P.parent/'packet58al-demand-transfer-prep/DECISION.md')==old['frozen_decision_sha256']
    build=read('evidence/build.json');assert build['passed'] and not build['device_executed']
    for name,h in build['sources'].items():
        if name.startswith(('native/','build/native/','vendor/')):assert sha(P/name)==h,name
    artifacts=dict(build['artifacts'])
    artifacts['build/device/p58-cache-fixtures']=old['artifacts']['build/device/p58-cache-fixtures']
    artifacts['build/device/p58-cache-fixtures-cli']=read('evidence/k1-cli.json')['binary_sha256']
    for name,h in artifacts.items():assert sha(P/name)==h,name
    closure=read('lineage/source-closure.json')
    for row in closure['files']:
        assert sha(ROOT/row['source'])==row['before'],'original changed: '+row['source']
        assert sha(P/row['destination'])==row['after'],'private source changed: '+row['destination']
    for row in read('lineage/resident-port.json')['files']:
        assert sha(ROOT/row['source'])==row['source_sha256']
        assert sha(P/row['destination'])==row['source_sha256']
    for row in read('lineage/harness58aj.json')['files']:
        assert sha(ROOT/row['source'])==row['source_sha256']
        assert sha(P/row['snapshot'])==row['source_sha256']
    proofs={}
    for name in ('build','bytes','ownership','preparation','parent-replay','resident-parent-replay',
                 'python-tests','resident-cpu','k1-cli','p58an-flags','p58an-imports','p58an-preparation',
                 'p58an-analyzer-audit'):
        path=f'evidence/{name}.json';row=read(path);assert row['passed'],path
        assert row.get('device_executed',False) is False,path
        assert row.get('max_rss_bytes',0)<4*1024**3,path
        proofs[path]=sha(P/path)
    for source,h in read('evidence/bytes.json')['sources'].items():assert sha(P/source)==h
    for source,h in read('evidence/resident-cpu.json')['sources'].items():assert sha(P/source)==h
    assert read('evidence/resident-cpu.json')['engine_binary_sha256']==artifacts['build/gnu-host/own-rt-iq3']
    for r in read('evidence/bytes.json')['records']:
        assert sha(P/'build'/f"{r['compiler']}-demand-bytes")==r['binary_sha256']
    checks=read('evidence/p58an-checks.json');assert all(r['returncode']==0 for r in checks['records'])
    proofs['evidence/p58an-checks.json']=sha(P/'evidence/p58an-checks.json')
    proposals={};rows={};warnings={}
    prep=read('evidence/preparation.json')
    for i,kind in enumerate(('smoke','v5')):
        path=P/f'proposals/{kind}.json';v=json.loads(path.read_text());assert not Path(v['output']).exists()
        rec=prep['records'][i];assert rec['proposal_sha256']==sha(path) and rec['real_argv']==v['native_argv']
        assert rec['binary_sha256']==artifacts['build/device/own-rt-iq3']
        assert rec['no_model_or_device_open'] and sha(P/rec['syscall_trace'])==rec['syscall_trace_sha256']
        proposals[str(path.relative_to(P))]=sha(path)
        rowpath=ROOT/f'experiments/own-xpu-runtime/ops/lane-queue/proposed-p58am-{kind}-A.txt'
        row=json.loads(next(x for x in rowpath.read_text().splitlines() if x.startswith('{')))
        assert row['name']==v['job_name'] and row['lane']=='A'
        assert row['argv'][row['argv'].index('--output')+1]==v['output']
        assert row['argv'][2]==str((P/'screen/queue_runner.py').relative_to(ROOT))
        assert v['unit']=='screen-'+row['name'] and v['card']==0
        assert int(v['native_argv'][v['native_argv'].index('--wait-seconds')+1])>=300
        assert v['native_argv'][v['native_argv'].index('--lookups')+1]=='resident'
        rows[str(rowpath.relative_to(ROOT))]=sha(rowpath)
        report=read(f'evidence/p58an-rehearse-{kind}.json');assert report['passed']
        assert read(f'evidence/p58an-plan-{kind}.log')['plan']=='passed'
        warnings[kind]={k:r for k,r in report['jobs'][0].items() if isinstance(r,dict) and r.get('status')=='WARN'}
        for leaf in (f'p58an-rehearse-{kind}.json',f'p58an-plan-{kind}.log'):
            proofs['evidence/'+leaf]=sha(P/'evidence'/leaf)
    for name in ('allocation-plan.json','storage-budget.json'):
        assert read(name)['passed'];proofs[name]=sha(P/name)
    proofs['wait-budget.json']=sha(P/'wait-budget.json')
    proofs['evidence/p58amd-incident-audit.json']=sha(P/'evidence/p58amd-incident-audit.json')
    files={}
    for f in P.rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(P)
        if str(rel).startswith('screen/evidence/') or f.name=='window.lock' or f.name.startswith('fault-'):continue
        if f.parent==P and f.suffix in ('.py','.md') or rel.parts[0] in ('native','inputs','screen','proposals') or str(rel).startswith('build/native/'):
            if '__pycache__' not in rel.parts:
                if f.suffix=='.py':ast.parse(f.read_text())
                files[str(f.relative_to(ROOT))]=sha(f)
    # Preserve every owned source byte, including archived historical metadata.
    for row in closure['files']:files[str((P/row['destination']).relative_to(ROOT))]=row['after']
    for name in ('lineage/source-closure.json','lineage/harness58aj.json','lineage/resident-port.json',
                 'lineage/historical-metadata.json','lineage/admission-closure.json'):
        files[str((P/name).relative_to(ROOT))]=sha(P/name)
    for row in read('lineage/admission-closure.json')['files']:
        assert sha(P/row['owned'])==row['sha256']
        files[str((P/row['owned']).relative_to(ROOT))]=row['sha256']
    footprint=sum(f.stat().st_size for f in P.rglob('*') if f.is_file() and f.relative_to(P).parts[0]!='evidence' and not str(f.relative_to(P)).startswith('screen/evidence/'))
    assert footprint<300000000
    package=dict(schema='packet58an.queue-packaging.v1',passed=True,ready_for_device=True,device_executed=False,
        parent='packet58aj resident record line',parent_tok_s=31.966820,record='cmveqsmsl00ebrf014yvrsosx',
        release_condition=RELEASE,release_amendment_sha256=sha(P/'RELEASE-AMENDMENT.md'),files=files|rows,
        proofs=proofs,unit_prefix='screen-',lane='A',card=0,windows=['K1a','K1b','WSCREEN'],
        whole_host_hold='coordinator retains PAUSE-B',preregistration_unchanged=True,compiles_performed=True,
        queued=False,model_or_device_opened=False,shared_rehearsal_warnings=warnings,
        build_and_source_closure_bytes=footprint,root_free_bytes=shutil.disk_usage('/').free,
        smoke_total_requests=24,smoke_legacy_report_request_count=12,v5_total_requests=60,
        v5_condition='fresh same-parent exact overlap smoke, overhead and actual storage gate')
    save(P/'screen-packaging.json',package)
    receipt=dict(schema='packet58an.build.v1',passed=True,cpu_prepared=True,device_executed=False,
        ready_for_device=True,parent=package['parent'],parent_tok_s=package['parent_tok_s'],record=package['record'],
        arithmetic='iq3-p49-split32-v1',variant='bcs-demand-retained32x2',resident_lookups=True,
        sources={str((ROOT/n).relative_to(P)):h for n,h in files.items()},artifacts=artifacts,proofs=proofs,
        proposals=proposals,release_condition=RELEASE,queue_packaging_sha256=sha(P/'screen-packaging.json'))
    save(P/'build-receipt.json',receipt)
    save(P/'seal.json',dict(schema='packet58am.seal.v1',passed=True,device_executed=False,
        build_receipt_sha256=sha(P/'build-receipt.json'),queue_packaging_sha256=sha(P/'screen-packaging.json'),
        proofs=proofs,proposals=proposals,artifacts=artifacts,frozen_decision_sha256=old['frozen_decision_sha256']))
    # Recheck both inert lane rows against the final dependency graph before READY.
    import sys
    sys.path.insert(0,str(P.parents[1]/'ops/lane-queue'));import pin_guard
    for kind in ('smoke','v5'):
        path=ROOT/f'experiments/own-xpu-runtime/ops/lane-queue/proposed-p58am-{kind}-A.txt'
        row=json.loads(next(x for x in path.read_text().splitlines() if x.startswith('{')))
        assert pin_guard.check_job(row)['passed']
    ready=dict(schema='packet58an.ready.v1',ready_for_device=True,cpu_prepared=True,device_executed=False,
        conditional_smoke_ready=True,v5_ready=False,v5_conditional_on_same_parent_smoke=True,
        parent=package['parent'],parent_tok_s=package['parent_tok_s'],record=package['record'],
        fallback_used=True,fallback_scope='unchanged parent expert commands for incompatible IQ3_XXS layer 2',
        demand_eligible_layers=47,unsupported_layout_layers=[2],device_repair_confirmation_pending=True,
        lookups='resident',oracle='iq3-p49-split32-v1',release_condition=RELEASE,
        release_amendment_sha256=sha(P/'RELEASE-AMENDMENT.md'),seal_sha256=sha(P/'seal.json'),
        build_receipt_sha256=sha(P/'build-receipt.json'),packaging_sha256=sha(P/'screen-packaging.json'),
        artifacts=artifacts,proofs=proofs,proposals=proposals,lanequeue_proposals=rows,
        frozen_decision_sha256=old['frozen_decision_sha256'],
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        shared_rehearsal_warnings=warnings,build_and_source_closure_bytes=footprint,
        queued=False,services_started=False,final_marker_written_last=True,
        pending=['coordinator live admission and fault review','device oracle and overlap smoke','v5 actual storage refresh and measured speed'])
    save(P/'READY-FOR-DEVICE.json',ready)  # Last artifact written.
    print('READY true: CPU-qualified resident-parent screen; no device execution or enqueue')
if __name__=='__main__':main()
