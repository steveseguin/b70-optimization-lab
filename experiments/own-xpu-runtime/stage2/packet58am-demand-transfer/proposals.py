"""Write inert, fresh coordinator proposals; no enqueue or device invocation."""
import json,shutil,math
from pathlib import Path
from prepare import P,ROOT,AH,AG,sha,save

def main():
    out=P/'proposals';out.mkdir(exist_ok=True);inputs=P/'inputs';inputs.mkdir(exist_ok=True)
    audit=json.loads((P.parent/'packet58al-demand-transfer-prep/evidence/parent-audit.json').read_text())
    pins=[]
    def copy(src,dst):
        src=Path(src);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        pins.append(dict(source=str(src.relative_to(ROOT)),destination=str(dst.relative_to(P)),sha256=sha(src),bytes=src.stat().st_size));return dst
    table=AG/'evidence/card0-ports-a/p60fusion/WSCREEN/run/suite-inputs.tsv'
    suite={64:[],128:[]}
    for line in table.read_text().splitlines():
        prompt,tokens,oracle=line.split();folder=inputs/prompt
        copy(tokens,folder/'tokens.txt')
        for name in ('plan.tsv','identity.tsv'):copy(Path(tokens).parent/name,folder/name)
        ref=list(map(int,Path(oracle).read_text().split()));assert len(ref)==128
        # The oracle remains the packet49 identity. Parent result is only an
        # additional exact consistency check, never a newly pinned oracle.
        real=json.loads((AH/f'evidence/card0-58ah-b/WS128/run/run/{prompt}/result.json').read_text())
        assert real['tokens']==ref
        pins.append(dict(source=str(Path(oracle).relative_to(ROOT)),sha256=sha(oracle),kind='unchanged packet49 tokens retained in parent bracket'))
        for cap in (64,128):
            target=folder/f'oracle-{cap}.txt';target.write_text('\n'.join(map(str,ref[:cap]))+'\n')
            suite[cap].append(f'{prompt} {folder/"tokens.txt"} {target}')
    selection=copy(AH/'selections/down-tile16.json',inputs/'selection.json')
    dispatch=copy(AH/'dispatch-speed6.json',inputs/'dispatch.json')
    k1=AH/'build/device/p58-cache-fixtures'
    expected=json.loads((P/'lineage/58ag-build-receipt.json').read_text())['artifacts']['build/device/p58-cache-fixtures']
    assert sha(k1)==expected
    copy(k1,P/'build/device/p58-cache-fixtures')
    # Cold load is an enclosing stage, not a measured individual operation.
    phases=[]
    for packet in (AH,P.parent/'packet58aj-onecard-resident',P.parent/'packet58ai-miss-census'):
        for path in (packet/'evidence').glob('card*/**/cold-start.json'):
            data=json.loads(path.read_text())
            phases.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path),data=data))
    cold_ms=max(r['prefill_total_ms'] for r in audit['request_cold_rows'])
    for row in phases:
        for k,v in row['data'].items():
            if type(v) in (int,float) and k.endswith('_ms'):cold_ms=max(cold_ms,v)
            if type(v) in (int,float) and k.endswith('_seconds'):cold_ms=max(cold_ms,v*1000)
    wait=max(300,math.ceil(4*cold_ms/1000));assert wait<=3600
    save(P/'wait-budget.json',dict(per_operation_seconds=wait,multiplier=4,minimum_seconds=300,
         largest_enclosing_cold_ms=cold_ms,phases=phases,parent_replay='evidence/parent-replay.json',
         scope='conservative enclosing cold stages, not claimed individual operations',in_run_data_deadline_seconds=None))
    for cap in (64,128):(inputs/f'suite-{cap}.tsv').write_text('\n'.join(suite[cap])+'\n')
    for kind,labels,cap in [('smoke',['S0','S1'],64),('v5',['A0','B0','A1','B1','A2'],128)]:
        views=inputs/f'{kind}-views.tsv';views.write_text(''.join(f'{label} {selection} {sha(selection)} overlap max p60fusion\n' for label in labels))
        command=audit['native_argv'][2:].copy();command[0]=str(P/'build/device/own-rt-iq3')
        values={'--max-new':str(cap),'--suite-inputs':str(inputs/f'suite-{cap}.tsv'),
            '--input':str(inputs/'incident-retrospective/tokens.txt'),'--plan':str(inputs/'incident-retrospective/plan.tsv'),
            '--identity':str(inputs/'incident-retrospective/identity.tsv'),'--selection':str(selection),
            '--dispatch':str(dispatch),'--output':str(P/f'evidence/card0-demand-a/{kind}/run')}
        for key,value in values.items():command[command.index(key)+1]=value
        command+=['--wait-seconds',str(wait),'--demand','bcs-demand-retained32x2','--bracket-inputs',str(views)]
        job=f'packet58am-demand-a-{kind}-A';assert not Path(values['--output']).exists()
        command+=['--demand-identity',job]
        if kind=='smoke':command+=['--demand-diagnostics']
        precommands=[]
        if kind=='smoke':
            for stage in ('K1a','K1b'):
                old=json.loads((AH/f'evidence/card0-58ah-b/{stage}/window.json').read_text())['command'];old[0]=str(P/'build/device/p58-cache-fixtures');old[old.index('--output')+1]=str(P/f'evidence/card0-demand-a/smoke/{stage}/run');precommands.append(dict(stage=stage,argv=old,binary_sha256=expected,gap_after_seconds=90))
        save(out/f'{kind}.json',dict(schema='packet58am.proposal.v1',job_name=job,lane='A',card=0,
            output=str(P/f'evidence/card0-demand-a/{kind}'),native_argv=command,
            environment={'OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':'/opt/intel/oneapi/compiler/2026.0/lib'},
            ready_for_device=False,release_condition='packet58ai census bound >= 1.000 ms/token',
            coordinator_only=True,queue_write_authorized=False,model_loads=1,views=labels,tokens_per_prompt=cap,prompts=12,
            pre_stages=['K1a','K1b'] if kind=='smoke' else [],gap_seconds=90,
            pre_stage_commands=precommands,
            scope='diagnostic screening, no record',whole_host_quiet_required=True,
            detailed_events=(kind=='smoke'),profiling=(kind=='smoke'),
            v5_requires_same_parent_smoke=True,warmup_excluded=['A0'] if kind=='v5' else [],
            performance_gate={'each_B_over_each_A1_A2':1.005,'warm_control_max_over_min':1.03,'strict_gain':.02},
            in_run_data_checks=['presence','format','exactness'],in_run_data_deadline_seconds=None,
            admission={'root_floor_bytes':25000000000,'host_required_available_bytes':99119554560,
                       'host_reserve_bytes':8589934592,'shadow_stop_bytes':4294967296,
                       'device_owned_bound_bytes':29963128848,'driver_allowance_bytes':536870912,'device_reserve_bytes':1500000000}))
    save(P/'lineage/input-pins.json',pins)
    print('Inert smoke and one-load v5 proposals written; wait',wait,'seconds')
if __name__=='__main__':main()
