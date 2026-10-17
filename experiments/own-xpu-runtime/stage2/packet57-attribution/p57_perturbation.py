#!/usr/bin/env python3
"""Post-device attribution/perturbation report; never a speed promotion gate.

summarize(control_run, instrumented_run) reads retained receipts and sites only.
The coordinator owns device work. Run this script with nice/taskset/python3 -B.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics as st
from timeline import extract, sha

REQUIRED_DRAFT_CLASSES = {'attention','moe_experts','shared_expert','hc_norm_merge',
                          'embedding_ple','head_prefix','argmax','transfers'}
REQUIRED_TARGET_LAYERS = {'blk.19','blk.22','blk.23','blk.24'}
REQUIRED_TARGET_CLASSES = {'attention','moe_experts','shared_expert','hc_norm_merge'}


def paired_summary(pairs, metric="cycle_ms"):
    result = {}
    for branch in ('all','hit','miss'):
        rows = [(a,b) for a,b in pairs if branch=='all' or a['hit']==(branch=='hit')]
        if not rows:
            result[branch] = dict(count=0, control_median_ms=None, instrumented_median_ms=None,
                                  ratio_instrumented_over_control=None, paired_delta_median_ms=None)
            continue
        a=st.median(a[metric] for a,b in rows)
        b=st.median(b[metric] for a,b in rows)
        result[branch] = dict(count=len(rows), control_median_ms=a,instrumented_median_ms=b,
                             ratio_instrumented_over_control=b/a,
                             paired_delta_median_ms=st.median(b[metric]-a[metric] for a,b in rows))
    return result


def validate_event(row, expected_rank):
    required={'schema','rank','fixture','position','speculative','label','class','event','start_ns','end_ns','device_ms'}
    if not required.issubset(row) or row['schema']!='packet57.event.v1':
        raise ValueError('missing/unknown event schema')
    if not isinstance(row['event'],int) or row['event']<1 or not isinstance(row['speculative'],bool):
        raise ValueError('invalid event identity/speculative flag')
    if row['rank']!=expected_rank or not 9<=row['fixture']<=16:
        raise ValueError('wrong event rank or sampling fixture')
    start,end=row['start_ns'],row['end_ns']
    if not isinstance(start,int) or not isinstance(end,int) or not 0<start<end:
        raise ValueError('missing/zero/negative event duration')
    if not math.isfinite(row['device_ms']) or row['device_ms']<=0:
        raise ValueError('invalid device duration')
    if not math.isclose(row['device_ms'],(end-start)/1e6,rel_tol=1e-5,abs_tol=1e-8):
        raise ValueError('event duration disagrees with timestamps')


def classify_scope(event):
    label=event['label']
    if label.startswith('draft.'):
        return 'draft'
    if label.startswith('blk.'):
        return '.'.join(label.split('.')[:2])
    return 'target_boundary'


def read_events(prompt_dir, sources):
    rows=[]
    for rank in (0,1):
        path=prompt_dir/f'rank{rank}/sites.jsonl'
        if not path.exists():raise ValueError(f'missing sites file {path}')
        sources.append(dict(path=str(path),sha256=sha(path)))
        seen=set()
        for line in path.read_text().splitlines():
            row=json.loads(line)
            # Legacy site rows may coexist; only the explicitly versioned
            # packet57 device events participate in attribution.
            if row.get('schema')!='packet57.event.v1':continue
            validate_event(row,rank)
            if row['event'] in seen:raise ValueError('duplicate GPU event in request/rank')
            seen.add(row['event']);rows.append(row)
    return rows


def analyze_events(events, pair_by_position):
    sums=defaultdict(float);counts=defaultdict(int);ops=defaultdict(set);groups=set();sampled=set()
    coverage=defaultdict(set)
    for e in events:
        scope=classify_scope(e)
        expected_rank = 1 if scope=='draft' or scope in {'blk.23','blk.24'} else 0 if scope in {'blk.19','blk.22'} else None
        if expected_rank is not None and e['rank']!=expected_rank:
            raise ValueError('event scope on wrong rank')
        coverage[(scope,e['fixture'],e['speculative'])].add(e['class'])
        # Speculative HALF(p+1) runs in cycle(p). Corrected HALF(p), DRAFT(p)
        # and rank-1 HALF(p) run in cycle(p). Never compare cross-card clocks.
        position=e['position']-int(e['speculative'] and scope!='draft')
        if position not in pair_by_position:raise ValueError('event does not join a generated cycle')
        sampled.add(position)
        key=(scope,e['rank'],e['class'])
        sums[key]+=e['device_ms'];counts[key]+=1
        ops[key].add((e['position'],e['speculative']))
        groups.add((scope,e['rank'],e['position'],e['speculative']))
    draft={cls for scope,rank,cls in sums if scope=='draft'}
    missing=REQUIRED_DRAFT_CLASSES-draft
    target={scope for scope,rank,cls in sums if scope.startswith('blk.')}
    if missing:raise ValueError('missing draft event classes: '+','.join(sorted(missing)))
    if REQUIRED_TARGET_LAYERS-target:raise ValueError('missing target layer events: '+','.join(sorted(REQUIRED_TARGET_LAYERS-target)))
    for fixture in range(9,17):
        if not REQUIRED_DRAFT_CLASSES.issubset(coverage.get(('draft',fixture,False),set())):
            raise ValueError('incomplete draft class inventory at fixture '+str(fixture))
        for scope in REQUIRED_TARGET_LAYERS:
            if not any(REQUIRED_TARGET_CLASSES.issubset(coverage.get((scope,fixture,spec),set())) for spec in (False,True)):
                raise ValueError('incomplete target class inventory at '+scope+' fixture '+str(fixture))
    return sums,counts,ops,groups,sampled


def summarize(control_root, instrumented_root):
    control_root,instrumented_root=Path(control_root),Path(instrumented_root)
    controls={p.parent.name:p for p in (control_root/'repeat-1').glob('*/receipt.json')}
    instruments={p.parent.name:p for p in (instrumented_root/'repeat-1').glob('*/receipt.json')}
    if len(controls)!=12 or controls.keys()!=instruments.keys():
        raise ValueError('requires matched complete twelve-prompt arms')
    sources=[];prompts={};full=[];sampled=[];draft_sampled=[];complete_layers=defaultdict(list);incomplete_layers=defaultdict(int);sums=defaultdict(float);counts=defaultdict(int);op_counts=defaultdict(int)
    for prompt in sorted(controls):
        cp,ip=controls[prompt],instruments[prompt]
        cj,ij=json.loads(cp.read_bytes()),json.loads(ip.read_bytes())
        for path,j in [(cp,cj),(ip,ij)]:
            sources.append(dict(path=str(path),sha256=sha(path)))
            if not j.get('passed') or not j.get('oracle_check',{}).get('passed'):
                raise ValueError('failed target-oracle receipt')
            if j.get('cached_tokens')!=0 or j.get('output_tokens')!=128:
                raise ValueError('requires cold 128-output-token request')
        for identity in ('prompt_id','prompt_token_sha256','output_token_sha256','target_split','binary_sha256','arithmetic'):
            if not cj.get(identity) or cj.get(identity)!=ij.get(identity):
                raise ValueError('arm identity/output mismatch: '+identity)
        cc,ic=extract(cj),extract(ij)
        if len(cc)!=127 or len(ic)!=127:raise ValueError('incomplete generated interval span')
        pairs={}
        for a,b in zip(cc,ic):
            if a['position']!=b['position'] or a['hit']!=b['hit']:
                raise ValueError('paired cycle identity/acceptance mismatch')
            pairs[a['position']]=(a,b)
        events=read_events(ip.parent,sources)
        ss,nn,oo,groups,touched=analyze_events(events,pairs)
        layer_groups=defaultdict(list)
        for e in events:
            scope=classify_scope(e)
            if scope in REQUIRED_TARGET_LAYERS:
                layer_groups[(scope,e['rank'],e['position'],e['speculative'])].append(e)
        for (scope,rank,position,spec),rows in layer_groups.items():
            key=(scope,rank,spec)
            complete=any(e['label']==scope+'.ffn.combine' for e in rows) and REQUIRED_TARGET_CLASSES.issubset({e['class'] for e in rows})
            if complete:complete_layers[key].append(sum(e['device_ms'] for e in rows))
            else:incomplete_layers[key]+=1
        selected=[pairs[p] for p in sorted(touched)]
        selected_draft=[pairs[pos] for pos in sorted({e['position'] for e in events if classify_scope(e)=='draft'})]
        full.extend(pairs.values());sampled.extend(selected);draft_sampled.extend(selected_draft)
        for k,value in ss.items():sums[k]+=value;counts[k]+=nn[k];op_counts[k]+=len(oo[k])
        prompts[prompt]=dict(full=paired_summary(list(pairs.values())),
                            sampled=paired_summary(selected),sampled_draft_wall=paired_summary(selected_draft,'D_wall_ms'),
                            sampled_positions=sorted(touched),
                            event_count=len(events),sampled_operation_groups=len(groups))
    coverage=paired_summary(sampled)
    if any(coverage[b]['count']==0 for b in ('hit','miss')):
        raise ValueError('sampled events require both hit and miss cycle coverage')
    # A single control/instrumented pair measures perturbation, not randomized
    # isolated causal effects. Scaled values are heuristic sensitivities only.
    factor=1/coverage['all']['ratio_instrumented_over_control']
    draft_coverage=paired_summary(draft_sampled,'D_wall_ms')
    if any(draft_coverage[b]['count']==0 for b in ('hit','miss')):
        raise ValueError('sampled draft events require both hit and miss cycle coverage')
    draft_factor=1/draft_coverage['all']['ratio_instrumented_over_control']
    totals=defaultdict(float)
    for (scope,rank,cls),value in sums.items():totals[(scope,rank)]+=value
    classes=[]
    for (scope,rank,cls),value in sorted(sums.items()):
        n=op_counts[(scope,rank,cls)]
        classes.append(dict(scope=scope,rank=rank,category=cls,event_count=counts[(scope,rank,cls)],
            operation_count=n,includes_partial_cancelled_operations=scope in REQUIRED_TARGET_LAYERS,
            measured_device_sum_ms=value,
            measured_device_mean_per_operation_ms=value/n,
            share_of_recorded_scope_device_time=value/totals[(scope,rank)],
            estimated_mean_per_operation_scaled_ms=value/n*factor,
            scaling_factor=factor,scaled_value_is_measurement=False,
            draft_wall_scaling_factor=draft_factor if scope=='draft' else None,
            estimated_mean_per_operation_draft_wall_scaled_ms=value/n*draft_factor if scope=='draft' else None))
    complete_layer_summary=[]
    for key in sorted(set(complete_layers)|set(incomplete_layers)):
        scope,rank,spec=key;values=complete_layers[key]
        complete_layer_summary.append(dict(layer=scope,rank=rank,speculative=spec,
            complete_operation_count=len(values),excluded_incomplete_operation_count=incomplete_layers[key],
            measured_device_sum_median_ms=st.median(values) if values else None,
            measured_device_sum_mean_ms=st.mean(values) if values else None,
            completion_rule='final ffn.combine event present and all four target classes; selected kernel event sum, not layer wall or transfers',
            destination_rank_cost_measured=False))
    return dict(schema='lab.packet57.perturbation.v1',passed=True,diagnostic=True,no_speed_claim=True,
        sources=sources,prompts=prompts,full_cycles=paired_summary(full),sampled_cycles=coverage,
        full_draft_wall=paired_summary(full,'D_wall_ms'),sampled_draft_wall=draft_coverage,
        classes=classes,complete_target_layers=complete_layer_summary,
        scale_definition='instrumented class mean * sampled control-cycle median / sampled instrumented-cycle median; draft_wall_scaled additionally uses paired sampled D-wall medians; both heuristic only, not corrected GPU time',
        scope='cycles touched by fixtures 9..16 events; speculative half mapped to previous-position cycle; includes boundary overlap; full 127 intervals reported separately',
        limitations=['Host/GPU clocks are not aligned; no cross-card GPU timestamp comparison.',
                     'Sparse target sites do not yield whole-model GPU idle or complete target-layer transfers.',
                     'Class shares describe recorded events, not shares of elapsed cycle wall time.',
                     'Target class operation means include partial cancelled attempts; use complete_target_layers for complete selected-layer event sums, separated by speculative/confirmed.',
                     'Complete layer event sums exclude general transfer labels and do not measure the same layer on the other rank.',
                     'Uniform cycle scaling does not recover class-specific uninstrumented costs or overlap.',
                     'One ordered control/profile pair does not separate instrumentation from temporal drift.'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--instrumented',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=summarize(args.control,args.instrumented)
    encoded=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:args.output.write_text(encoded)
    else:print(encoded,end='')


if __name__=='__main__':main()
