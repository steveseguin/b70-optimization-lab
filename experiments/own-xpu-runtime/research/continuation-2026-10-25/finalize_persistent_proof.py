#!/usr/bin/env python3
"""Audit repeated cold requests in one terminally clean worker set; CPU only."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

from finalize_wavefront_proof import HERE, compare, identity, save
import finalize_live_proof as live_proof
from finalize_live_proof import compressed
import compare_draft_state as draft_compare


def same_fields(actual, expected):
    return all(type(actual.get(k)) is type(v) and actual[k]==v for k,v in expected.items())


def audit_request(run, plan, request, row, index, previous_final):
    errors=[];receipts=[];native_counts=[]
    def check(ok, why):
        if not ok:errors.append(why)
    initial=row['initial_sequences'];final=row['final_sequences']
    events=[json.loads(line) for line in (request/'schedule.jsonl').read_text().splitlines()]
    pairs=[r for r in events if r.get('event')=='live-draft']
    spec=json.loads(Path(plan['suite']).read_text())['prompts'][index]
    inputs=spec['prompt_tokens']+row['output_ids'][:-1]
    check(row.get('cached_tokens')==0 and type(row.get('cached_tokens')) is int
          and row.get('prompt_state_reused') is False and row.get('process_reused') is True,'cold-state declaration')
    for stage in plan['stages']:
        sid=stage['id'];native=Path(stage['native_output'])/'requests'/request.name
        reset=json.loads((native/'wavefront-reset.json').read_text())
        expected_sequence=1 if previous_final is None else previous_final[sid]+2 # per-request DUMP then RESET
        expected=dict(schema='ownrt.pipeline-reset.v1',passed=True,stage_id=sid,global_sequence=expected_sequence,
            target_position=0,draft_position=0 if stage['first'] else None,pending_ticket=False,sticky_error=0,
            allocation_ids_preserved=True,context_extent=32,alternate_extent=32,counters_reset=True,trace_reset=True)
        check(same_fields(reset,expected) and initial[sid]==expected_sequence,f'stage{sid} cold reset identity/sequence')
        recorded=row['reset_receipts'][sid]
        check(all(recorded.get(k)==v for k,v in reset.items()) and recorded['native_output']==str(native),
              f'stage{sid} controller/native reset receipt disagreement')
        reset_work=json.loads((native/'reset.json').read_text())
        check(reset_work.get('passed') is True and reset_work.get('allocation_ids_preserved') is True
              and type(reset_work.get('allocations')) is int and reset_work['allocations']>0
              and type(reset_work.get('bytes')) is int and reset_work['bytes']>0,f'stage{sid} actual reset work')
        metadata=Path(stage['native_output'])/f'reset-{expected_sequence}.txt'
        check(metadata.read_text()==str(native)+'\n\n',f'stage{sid} admitted reset destination/oracle')
        # Sidecars copy the original physical allocation identities. The native
        # checkpoint validates each live ID/label/extent at every boundary.
        for name in ('launch-plan.json','pipeline-stage.json','wavefront-checkpoint-layout.json'):
            check((native/name).read_bytes()==(Path(stage['native_output'])/name).read_bytes(),
                  f'stage{sid} immutable allocation/layout sidecar changed: {name}')
        layout=json.loads((native/'wavefront-checkpoint-layout.json').read_text())
        check(layout.get('complete_mutable_physical_allocations') is True
              and layout.get('partitioned_draft') is False,f'stage{sid} default complete-owner checkpoint required')
        sent=[r for r in events if r.get('event')=='send' and r['stage']==sid]
        replies=[r for r in events if r.get('event')=='reply' and r['stage']==sid]
        check([(r['op'],r['sequence'],r['row'],r['position']) for r in sent]
              ==[(r['op'],r['sequence'],r['row'],r['position']) for r in replies],f'stage{sid} every command replied in order')
        wire=sent+([r for r in pairs] if sid==0 else [])
        check(sorted(r['sequence'] for r in wire)==list(range(initial[sid]+1,final[sid]+1)),
              f'stage{sid} global wire sequence has gap/duplicate/reset')
        native_rows=[json.loads(line) for line in (native/'wavefront.jsonl').read_text().splitlines()]
        check(len(native_rows)==len(sent),f'stage{sid} native row trace complete')
        for observed,issued in zip(native_rows,sent):
            expected_row=dict(stage=sid,sequence=issued['sequence'],op=issued['op'],position=issued['position'],
                token=issued['token'],fixture=max(0,issued['position']-len(spec['prompt_tokens'])+2),
                ticket=issued['sequence'] if issued['op']==20 else issued['speculative'])
            check(same_fields(observed,expected_row),f'stage{sid} native command differs from controller')
        commits=[r for r in native_rows if r['op']==21]
        check([r['position'] for r in commits]==list(range(len(inputs)))
              and [r['token'] for r in commits]==inputs,f'stage{sid} every cold prompt/output input committed once')
        prompt_rows=[r for r in native_rows if r['op']==20 and r['position']<len(spec['prompt_tokens'])]
        check([r['position'] for r in prompt_rows]==list(range(len(spec['prompt_tokens'])))
              and [r['token'] for r in prompt_rows]==spec['prompt_tokens'],f'stage{sid} prompt was fully executed')
        if sid==0:
            native_draft=[json.loads(line) for line in (native/'draft-rows.jsonl').read_text().splitlines()]
            check([(r['draft_position']+1,r['confirmed_token'],r['head'],r['guess']) for r in native_draft]
                  ==[(r['position'],r['token'],r['head'],r['proposal']) for r in pairs],
                  'actual provider trace differs from canonical controller pairs')
        receipts.append(dict(stage=sid,reset=reset,reset_work=reset_work,
            reset_source=identity(native/'wavefront-reset.json'),metadata_source=identity(metadata)))
        native_counts.append(dict(stage=sid,wire_start=initial[sid],wire_end=final[sid],native_rows=len(native_rows),
                                  committed_rows=len(commits),prompt_rows=len(prompt_rows)))
    return dict(passed=not errors,errors=errors,reset_receipts=receipts,execution=native_counts,
                observed_draft_pairs=len(pairs),scope='All prompt rows executed anew; native reset/work receipts and fixed allocation identities validated. Process/model/page caches remain warm.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();run,out=args.run.resolve(),args.out.resolve()
    terminal=json.loads((run/'result.json').read_text())
    suite_result=json.loads((run/'suite-result.json').read_text())
    plan=json.loads((run/'plan.json').read_text())
    suite=json.loads(Path(plan['suite']).read_text())
    assert identity(Path(plan['suite']))['sha256']==plan['suite_sha256']
    assert len(suite['prompts'])==2 and plan['dump_each'] is True
    out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.json','result.json','suite-result.json','admission.json','unit.json'):
        shutil.copyfile(run/name,out/name)
    shutil.copyfile(plan['suite'],out/'suite.json')
    reference=HERE/'live-pp4-proof'
    previous_final=None;audits=[];proofs=[]
    for index,spec in enumerate(suite['prompts']):
        request=run/f'request-{index:02d}-{spec["id"]}'
        row=json.loads((request/'result.json').read_text())
        audit=audit_request(run,plan,request,row,index,previous_final)
        previous_final=row['final_sequences']
        # Derived inputs adapt the shared finalizer to per-request native paths.
        # Every original record is retained and hash-bound; no run is fabricated.
        derived=out/f'input-{request.name}';derived.mkdir()
        request_plan=copy.deepcopy(plan)
        request_plan.update(prompt_tokens=spec['prompt_tokens'],max_new=spec['max_new'],
                            derivation=dict(original_plan=identity(run/'plan.json'),request_result=identity(request/'result.json')))
        for stage in request_plan['stages']:
            stage['native_output']=str(Path(stage['native_output'])/'requests'/request.name)
        request_result=dict(row['driver_result'],passed=terminal.get('passed') is True and row['passed'] is True,
            error=terminal.get('error'),live_pids=terminal.get('live_pids'),returncodes=terminal.get('returncodes'),
            derivation=dict(outer_terminal=identity(run/'result.json'),request_result=identity(request/'result.json')))
        save(derived/'plan.json',request_plan);save(derived/'result.json',request_result)
        for name in ('schedule.jsonl','tokens.jsonl'):shutil.copyfile(request/name,derived/name)
        for name in ('admission.json','unit.json'):shutil.copyfile(run/name,derived/name)
        shutil.copyfile(request/'result.json',derived/'original-request-result.json')
        proof=out/request.name
        saved_argv=sys.argv
        try:
            sys.argv=[str(Path(live_proof.__file__)),'--run',str(derived),'--out',str(proof),
                '--dump-marker',str(2000000000+index),'--draft-reference',str(reference/'draft-state-set.json')]
            code=live_proof.main()
        finally:sys.argv=saved_argv
        audit['complete_state_and_legacy_gate']=code==0
        target=compare.compare(compare.load_set(reference/'candidate-state-set.json'),compare.load_set(proof/'candidate-state-set.json'))
        audit['target_exact_vs_accepted_live_pp4']=target['passed']
        compressed(proof/'accepted-live-target-comparison.json.gz',target)
        save(proof/'reset-audit.json',audit)
        audits.append(audit);proofs.append(proof)
    target_cross=compare.compare(compare.load_set(proofs[0]/'candidate-state-set.json'),compare.load_set(proofs[1]/'candidate-state-set.json'))
    draft_cross=draft_compare.compare(draft_compare.load_set(proofs[0]/'draft-state-set.json'),draft_compare.load_set(proofs[1]/'draft-state-set.json'))
    final_dump_checks=[]
    for stage in plan['stages']:
        native=Path(stage['native_output'])/'requests'/proofs[-1].name
        for suffix in ('', '.draft') if stage['first'] else ('',):
            before=native/f'state-2000000001{suffix}'
            after=native/f'state-2147483647{suffix}'
            final_dump_checks.append(dict(stage=stage['id'],kind='draft' if suffix else 'target',
                passed=compare.BUNDLE.read_state(before)==compare.BUNDLE.read_state(after),
                per_request_seal=identity(before/'state-seal.txt'),outer_final_seal=identity(after/'state-seal.txt')))
    compressed(out/'request-target-comparison.json.gz',target_cross)
    compressed(out/'request-draft-comparison.json.gz',draft_cross)
    passed=all(a['passed'] and a['complete_state_and_legacy_gate'] and a['target_exact_vs_accepted_live_pp4'] for a in audits) \
        and target_cross['passed'] and draft_cross['passed'] and suite_result.get('passed') is True \
        and all(row['passed'] for row in final_dump_checks)
    summary=dict(schema='ownrt.persistent-reset-proof.v1',passed=passed,requests=2,
        same_workers=True,prompt_state_reused=False,all_prompt_rows_executed=True if all(a['passed'] for a in audits) else None,
        target_state_exact_between_requests=target_cross['passed'],draft_state_exact_between_requests=draft_cross['passed'],
        request_audits=audits,final_dump_checks=final_dump_checks,
        source_run=str(run),raw_retention='Original run paths preserved; durable archival pending.',
        finalizer=identity(Path(__file__)),speed_claim=False,diagnostic_only=True)
    save(out/'summary.json',summary)
    (out/'RESULT.md').write_text(f'''# Persistent cold reset proof: {'PASSED' if passed else 'FAILED'}

Two identical 87-token prompts ran in the same four native processes, with a
quiescent cold reset before each. Each request emitted the 32 baseline tokens,
and its 2,065 target buffers and 73 draft allocations were compared to the
accepted live PP4 run and to the other request. Full raw hidden pair identity,
all 117 provider steps and all 32 legacy draft proposals were checked separately.

All gates passed: {passed}. Every stage's global wire sequence, native command
trace, cold reset receipt, preserved allocation layout and all 87 executed
prompt rows were checked. This proves request-state reuse was disabled for
these requests; process/model/page caches remained warm. No speed claim.

[Summary](summary.json), [target cross-comparison](request-target-comparison.json.gz),
[draft cross-comparison](request-draft-comparison.json.gz). Per-request packets
retain full comparisons and reset-audit details. Derived input adapters are
explicitly hash-bound to the original shared run and request records.
Original raw state remains external; durable archival is pending.
''')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('request_audits','final_dump_checks','finalizer')}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
