#!/usr/bin/env python3
"""Read-only placement-plan and two32 terminal review; canonical comparator stays unchanged."""
import argparse
import gzip
import json
from pathlib import Path
import tempfile
from finalize_persistent_rolling_proof import (need,read,lines,identity,compare,audit_reset,audit_controller,audit_native,
    audit_provider,bind_survival,audit_timing,survival_bytes,HERE,validate_identity)


def plan_review(plan_path,reference_path):
    plan=read(plan_path);prior=read(reference_path)
    need(plan['boundaries']==[0,8,21,34,48] and plan['check_policy']=='qualification'
         and plan['dump_each'] is True and plan['suite_prompt_count']==2,'explicit balanced two32 checked plan')
    recursive=read(HERE/'recursive-provider-reference-v2.json');suite=read(Path(plan['suite']))
    synthetic_terminal=dict(schema='ownrt.persistent-rolling-result.v1',mode='persistent-rolling',check_policy='qualification',
        passed=True,error=None,live_pids=[],returncodes={str(s['id']):0 for s in plan['stages']},actual_provider=True,scripted_oracle_assisted=False)
    # Pure planned identity check; this synthetic object is not a run completion claim.
    validate_identity(plan,suite,synthetic_terminal,recursive)
    for key in ('model_identity_sha256','draft_model_sha256','draft_experts','context','vocab','activation_dtype','eos_token_ids'):
        need(plan[key]==prior[key],'model/arithmetic identity changed')
    def pins(p):return {k:v for k,v in p['pins'].items() if k not in (p['config'],p['suite'])}
    need(pins(plan)==pins(prior),'execution/source/build pins changed beyond reviewed placement configuration')
    for name,want in pins(plan).items():
        if name.endswith('.py') or name.endswith('/build-receipt.json') or name.endswith('/own-engine'):
            need(identity(Path(name))['sha256']==want,'current pinned source/build changed')
    allowed_value_flags=['--shared','--output','--max-new','--seconds','--pipeline-boundaries','--pipeline-ring-request-sha256',
        '--pipeline-ring-check-policy','--pipeline-ring-final-shared','--pipeline-ring-trace-limit']
    policy_flags=['--pipeline-ring-verify-restore','--pipeline-ring-recursive-verify-restore','--pipeline-ring-verify-provider-survival']
    def fixed_argv(stage):
        args=list(stage['argv'])
        for flag in allowed_value_flags:
            if flag in args:
                need(args.count(flag)==1,'duplicate variable option');i=args.index(flag);need(i+1<len(args),'variable option value absent');del args[i:i+2]
        for flag in policy_flags:
            if flag in args:args.remove(flag)
        return args
    owners=[]
    for index,(stage,old) in enumerate(zip(plan['stages'],prior['stages'])):
        need(stage['id']==index and (stage['begin'],stage['end'])==tuple(plan['boundaries'][index:index+2])
             and stage['bdf']==old['bdf'] and stage['first'] is (index==0) and stage['final'] is (index==3),'absolute stage coverage/physical owner changed')
        args=stage['argv'];option=lambda flag:args[args.index(flag)+1]
        need(option('--pipeline-boundaries')==','.join(map(str,plan['boundaries'])) and option('--pipeline-stage')==str(index)
             and option('--pipeline-ring-check-policy')=='qualification' and option('--max-new')=='32'
             and option('--pipeline-ring-request-sha256')==plan['request_sha256']
             and option('--pipeline-ring-trace-limit')==str(plan['ring_trace_limit'])
             and '--pipeline-ring-verify-restore' in args,'native partition/checked policy flags differ')
        for flag in policy_flags[1:]:need((flag in args) is stage['first'],'provider check policy ownership differs')
        need(fixed_argv(stage)==fixed_argv(old),'native arithmetic or model args changed')
        a=dict(stage['environment']);b=dict(old['environment'])
        for key,leaf in [('SYCL_CACHE_DIR','sycl'),('NEO_CACHE_DIR','neo'),('XDG_CACHE_HOME','xdg')]:
            need(a.pop(key)==str(Path(plan['output'])/f'stage{index}/cache/{leaf}'),'owner cache path differs')
            need(b.pop(key)==str(Path(prior['output'])/f'stage{index}/cache/{leaf}'),'reference cache path differs')
        need(a==b,'arithmetic/device environment changed');owners.append({k:stage[k] for k in ('id','begin','end','bdf','packed_weight_bytes')})
    # Existing generic fixture exercises these exact48-layer repartitions without touching model/GPU.
    import test_compare_pipeline_state as fixture
    with tempfile.TemporaryDirectory(dir='/dev/shm') as temp:
        root=Path(temp);gold=fixture.make_set(root/'old',[0,13,25,37,48],spares=True)
        candidate=fixture.make_set(root/'new',plan['boundaries'],spares=True)
        compared=compare.compare(compare.load_set(gold),compare.load_set(candidate));need(compared['passed'],'canonical absolute-layer repartition fixture failed')
    return dict(passed=True,plan=identity(plan_path),reference_execution_plan=identity(reference_path),boundaries=plan['boundaries'],owners=owners,
        exact_execution_pins=True,absolute_layer_fixture=dict(passed=True,layers=48,compared_buffers=len(compared['compared_source_keys'])),
        comparator=identity(Path(compare.__file__)),finalizer=identity(HERE/'finalize_persistent_rolling_proof.py'),
        adapter_required=False,qualification_status='plan/source suitability only until terminal proof',speed_claim=False)


