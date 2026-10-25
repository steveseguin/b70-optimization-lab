#!/usr/bin/env python3
"""Independent terminal metadata/witness rerun and separately derived first99 metrics."""
import argparse
import ast
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
from persistent_rolling_suite_audit import (read,lines,need,load_baseline,audit_provider,work_breakdown,
    validate_prerequisite_closure,load_planner_transition,validate_prerequisite_record)
from finalize_persistent_rolling_proof import (identity,audit_reset,audit_controller,audit_native,audit_timing,survival_bytes)
from finalize_persistent_rolling_suite import attest
from persistent_ring_policy import EMPTY_SHA

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent


def stats(values):
    need(values and all(math.isfinite(v) for v in values),'finite metric population')
    ordered=sorted(values);at=(len(values)-1)*.1;lo=int(at);hi=min(lo+1,len(values)-1)
    return dict(count=len(values),median=statistics.median(values),mean=statistics.fmean(values),
        p10=ordered[lo]*(1-(at-lo))+ordered[hi]*(at-lo),minimum=ordered[0],maximum=ordered[-1])


def fixed_classes(path):
    tree=ast.parse(Path(path).read_text());matches=[node.value for node in tree.body if isinstance(node,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='PROMOTION_PROMPT_CLASSES' for t in node.targets)]
    need(len(matches)==1,'one fixed suite class map required');mapping=ast.literal_eval(matches[0])
    need(len(mapping)==12 and len(set(mapping.values()))==6,'fixed twelve prompts/six classes required')
    return mapping


def row_metrics(prompt,row,tokens,prompt_class):
    outputs=row['output_ids'];need(len(tokens)==len(outputs)>=100,'all natural responses must cover100 events')
    need([(r['index'],r['token']) for r in tokens]==list(enumerate(outputs)),'metric timestamps bind exact output IDs')
    t=[r['committed_monotonic_s'] for r in tokens];start=row['request_started_monotonic_s'];end=row['request_finished_monotonic_s']
    need(all(math.isfinite(x) for x in t+[start,end]) and start<=t[0]<t[99]<=t[-1]<=end
         and all(a<=b for a,b in zip(t,t[1:])),'ordered measured metric window')
    numerator=99;span=t[99]-t[0];fullspan=t[-1]-t[0]
    need(row['timing']['first_token_seconds']==t[0]-start and row['timing']['decode_intervals']==len(outputs)-1
         and row['timing']['decode_tokens_per_second']==(len(outputs)-1)/fullspan,'stored full response timing differs')
    return dict(prompt_id=prompt['id'],prompt_class=prompt_class,prompt_tokens=len(prompt['prompt_tokens']),
        requested_cap=prompt['max_new'],output_tokens=len(outputs),cached_tokens=row['cached_tokens'],
        prompt_sha256=row['prompt_token_sha256'],output_sha256=row['output_token_sha256'],token_hash_encoding='uint32-little-endian',
        first99=dict(event_count=100,interval_count=99,numerator=numerator,first_event_index=0,last_event_index=99,
            first_monotonic_s=t[0],last_monotonic_s=t[99],seconds=span,tokens_per_second=numerator/span),
        ttft_seconds=t[0]-start,request_start_monotonic_s=start,request_end_monotonic_s=end,
        reset_seconds=row['reset_seconds'],full_natural_completion_seconds=fullspan,
        full_natural_completion_intervals=len(outputs)-1,full_natural_completion_tokens_per_second=(len(outputs)-1)/fullspan,
        cap512_tokens_per_second=(len(outputs)-1)/fullspan if len(outputs)==512 else None,
        wall_seconds=end-start,wall_tokens_per_second=len(outputs)/(end-start),
        prompt_tokens_per_ttft_second=len(prompt['prompt_tokens'])/(t[0]-start),pure_prefill_seconds=None,
        native_prefill_tokens_per_second=None)


