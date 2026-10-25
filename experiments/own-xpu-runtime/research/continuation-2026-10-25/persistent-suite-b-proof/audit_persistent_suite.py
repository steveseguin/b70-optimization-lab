#!/usr/bin/env python3
"""Independently audit terminal persistent-suite evidence without device access."""
import argparse
import gzip
import json
import math
from pathlib import Path
import shutil
import statistics

from finalize_persistent_proof import audit_request
from finalize_wavefront_proof import HERE, compare, identity, save, token_hash


def require(ok, message):
    if not ok:
        raise ValueError(message)


def timing(rows, outputs):
    require(len(rows) == len(outputs) and len(outputs) > 1, 'complete multi-token timing required')
    require([r['index'] for r in rows] == list(range(len(outputs)))
            and all(type(r['index']) is int for r in rows)
            and [r['token'] for r in rows] == outputs, 'timestamp token/index identity')
    stamps = [r['committed_monotonic_s'] for r in rows]
    require(all(type(t) in (float, int) and math.isfinite(t) for t in stamps)
            and all(a <= b for a, b in zip(stamps, stamps[1:])), 'finite monotonic timestamps required')
    seconds = stamps[-1] - stamps[0]
    require(seconds > 0, 'positive complete output span required')
    return dict(numerator=len(outputs)-1, denominator_seconds=seconds,
                first_timestamp=stamps[0], last_timestamp=stamps[-1],
                tokens_per_second=(len(outputs)-1)/seconds,
                window='First to last controller-observed committed output, full response; no first-99 inference.')


def cold(row):
    require(type(row.get('cached_tokens')) is int and row['cached_tokens'] == 0,
            'explicit zero cached_tokens required')
    require(row.get('prompt_state_reused') is False and row.get('process_reused') is True,
            'cold request state in reused process required')


def rates_summary(rates):
    require(rates and all(type(r) in (float, int) and math.isfinite(r) and r > 0 for r in rates),
            'finite positive rates required')
    return dict(median=statistics.median(rates), minimum=min(rates), maximum=max(rates))


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def distribution(values):
    values = sorted(values)
    def quantile(p):
        offset = (len(values)-1)*p
        lower = int(offset)
        return values[lower] + (values[min(lower+1,len(values)-1)]-values[lower])*(offset-lower)
    return dict(count=len(values), total_ms=sum(values), minimum_ms=min(values) if values else None,
                median_ms=statistics.median(values) if values else None,
                p90_ms=quantile(.9) if values else None, p99_ms=quantile(.99) if values else None,
                maximum_ms=max(values) if values else None)