def terminal_review(proof_path,plan):
    summary=read(proof_path/'summary.json');run=Path(summary['source_run']);terminal=read(run/'persistent-rolling-result.json')
    need(summary['schema']=='ownrt.persistent-rolling-proof.v1' and summary['passed'] is True and summary['requests']==2
         and summary['all_requests_full_state_parity'] is True and summary['check_policy']=='qualification','accepted balanced two32 fullstate proof required')
    need(identity(run/'plan.json')['sha256']==identity(proof_path/'plan.json')['sha256']==summary['original_plan']['sha256'],
         'terminal original/retained plan identity differs')
    need(read(run/'plan.json')==plan and terminal['passed'] is True and terminal['live_pids']==[]
         and terminal['returncodes']=={str(i):0 for i in range(4)},'clean matching placement run required')
    recursive=read(HERE/'recursive-provider-reference-v2.json');suite=read(Path(plan['suite']))
    validate_identity(plan,suite,terminal,recursive)
    previous_request=plan['request_sha256'];previous_sequences=[0]*4;previous_position=0;inventories=None;rows=[]
    for index,(prompt,stated) in enumerate(zip(suite['prompts'],summary['request_summaries'])):
        folder=run/stated['directory'];local=proof_path/stated['directory'];result=read(folder/'result.json')
        reset=audit_reset(plan,prompt,result,lines(folder/'reset-commands.jsonl'),previous_request=previous_request,
            previous_sequences=previous_sequences,previous_target_position=previous_position,prior_inventories=inventories,
            read_raw=lambda path:survival_bytes(path)[0]);need(reset==stated['reset_audit'],'reset chain proof differs')
        need(result['output_ids']==recursive['target_output_ids'],'32 canonical outputs differ')
        stages=[dict(s,native_output=result['reset_receipts'][i]['native_output']) for i,s in enumerate(plan['stages'])]
        native0=Path(stages[0]['native_output']);meta=read(native0/'pipeline-stage.json');batches=lines(folder/'provider-batches.jsonl')
        replay=audit_controller(lines(folder/'commands.jsonl'),lines(folder/'final-records.jsonl'),batches,prompt['prompt_tokens'],result['output_ids'],
            result['request_sha256'],4,meta['stream_bytes'],plan['vocab'],plan['context'],epoch=result['epoch'],
            initial_sequences=result['initial_sequences'],check_policy='qualification',max_new=32)
        need([s['last_sequence'] for s in replay['states']]==result['final_sequences'],'wire sequence boundary differs')
        inputs=prompt['prompt_tokens']+result['output_ids'][:-1];survival=None
        for stage in stages:
            native=Path(stage['native_output']);marker=f'state-{2000000000+index}';att=read(native/(marker+'.ring-state.json'))
            nr=lines(native/'ring.jsonl');checked=dict(stage=stage['id'],**audit_native(nr,replay['sent'][stage['id']],replay['created'],inputs,att,stage['final']))
            need(checked==stated['native_command_audits'][stage['id']],'native row audit differs')
            if stage['first']:
                checked=audit_provider(batches,lines(native/'ring-draft-batches.jsonl'),recursive,replay,len(prompt['prompt_tokens']),att,
                    result['request_sha256'],epoch=result['epoch'],policy='qualification')
                need(checked==stated['provider_audit'],'117 true-pair/32recursive reference differs')
                survival=bind_survival(lines(native/'ring-provider-survival.jsonl'),replay,batches,recursive,len(prompt['prompt_tokens']),result['request_sha256'])
                need(survival==stated['survival_audit'],'provider byte/host/suffix survival differs')
        target=json.loads(gzip.decompress((local/'target-comparison.json.gz').read_bytes()))
        draft=json.loads(gzip.decompress((local/'draft-comparison.json.gz').read_bytes()))
        need(target['passed'] is True and draft['passed'] is True and len(target['compared_source_keys'])==2065
             and len(draft['compared_source_keys'])==73,'complete canonical target/draft parity result required')
        rerun=compare.compare(target['reference'],target['candidate']);need(rerun['passed'],'stored canonical identities differ')
        manifest=read(local/'candidate-state-set.json');need([s['begin'] for s in manifest['stages']]+[manifest['stages'][-1]['end']]==plan['boundaries'],
             'comparison uses another placement')
        # Bind current retained metadata/seals while avoiding another large raw-array read.
        for source in target['candidate']['sources']+draft['candidate']['sources']:
            path=Path(source['path'])
            if path.name in ('state-seal.txt','state-index.tsv','state.json'):
                need(identity(path)['sha256']==source['sha256'],'sealed metadata changed after comparison')
        need(audit_timing(lines(folder/'tokens.jsonl'),result['output_ids'],result)==stated['timing'],'observed timing differs')
        rows.append(dict(id=prompt['id'],epoch=result['epoch'],outputs=32,target_buffers=2065,draft_allocations=73,
            canonical_pairs=stated['provider_audit']['pairs'],recursive_pairs=stated['provider_audit']['depth2_pairs'],survival_checks=survival['checks'],
            actual_proposal_rows=replay['actual_proposal_rows'],native_counts=[a['counters'] for a in stated['native_command_audits']]))
        previous_request=result['request_sha256'];previous_sequences=reset['post_sequences'];previous_position=len(inputs);inventories=reset['inventories']
    need(len(rows)==2,'exact two-request proof required')
    observations=lines(run/'observations.jsonl');need(all(o['known_fault_baseline_matches'] is True for o in observations),'new fault observed')
    return dict(passed=True,source_proof=identity(proof_path/'summary.json'),rows=rows,observations=len(observations),all_fault_baselines_match=True,
        full_raw_state_reread=False,speed_claim=False,scope='Two cold32 repeated requests; absolute-layer canonical target and complete draft equality. No fullsuite speed or independent CPU reference claim.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--reference-plan',type=Path,required=True)
    p.add_argument('--proof',type=Path);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    review=plan_review(args.plan,args.reference_plan)
    if args.proof:review['terminal_review']=terminal_review(args.proof,read(args.plan))
    review.update(schema='ownrt.persistent-balanced-placement-review.v1',implementation=identity(Path(__file__)),gpu_actions=False)
    with args.out.open('x') as f:json.dump(review,f,indent=2);f.write('\n')
    print(json.dumps(dict(passed=True,terminal_checked=args.proof is not None,out=str(args.out))))


if __name__=='__main__':main()
