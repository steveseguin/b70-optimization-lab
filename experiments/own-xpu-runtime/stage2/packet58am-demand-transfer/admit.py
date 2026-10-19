"""Read-only proposal admission. This module cannot launch or enqueue work."""
import argparse,json,shutil
from pathlib import Path
from prepare import P,sha

def require(ok,message):
    if not ok:raise ValueError(message)
def identity(proposal):
    argv=proposal['native_argv'];name=proposal['job_name']
    require(proposal['lane']=='A' and proposal['card']==0,'one-card lane A')
    require(argv[argv.index('--demand-identity')+1]==name,'proposal-derived gate identity')
    return name
def plan(proposal):
    name=identity(proposal);argv=proposal['native_argv'];kind='smoke' if proposal['tokens_per_prompt']==64 else 'v5'
    require(proposal['model_loads']==1 and proposal['prompts']==12,'one full-suite load')
    require(proposal['views']==(['S0','S1'] if kind=='smoke' else ['A0','B0','A1','B1','A2']),'preregistered view order')
    require(proposal['in_run_data_deadline_seconds'] is None,'no data-proof wall limit')
    require(set(proposal['in_run_data_checks'])=={'presence','format','exactness'},'in-run data checks')
    require('--demand-diagnostics' in argv if kind=='smoke' else '--demand-diagnostics' not in argv,'profiling scope')
    wait=json.loads((P/'wait-budget.json').read_text())
    require(int(argv[argv.index('--wait-seconds')+1])>=wait['per_operation_seconds'],'cold operation wait')
    require(not Path(proposal['output']).exists(),'fresh output required')
    require(proposal['admission']['root_floor_bytes']==25000000000,'25 GB device storage floor')
    require(proposal['admission']['host_required_available_bytes']>=99119554560,'full host reserve')
    return dict(passed=True,device_executed=False,job_name=name,kind=kind,argv=argv)
def device_admission(proposal,ready,census,smoke=None):
    plan(proposal)
    require(ready.get('ready_for_device') is True,'coordinator census release withheld')
    require(ready.get('seal_sha256')==sha(P/'seal.json'),'readiness seal binding')
    seal=json.loads((P/'seal.json').read_text())
    kind='smoke' if proposal['tokens_per_prompt']==64 else 'v5'
    path=P/f'proposals/{kind}.json'
    require(json.loads(path.read_text())==proposal and seal['proposals'][f'proposals/{kind}.json']==sha(path),'sealed exact proposal')
    for name,digest in seal['artifacts'].items():require(sha(P/name)==digest,'sealed native artifact')
    require(census.get('decision')=='brief-transfer-mechanism' and census.get('upper_bound_ms_per_token',-1)>=1,'complete census bound >=1.000 ms/token')
    require(census.get('measurement_stability_gate',{}).get('passed') is True,'census measurement stability')
    require(census.get('native_closure_verified') is True and census.get('exact_oracle_verified') is True,'coordinator must verify full native and oracle closure')
    require(bool(census.get('evidence_hashes')),'hash-bound complete census evidence')
    for name,digest in census['evidence_hashes'].items():require(sha(Path(name))==digest,'census evidence changed')
    if proposal['tokens_per_prompt']==128:
        require(smoke and smoke.get('exact') and smoke.get('observed_overlap_ns',0)>0 and smoke.get('same_parent') and smoke.get('overhead_qualified'),'same-parent exact overlap smoke required')
        require(smoke.get('storage_volume_measured') is True,'replace storage estimate with actual smoke volume')
        require(proposal['storage'].get('actual_smoke_volume_bytes')==smoke.get('actual_volume_bytes') and type(smoke.get('actual_volume_bytes')) is int,'v5 reservation must actually be refreshed from smoke')
        require(smoke.get('job_name')==json.loads((P/'proposals/smoke.json').read_text())['job_name'],'same smoke proposal identity')
    available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    require(available>=proposal['admission']['host_required_available_bytes'],'full host memory bound plus reserve')
    require(shutil.disk_usage('/').free>=25000000000+proposal['storage']['planned_outstanding_write_bytes'],'disk floor plus outstanding writes')
    return True
def main():
    parser=argparse.ArgumentParser();parser.add_argument('proposal',type=Path);args=parser.parse_args()
    print(json.dumps(plan(json.loads(args.proposal.read_text())),indent=2))
if __name__=='__main__':main()