def aggregate(rows):
    grouped={}
    for row in rows:grouped.setdefault(row['prompt_class'],[]).append(row['first99']['tokens_per_second'])
    medians={k:statistics.median(v) for k,v in sorted(grouped.items())}
    return dict(primary_metric_name='median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft',
        primary_metric_aggregation='median-of-prompt-class-medians',primary_metric_accounting='inter-token-intervals',
        primary=stats(list(medians.values())),class_medians=medians,class_prompt_counts={k:len(v) for k,v in grouped.items()},
        all_prompt_first99=stats([r['first99']['tokens_per_second'] for r in rows]),
        full_natural_completion=stats([r['full_natural_completion_tokens_per_second'] for r in rows]),
        cap512_only=stats([r['cap512_tokens_per_second'] for r in rows if r['cap512_tokens_per_second'] is not None]),
        ttft_seconds=stats([r['ttft_seconds'] for r in rows]),wall_tokens_per_second=stats([r['wall_tokens_per_second'] for r in rows]),
        output_lengths=[r['output_tokens'] for r in rows])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--proof',type=Path,required=True)
    p.add_argument('--review-out',type=Path,required=True);p.add_argument('--metrics-out',type=Path,required=True);args=p.parse_args()
    proof=args.proof.resolve();summary=read(proof/'summary.json');run=Path(summary['source_run']);plan=read(run/'plan.json')
    terminal=read(run/'persistent-rolling-result.json');suite=read(Path(plan['suite']));baseline=load_baseline(HERE/'persistent-rolling-baseline-audit.json')
    need(summary['schema']=='ownrt.persistent-rolling-suite-proof.v1' and summary['passed'] is True
         and summary['requests']==12 and summary['output_tokens']==5965 and summary['final_target_state_exact'] is True
         and summary['final_target_buffer_count']==2065 and summary['final_state_position']==571
         and summary['all_requests_full_state_parity'] is False and summary['final_draft_state_parity'] is False
         and summary['byte_verification_enabled'] is False and summary['provider_survival_evidence']=='not-collected'
         and summary['speed_claim'] is summary['certified'] is False,'terminal proof scope differs')
    need(terminal['passed'] is True and terminal['live_pids']==[] and terminal['returncodes']=={str(i):0 for i in range(4)},'clean terminal required')
    need(terminal['plan_sha256']==identity(run/'plan.json')['sha256']==identity(proof/'plan.json')['sha256'],'plan source identity differs')
    source_receipt=read(HERE/'persistent-rolling-suite-audit-cpu.json')
    for name,want in source_receipt['sources'].items():need(identity(ROOT/'experiments/own-xpu-runtime'/name)['sha256']==want,'frozen suite auditor source changed')
    need(summary['finalizer']==identity(HERE/'finalize_persistent_rolling_suite.py'),'proof finalizer identity differs')
    for item in summary['prerequisites']:
        sp=Path(item['summary']['path']);pp=Path(item['plan']['path']);prior_summary=read(sp)
        for path,expected in ((sp,item['summary']),(pp,item['plan'])):need(identity(path)==expected,'prerequisite source changed')
        checked_path=Path(summary['prerequisites'][0]['summary']['path'])
        prior=validate_prerequisite_record(prior_summary,pp,prior_summary['check_policy'],checked_path)
        bridge=item['execution_closure']['planner_transition'];transition=load_planner_transition(Path(bridge['path']),bridge['sha256']) if bridge else None
        need(validate_prerequisite_closure(plan,prior,transition)==item['execution_closure'],'prerequisite exact execution closure differs')
    class_path=ROOT/'scripts/qualify_realistic_window_metrics.py';classmap=fixed_classes(class_path)
    rows=[];checks=[];sources=[];previous_request=plan['request_sha256'];previous_sequences=[0]*4;previous_position=0;inventories=None
    for index,(prompt,want,stated) in enumerate(zip(suite['prompts'],baseline['rows'],summary['request_summaries'])):
        folder=run/f"request-{index:02d}-{prompt['id']}";local=proof/folder.name;result=read(folder/'result.json')
        need(result['output_ids']==want['expected_output_ids'] and type(result['cached_tokens'])is int and result['cached_tokens']==0,'exact cold output IDs differ')
        reset=audit_reset(plan,prompt,result,lines(folder/'reset-commands.jsonl'),previous_request=previous_request,
            previous_sequences=previous_sequences,previous_target_position=previous_position,prior_inventories=inventories,
            read_raw=lambda path:survival_bytes(path)[0]);need(reset==stated['reset_audit'],'reset chain proof differs')
        stages=[dict(s,native_output=result['reset_receipts'][i]['native_output']) for i,s in enumerate(plan['stages'])]
        commands=lines(folder/'commands.jsonl');records=lines(folder/'final-records.jsonl');batches=lines(folder/'provider-batches.jsonl')
        metadata=read(Path(stages[0]['native_output'])/'pipeline-stage.json');inputs=prompt['prompt_tokens']+result['output_ids'][:-1]
        replay=audit_controller(commands,records,batches,prompt['prompt_tokens'],result['output_ids'],result['request_sha256'],4,metadata['stream_bytes'],
            plan['vocab'],plan['context'],epoch=result['epoch'],initial_sequences=result['initial_sequences'],check_policy='measured',max_new=512)
        need([s['last_sequence'] for s in replay['states']]==result['final_sequences'],'actual global wire frontier differs')
        need(replay['actual_proposal_rows']==stated['actual_proposal_rows'],'actual proposal-row total differs')
        native_counts=[];native_provider=None
        for stage in stages:
            native=Path(stage['native_output']);ap=native/('state-2147483647.ring-state.json' if index==11 else 'ring-quiescence.json');att=read(ap)
            attest(att,stage,result['request_sha256'],result['epoch'],len(inputs),native/'ring-checkpoint-layout.json')
            nr=lines(native/'ring.jsonl');checked=dict(stage=stage['id'],**audit_native(nr,replay['sent'][stage['id']],replay['created'],inputs,att,stage['final']))
            need(checked==stated['native_audits'][stage['id']],'native command proof differs');native_counts.append(checked['counters'])
            if stage['first']:
                native_provider=lines(native/'ring-draft-batches.jsonl');checked=audit_provider(batches,native_provider,replay,records,len(prompt['prompt_tokens']),att,result['request_sha256'],result['epoch'])
                need(checked==stated['provider_audit'],'actual provider/native provenance differs')
                raw,source=survival_bytes(native/'ring-provider-survival.jsonl');need(raw==b'' and source['sha256']==EMPTY_SHA,'measured survival evidence is not empty')
        need(work_breakdown(commands,replay,native_provider,len(prompt['prompt_tokens']))==stated['work'],'recorded busy/rollback work statistics differ')
        tokens=lines(folder/'tokens.jsonl');need(audit_timing(tokens,result['output_ids'],result)==stated['timing'],'timestamp window proof differs')
        rows.append(row_metrics(prompt,result,tokens,classmap[prompt['id']]))
        checks.append(dict(id=prompt['id'],epoch=result['epoch'],reset_owners=4,output_tokens=len(result['output_ids']),
            canonical_provider_pairs=len(replay['providers']),recursive_pairs=stated['provider_audit']['recursive_pairs'],
            actual_proposal_rows=replay['actual_proposal_rows'],per_stage_counts=native_counts))
        for name in ('tokens.jsonl','result.json','commands.jsonl','reset-commands.jsonl','provider-batches.jsonl','final-records.jsonl'):
            src=identity(folder/name);need(identity(local/name)['sha256']==src['sha256'],'retained/source journal differs');sources.append(src)
        previous_request=result['request_sha256'];previous_sequences=reset['post_sequences'];previous_position=len(inputs);inventories=reset['inventories']
    need(len(rows)==12 and sum(r['output_tokens'] for r in rows)==5965,'complete fixed suite')
    comparison=json.loads(gzip.decompress((proof/'final-target-comparison.json.gz').read_bytes()))
    need(comparison['passed'] is True and len(comparison['compared_source_keys'])==2065,'final sealed target comparison result differs')
    draft=read(proof/'final-draft-authentication.json');need(draft['passed'] is True and draft['allocation_count']==73 and draft['parity_against_independent_reference'] is False,'final draft scope differs')
    observations=lines(run/'observations.jsonl');need(all(o['known_fault_baseline_matches'] is True and len(o['kernel']['faults'])==14 for o in observations),'new fault in observations')
    derived=aggregate(rows);need(derived['full_natural_completion']['median']==summary['timing']['candidate_median'],'full completion median differs')
    policy=ROOT/'docs/localmaxxing.md';agents=ROOT/'AGENTS.md';reference=HERE/'reference/summary.json'
    disposition=dict(status='withheld',submitted=False,server_dry_run_performed=False,
        reasons=['Measured negative on retained full-natural-completion diagnostic:41.572519 versus prior matching four-card42.311881; primary first99 comparison against prior candidates is not established here.',
                 'No neural.download.promotion-attestation.v1 for this exact performance JSON linking registered oracle, deterministic repeats/fresh-process evidence, unchanged verifier and explicit no-quality-loss decision.',
                 'Independent CPU reference still has6/5965 teacher-forced discrepancies; native-state/legacy-output equality does not resolve them.',
                 'These are controller committed-output observations and native reset-backed cached_tokens0, not an OpenAI usage report or completed external submission gate.'],
        quality_scope='Final target2065 buffers match prior cold suite only for decision-memo; all12 output IDs match retained engine outputs; no independent long draft state parity.',
        timestamp_window_available_all_prompts=True,eos333_is_metric_eligible=True,
        policy_sources=[identity(policy),identity(agents)],reference_disagreements=read(reference)['aggregate'],reference=identity(reference),
        prohibited_action_note='No new server/process repeat was requested or run; existing stability constraints remain unchanged.')
    metric=dict(schema='ownrt.persistent-rolling-derived-windows.v1',source_proof=identity(proof/'summary.json'),source_run=str(run),
        rows=rows,summary=derived,fixed_class_source=identity(class_path),fixed_classes=classmap,source_token_journals=[s for s in sources if s['path'].endswith('/tokens.jsonl')],
        metric_scope='Offline derived from actual controller committed-output timestamps;100 events,99 intervals. Primary is median of6 fixed class medians; ordinary all-prompt median is secondary.',
        ttft_definition='First committed output timestamp minus request_started_monotonic_s immediately before drive; includes prompt processing, canonical MTP work, first output head, queue/controller overhead and any lazy JIT. Excludes RESET, request-plan serialization, model loading and final DUMP.',
        prefill_definition='No isolated prefill-completion timestamp exists. prompt_tokens/TTFT is only an effective latency proxy; pure native prefill seconds and tok/s remain null.',
        wall_definition='Output_count/(drive_return_time-drive_start_time); includes prompt processing, post-output drain and final provider work, excludes RESET/DUMP/model loading.',
        old_service_comparison=dict(median=47.97057758420032,window='Full response aggregate native/service decode, not first99; individual old completion timestamps unavailable.',first99_rate=None,direct_first99_comparison=False),
        prior_four_card_full_response_median=42.311880797977615,localmaxxing=disposition,certified=False,speed_claim=False,implementation=identity(Path(__file__)))
    review=dict(schema='ownrt.persistent-rolling-suite-run-review.v1',passed=True,source_proof=identity(proof/'summary.json'),source_run=str(run),
        checks=checks,source_journals=sources,terminal=identity(run/'persistent-rolling-result.json'),auditor_cpu_receipt=identity(HERE/'persistent-rolling-suite-audit-cpu.json'),
        observations=dict(samples=len(observations),known_fault_signatures=14,all_baseline_matches=True,min_mem_available_bytes=min(o['memory']['MemAvailable'] for o in observations),
            last_sample_holders=observations[-1]['holders'],scope='Periodic samples occur while workers are live; terminal result independently records all exits0/no live PIDs.'),
        full_state_raw_reread=False,final_target_compared_buffers=2065,final_target_position=571,final_draft_authenticated_allocations=73,
        metric_summary=derived,localmaxxing=disposition,scope='Independent re-execution of frozen raw command/reset/provider/native validators and timestamp arithmetic; final raw-state comparison result authenticated without rereading model-sized arrays.',implementation=identity(Path(__file__)))
    for path,data in ((args.review_out,review),(args.metrics_out,metric)):
        with path.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
    print(json.dumps(dict(passed=True,class_balanced_first99=derived['primary']['median'],all_prompt_first99=derived['all_prompt_first99']['median'],
        ordinary_full_completion=derived['full_natural_completion']['median'],ttft_median=derived['ttft_seconds']['median'],localmaxxing='withheld')))


if __name__=='__main__':main()