def breakdown(plan, request, events, token_rows):
    # Explicit warm-up exclusion for tuning only. The first generated transition
    # can include first-use work. Do not remove it from reported full-response rates.
    start, end = token_rows[1]['committed_monotonic_s'], token_rows[-1]['committed_monotonic_s']
    span_ms = (end-start)*1000
    sends = {(e['stage'],e['sequence']):e for e in events if e.get('event') == 'send'}
    replies = {(e['stage'],e['sequence']):e for e in events if e.get('event') == 'reply'}
    draft = [e for e in events if e.get('event') == 'live-draft'
             and e['monotonic_s']-e['busy_ms']/1000 >= start and e['monotonic_s'] <= end]
    stages = []
    for stage in plan['stages']:
        sid = stage['id']
        native = Path(stage['native_output'])/'requests'/request.name
        native_rows = lines(native/'wavefront.jsonl')
        selected = []
        for row in native_rows:
            send, reply = sends[(sid,row['sequence'])], replies[(sid,row['sequence'])]
            if send['monotonic_s'] >= start and reply['monotonic_s'] <= end:
                selected.append((row,send,reply))
        resolved = {r['ticket']:r['op'] for r in native_rows if r['op'] in (21,22)}
        compute = [r for r,_,_ in selected if r['op'] == 20]
        require(all(r['sequence'] in resolved for r in compute), 'tuning ROW lacks terminal commit/abort')
        rtt = [(reply['monotonic_s']-send['monotonic_s'])*1000 for _,send,reply in selected]
        residual = [duration-reply['busy_ms'] for duration,(_,_,reply) in zip(rtt,selected)]
        clipped_command_ms = sum(max(0,min(end,replies[k]['monotonic_s'])-max(start,send['monotonic_s']))*1000
            for k,send in sends.items() if k[0] == sid)
        stages.append(dict(stage=sid, begin=stage['begin'], end=stage['end'], layers=stage['end']-stage['begin'],
            row_wall_ms=distribution([r['wall_ms'] for r in compute]),
            row_noncheckpoint_wall_ms=distribution([r['wall_ms']-r['checkpoint_ms'] for r in compute]),
            capture_ms=distribution([r['checkpoint_ms'] for r in compute if r['tentative']]),
            commit_ms=distribution([r['checkpoint_ms'] for r,_,_ in selected if r['op']==21 and r['tentative']]),
            restore_ms=distribution([r['checkpoint_ms'] for r,_,_ in selected if r['op']==22]),
            wasted_row_ms=distribution([r['wall_ms'] for r in compute if resolved[r['sequence']]==22]),
            committed_row_ms=distribution([r['wall_ms'] for r in compute if resolved[r['sequence']]==21]),
            native_all_command_ms=distribution([reply['busy_ms'] for _,_,reply in selected]),
            controller_roundtrip_ms=distribution(rtt), controller_roundtrip_minus_native_wall_ms=distribution(residual),
            command_roundtrip_occupied_ms=clipped_command_ms,
            no_target_command_inflight_ms=span_ms-clipped_command_ms,
            canonical_draft_native_ms=distribution([r['busy_ms'] for r in draft] if sid==0 else [])))
    return dict(window='Second through last generated-token controller timestamps; fully contained commands for distributions, clipped commands for occupancy. Prompt and first generated transition excluded for tuning only; no claim that all compilation effects are absent.',
        start_timestamp=start,end_timestamp=end,span_ms=span_ms, stages=stages,
        proposal_hits=sum(e.get('event')=='proposal-hit' and start<=e['monotonic_s']<=end for e in events),
        proposal_misses=sum(e.get('event')=='proposal-miss' and start<=e['monotonic_s']<=end for e in events),
        scope='Native wall includes host dispatch/waits, not isolated GPU kernel time. ROW wall includes capture. Roundtrip-minus-native includes IPC, tracing and coordinator scheduling. No-target-command time includes dependencies and (on stage0) draft work; it is not measured GPU idle. Stages overlap, so stage totals must not be summed as elapsed time.',
        quantile_definition='Linear interpolation at (n-1)*p; ordinary even median.')


def retain(path, destination):
    """Compact trace retention; original source hash is recorded separately."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.jsonl':
        destination = destination.with_suffix(destination.suffix+'.gz')
        destination.write_bytes(gzip.compress(path.read_bytes(), mtime=0))
    else:
        shutil.copyfile(path, destination)
    return dict(source=identity(path), retained=identity(destination))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--baseline', type=Path, default=HERE.parent/'review-2026-10-25/normal-service-suite.json')
    args = p.parse_args()
    run, out = args.run.resolve(), args.out.resolve()
    terminal = json.loads((run/'result.json').read_text())
    finished = json.loads((run/'suite-result.json').read_text())
    plan = json.loads((run/'plan.json').read_text())
    suite = json.loads(Path(plan['suite']).read_text())
    baseline = json.loads(args.baseline.read_text())
    require(identity(Path(plan['suite']))['sha256'] == plan['suite_sha256'], 'suite input SHA')
    require(terminal.get('passed') is True and terminal.get('error') is None
            and terminal.get('live_pids') == [] and terminal.get('returncodes') == {str(s['id']): 0 for s in plan['stages']},
            'terminal clean worker exit required')
    require(finished.get('passed') is True and plan['dump_each'] is False
            and len(suite['prompts']) == len(baseline['rows']) == len(finished['prompts']) == 12,
            'complete twelve-prompt suite required')
    require(plan['activation_dtype'] == 'F32' and len(plan['stages']) == 4
            and plan.get('live_draft') is True and plan.get('use_proposals') is True, 'PP4 live F32 identity')
    out.mkdir(parents=True, exist_ok=False)
    receipts = [retain(run/name, out/name) for name in ('plan.json','result.json','suite-result.json','admission.json','unit.json')]
    receipts += [retain(Path(plan['suite']), out/'suite.json'), retain(args.baseline, out/'baseline.json')]
    previous = None
    rows, audits, breakdowns = [], [], []
    for index, (spec, old) in enumerate(zip(suite['prompts'], baseline['rows'])):
        request = run/f'request-{index:02d}-{spec["id"]}'
        row = json.loads((request/'result.json').read_text())
        require(row == finished['prompts'][index] and row['passed'] is True, 'suite/request record equality')
        require(spec['id'] == old['prompt_id'] == row['id'], 'frozen prompt ordering identity')
        require(spec['prompt_tokens'] == old['prompt_token_ids'] and row['output_ids'] == old['output_token_ids']
                and spec['expected_output_ids'] == old['output_token_ids'], 'baseline prompt/output token identity')
        require(type(old.get('cached_tokens')) is int and old['cached_tokens'] == 0, 'baseline cache observation')
        cold(row)
        audit = audit_request(run, plan, request, row, index, previous)
        require(audit['passed'], f'{spec["id"]}: native cold/reset audit: {audit["errors"]}')
        previous = row['final_sequences']
        events = lines(request/'schedule.jsonl')
        pairs = [e for e in events if e.get('event') == 'live-draft']
        inputs = spec['prompt_tokens'] + row['output_ids'][:-1]
        require([e['position'] for e in pairs] == list(range(1, len(inputs)))
                and [e['token'] for e in pairs] == inputs[1:]
                and all(e['head'] is (e['position']+1 >= len(spec['prompt_tokens'])) for e in pairs),
                'canonical true-pair sequence/head mask')
        token_rows = lines(request/'tokens.jsonl')
        timed = timing(token_rows, row['output_ids'])
        recorded = row['timing']
        require(timed['numerator'] == recorded['decode_intervals']
                and timed['denominator_seconds'] == recorded['committed_output_span_seconds']
                and timed['tokens_per_second'] == recorded['decode_tokens_per_second'], 'independent candidate timing arithmetic')
        require(old['decode_numerator'] == old['decode_intervals'] == len(old['output_token_ids'])-1,
                'baseline full-response numerator')
        old_rate = old['decode_numerator']/(old['decode_wall_ms']/1000)
        require(math.isclose(old_rate, old['decode_tok_s'], rel_tol=1e-12), 'baseline timing arithmetic')
        hits = sum(e.get('event') == 'proposal-hit' for e in events)
        misses = sum(e.get('event') == 'proposal-miss' for e in events)
        rows.append(dict(id=spec['id'], prompt_tokens=len(spec['prompt_tokens']), output_tokens=len(row['output_ids']),
                         exact_output_ids=True, cold_prompt_state=True, canonical_draft_pairs=len(pairs),
                         output_token_sha256=token_hash(row['output_ids']), candidate=timed,
                         baseline_tokens_per_second=old_rate, observed_rate_ratio=timed['tokens_per_second']/old_rate,
                         hits=hits, misses=misses, reset_seconds=row['reset_seconds'],
                         first_token_seconds=recorded['first_token_seconds'],
                         full_response_seconds=recorded['full_response_seconds']))
        local = out/request.name
        for name in ('result.json','schedule.jsonl','tokens.jsonl'):
            receipts.append(retain(request/name, local/name))
        for stage in plan['stages']:
            native = Path(stage['native_output'])/'requests'/request.name
            for name in ('wavefront-reset.json','reset.json','wavefront.jsonl') + (('draft-rows.jsonl',) if stage['first'] else ()):
                receipts.append(retain(native/name, local/f'stage{stage["id"]}'/name))
        save(local/'audit.json', audit)
        stage_timing = breakdown(plan, request, events, token_rows)
        save(local/'stage-timing.json', stage_timing)
        breakdowns.append(dict(id=spec['id'], **stage_timing))
        audits.append(audit)
    candidate_rates = [r['candidate']['tokens_per_second'] for r in rows]
    old_rates = [r['baseline_tokens_per_second'] for r in rows]
    candidate_stats, old_stats = rates_summary(candidate_rates), rates_summary(old_rates)
    require(candidate_stats['median'] == finished['decode_median_tokens_per_second'], 'conventional candidate median')
    require(math.isclose(old_stats['median'], baseline['median_decode_tok_s'], rel_tol=1e-12), 'conventional baseline median')
    # Authenticate the terminal dump, without claiming per-prompt state equality.
    last = suite['prompts'][-1]
    state_set = dict(schema='ownrt.pipeline-state-set.v2', mode='verified-wavefront',
        layer_count=plan['boundaries'][-1], require_byte_verified_restores=plan['verify_restore'],
        input_identity=dict(model_sha256=plan['model_identity_sha256'], arithmetic='F32',
            prompt_token_sha256=token_hash(last['prompt_tokens']), output_token_sha256=token_hash(rows and finished['final_output_ids']),
            position=finished['final_input_position']), stages=[])
    for stage in plan['stages']:
        native = Path(stage['native_output'])/'requests'/f'request-11-{last["id"]}'
        dump = native/'state-2147483647'
        state_set['stages'].append(dict(id=stage['id'], begin=stage['begin'], end=stage['end'], dump=str(dump),
            plan=str(native/'launch-plan.json'), metadata=str(native/'pipeline-stage.json'),
            quiescence=str(native/'state-2147483647.wavefront-state.json')))
        for name in ('launch-plan.json','pipeline-stage.json','wavefront-checkpoint-layout.json','state-2147483647.wavefront-state.json'):
            receipts.append(retain(native/name, out/'final-state'/f'stage{stage["id"]}'/name))
        for name in ('state-seal.txt','state-index.tsv','state.json'):
            receipts.append(retain(dump/name, out/'final-state'/f'stage{stage["id"]}'/dump.name/name))
    save(out/'final-state-set.json', state_set)
    compare.load_set(out/'final-state-set.json')
    save(out/'stage-timing.json', dict(requests=breakdowns, boundaries=plan['boundaries'],
        scope='Descriptive per-request decode-window measurements only; no estimated benefit from different boundaries.'))
    summary = dict(schema='ownrt.persistent-suite-audit.v1', passed=True, requests=12,
        output_tokens=sum(r['output_tokens'] for r in rows), exact_output_ids=True,
        all_cold_native_resets_checked=True, all_prompt_rows_executed=True, final_target_dump_authenticated=True,
        full_state_parity_for_twelve_prompts=False, candidate_rates=candidate_stats, baseline_rates=old_stats,
        median_rate_ratio=candidate_stats['median']/old_stats['median'],
        pooled_interval_rate=sum(r['candidate']['numerator'] for r in rows)/sum(r['candidate']['denominator_seconds'] for r in rows),
        rows=rows, receipts=receipts, finalizer=identity(Path(__file__)), speed_claim=False, certified=False,
        timing_scope='Full-response output intervals. Candidate controller COMMIT receipt timestamp vs baseline native completion service aggregate; different observation layers. Model/runtime/page caches warm; request state cold. Not a controlled kernel or certified benchmark.',
        arithmetic_scope='Exact frozen GPU F32 output IDs. Six prior CPU-reference disagreements remain unresolved.',
        raw_retention='Original external raw final state preserved; compact native/controller traces retained here.')
    save(out/'summary.json', summary)
    (out/'RESULT.md').write_text(f'''# Persistent PP4 twelve-prompt audit: PASSED

All {summary['output_tokens']:,} output IDs match the frozen normal-service suite.
Every prompt was executed anew after a native cold reset in the same four workers;
all reset receipts, preserved allocation layouts, global wire sequences, native
commands and canonical draft input pairs passed independent checks.

Observed full-response decode median: **{candidate_stats['median']:.4f} tok/s**
versus **{old_stats['median']:.4f} tok/s** ({summary['median_rate_ratio']:.4f}×).
Each rate is (output count − 1)/(last timestamp − first timestamp); the even-sized
suite uses the mean of its two middle rates. These are uncertified observations:
candidate timestamps follow controller COMMIT replies, while the baseline uses
native completion aggregates. No first-99 interval timestamps are inferred.

All four workers exited cleanly. The final target dump and quiescence are
authenticated; this suite did not dump and compare full state for every prompt.
Earlier two-request reset qualification supplies that narrower state proof.
Six CPU-reference disagreements remain unresolved. No draft training occurred.

[Structured audit and source hashes](summary.json), [terminal result](result.json),
[suite records](suite-result.json), [final state manifest](final-state-set.json).
Original raw final state remains external. Compact native/controller traces are retained.
''')
    print(json.dumps({k:summary[k] for k in ('passed','requests','output_tokens','candidate_rates','baseline_rates','median_rate_ratio')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
