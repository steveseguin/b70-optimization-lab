#!/usr/bin/env python3
"""Read paired screen receipts/sites; diagnostic costs, never a speed claim."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics as st
from timeline import extract, sha

LAYERS = {'blk.22': (0, 'GDN'), 'blk.23': (0, 'QSA'),
          'blk.24': (1, 'GDN'), 'blk.27': (1, 'QSA')}
TARGET_CLASSES = {'attention', 'moe_experts', 'shared_expert', 'hc_norm_merge'}
DRAFT_CLASSES = TARGET_CLASSES | {'embedding_ple', 'head_prefix', 'argmax', 'transfers'}
BOUNDARIES = {'blk.0.hc.a.norm': (0,'begin'), 'blk.23.ffn.combine': (0,'end'),
              'blk.24.hc.a.norm': (1,'begin'), 'blk.47.ffn.combine': (1,'end')}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def stats(values):
    values = [v for v in values if v is not None]
    return dict(count=len(values), mean_us=st.mean(values), median_us=st.median(values),
                min_us=min(values), max_us=max(values)) if values else dict(count=0)


def scope(row):
    label = row['label']
    if label.startswith('draft.'):
        return 'draft'
    if label in BOUNDARIES and label.startswith(('blk.0.', 'blk.47.')):
        return 'target_span'
    if label.startswith('blk.'):
        return '.'.join(label.split('.')[:2])
    return 'target_boundary'


def validate_event(e, rank):
    require(e.get('schema') == 'packet57.event.v1', 'unknown event schema')
    require(e.get('rank') == rank and type(e.get('fixture')) is int and 9 <= e['fixture'] <= 16,
            'wrong rank/sample window')
    require(type(e.get('position')) is int and type(e.get('speculative')) is bool, 'bad event identity')
    require(type(e.get('event')) is int and e['event'] > 0, 'bad event ID')
    require(type(e.get('start_ns')) is int and type(e.get('end_ns')) is int
            and 0 < e['start_ns'] <= e['end_ns'] and (e['start_ns'] < e['end_ns'] or 'transfer' in e['label']),
            'invalid event timestamps')  # small copies can resolve to equal device timestamps (zero duration)
    require(isinstance(e.get('device_ms'), (int,float)) and math.isfinite(e['device_ms'])
            and math.isclose(e['device_ms'], (e['end_ns']-e['start_ns'])/1e6, rel_tol=1e-5),
            'invalid event duration')
    where = scope(e)
    require(where not in LAYERS or LAYERS[where][0] == rank, 'layer on wrong rank')
    require(where != 'draft' or rank == 1, 'draft on wrong rank')
    if row := BOUNDARIES.get(e['label']):
        require((rank,e.get('layer_boundary')) == row, 'invalid layer boundary')
    else:
        require(not e.get('layer_boundary'), 'unexpected layer boundary')
    require(where in LAYERS or where in ('draft', 'target_boundary', 'target_span'), 'unregistered sampled layer')


def read_events(root, sources, *, control=False):
    events = []
    for rank in (0,1):
        path = root/f'rank{rank}/sites.jsonl'
        require(path.is_file(), 'missing sites: '+str(path))
        sources[str(path)] = sha(path)
        seen = set()
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get('schema') != 'packet57.event.v1':
                continue
            require(not control, 'control arm contains instrumentation events')
            validate_event(row, rank)
            require(row['event'] not in seen, 'duplicate event')
            seen.add(row['event'])
            events.append(row)
    return events


def event_groups(events, cycles):
    groups = defaultdict(list)
    touched = set()
    for e in events:
        where = scope(e)
        # Speculative target p+1 belongs to cycle p; D and corrected target p to p.
        pos = e['position'] - int(e['speculative'] and where != 'draft')
        require(pos in cycles, 'event has no generated cycle')
        touched.add(pos)
        groups[(where,e['rank'],e['fixture'],e['position'],e['speculative'])].append(e)
    # Every sampled generated index must include complete draft and both target
    # layer types per rank; extra cancelled speculative prefixes are excluded.
    for fixture in range(9,17):
        for where in ('draft', *LAYERS):
            required = DRAFT_CLASSES if where == 'draft' else TARGET_CLASSES
            matching = [rows for (s,r,f,p,spec),rows in groups.items() if s==where and f==fixture]
            require(any(required <= {e["class"] for e in rows} and
                        (where=="draft" or any(e["label"]==where+".ffn.combine" for e in rows))
                        for rows in matching), "incomplete sampled operation: "+where+" fixture "+str(fixture))
    return groups, touched


def base_summarize(root):
    root = Path(root)
    controls = {p.parent.name:p for p in (root/'control').glob('*/receipt.json')}
    instruments = {p.parent.name:p for p in (root/'attribution').glob('*/receipt.json')}
    require(len(controls)==12 and controls.keys()==instruments.keys(), 'requires paired complete twelve-prompt screen')
    sources, pairs, selected_pairs, draft_pairs = {}, [], [], []
    by_class = defaultdict(list)
    excluded = defaultdict(int)
    boundaries = defaultdict(list)
    spans = defaultdict(list)
    excluded_spans = defaultdict(int)
    prompt_rows = {}
    for prompt in sorted(controls):
        cp, ip = controls[prompt], instruments[prompt]
        a, b = json.loads(cp.read_text()), json.loads(ip.read_text())
        for path, row, arm in ((cp,a,'control'),(ip,b,'attribution')):
            sources[str(path)] = sha(path)
            require(row.get('passed') is True and row.get('exact_oracle') is True and row.get('oracle_check',{}).get('passed') is True, 'failed target oracle')
            require(row.get('attribution_arm') == arm and row.get('cached_tokens') == 0
                    and row.get('output_tokens') == 128, 'requires cold 128-token arms')
            require(row.get('target_split') == [24,24], '24/24 selection required')
        for key in ('prompt_id','prompt_token_sha256','output_token_sha256','binary_sha256','selection_sha256'):
            require(a.get(key) and a.get(key)==b.get(key), 'arm identity/output mismatch: '+key)
        require(a['tokens']==b['tokens'] and len(a['tokens'])==128, 'paired output bytes differ')
        ac, bc = extract(a), extract(b)
        require(len(ac)==len(bc)==127, 'incomplete generated cycles')
        paired = {}
        for x,y in zip(ac,bc):
            require(x['position']==y['position'] and x['hit']==y['hit'], 'paired acceptance differs')
            paired[x['position']] = (x,y)
        read_events(cp.parent,sources,control=True)
        events = read_events(ip.parent,sources)
        groups,touched = event_groups(events,paired)
        half_status = {}
        for arm, path in (('control',cp),('attribution',ip)):
            for rank in (0,1):
                timing = path.parent/f'rank{rank}/timings.jsonl'
                require(timing.is_file(), 'missing half cancellation receipt')
                sources[str(timing)] = sha(timing)
                for line in timing.read_text().splitlines():
                    r=json.loads(line)
                    key=(arm,rank,r['position'],r['speculative'])
                    require(key not in half_status, 'duplicate half timing identity')
                    half_status[key]=r
        endpoints = defaultdict(lambda: defaultdict(list))
        for e in events:
            if e.get('layer_boundary'):
                endpoints[(e['rank'],e['position'],e['speculative'])][e['layer_boundary']].append(e)
        for (rank,pos,spec), ends in endpoints.items():
            key=(rank,spec)
            if not ends['begin'] or not ends['end']:
                excluded_spans[key] += 1
                continue
            for arm in ('control','attribution'):
                require((arm,rank,pos,spec) in half_status, 'boundary has no half timing receipt')
            if any(half_status[(arm,rank,pos,spec)]['cancelled'] for arm in ('control','attribution')):
                excluded_spans[key] += 1
                continue
            start=min(e['start_ns'] for e in ends['begin'])
            end=max(e['end_ns'] for e in ends['end'])
            require(end>start, 'reversed same-card layer span')
            c,i=paired[pos-int(spec)]
            metric='S_ms' if spec else 'A_ms' if rank==0 else 'B_ms'
            require(c[metric] is not None and i[metric] is not None, 'layer span missing half envelope')
            layer_us=(end-start)/1000
            spans[key].append(dict(control_half_us=c[metric]*1000,instrumented_half_us=i[metric]*1000,
                                  layer_span_us=layer_us,outside_us=i[metric]*1000-layer_us))
        pairs.extend(paired.values())
        selected_pairs.extend(paired[pos] for pos in sorted(touched))
        draft_positions = {e['position'] for e in events if scope(e)=='draft'}
        draft_pairs.extend(paired[pos] for pos in sorted(draft_positions))
        for (where,rank,fixture,position,spec), rows in groups.items():
            cls = {e['class'] for e in rows}
            if where in LAYERS:
                complete = TARGET_CLASSES <= cls and any(e['label']==where+'.ffn.combine' for e in rows)
                if not complete:
                    excluded[(rank,LAYERS[where][1],spec)] += 1
                    continue
                kind = LAYERS[where][1]
            elif where == 'draft':
                require(DRAFT_CLASSES <= cls, 'partial draft operation')
                kind = 'draft'
            elif where == 'target_span':
                continue
            else:
                for e in rows:
                    boundaries[(rank,e['class'])].append(e['device_ms']*1000)
                continue
            totals = defaultdict(float)
            for e in rows:
                totals[e['class']] += e['device_ms']*1000
            for cls,value in totals.items():
                by_class[(rank,kind,spec,cls)].append(value)
        prompt_rows[prompt] = dict(event_count=len(events), sampled_cycles=len(touched),
                                  control_output_sha256=a['output_token_sha256'])
    def paired_stats(rows, metric):
        result = {}
        for branch in ('all','hit','miss'):
            part = [(a,b) for a,b in rows if (branch=='all' or a['hit']==(branch=='hit'))
                    and a.get(metric) is not None and b.get(metric) is not None]
            c = stats([a[metric]*1000 for a,b in part]); i = stats([b[metric]*1000 for a,b in part])
            factor = c['median_us']/i['median_us'] if part and i['median_us']>0 else None
            result[branch] = dict(control=c,instrumented=i,control_over_instrumented=factor)
        return result
    cycle = paired_stats(selected_pairs,'cycle_ms')
    draft = paired_stats(draft_pairs,'D_wall_ms')
    require(all(cycle[k]['control']['count'] for k in ('hit','miss')), 'need sampled hit and miss coverage')
    factor = cycle['all']['control_over_instrumented']
    draft_factor = draft['all']['control_over_instrumented']
    require(factor and draft_factor, 'missing scaling control')
    classes, levers = [], []
    total_layer = defaultdict(float)
    for (rank,kind,spec,cls), values in sorted(by_class.items()):
        scale = draft_factor if kind=='draft' else factor
        row = dict(rank=rank,layer_type=kind,speculative=spec,category=cls,
                   measured=stats(values), estimated_scaled_mean_us=st.mean(values)*scale,
                   scale_factor=scale,scaled_is_measurement=False,
                   excluded_partial_layers=excluded[(rank,kind,spec)])
        classes.append(row)
        multiplicity = 1 if kind=='draft' else 18 if kind=='GDN' else 6
        if kind!='draft': total_layer[(rank,spec)] += st.mean(values)*multiplicity
        levers.append(dict(rank=rank,role='draft' if kind=='draft' else 'speculative_half' if spec else 'target_half',
            layer_type=kind,category=cls,estimated_cost_us=row['estimated_scaled_mean_us']*multiplicity,
            multiplicity=multiplicity,measured=False))
    halves = {name:paired_stats(selected_pairs,metric) for name,metric in
              [('rank0_speculative','S_ms'),('rank0_corrected','A_ms'),('rank1_target','B_ms')]}
    # A_ms=0 on hits is absence, not a zero-cost corrected half.
    halves['rank0_corrected'] = paired_stats([(a,b) for a,b in selected_pairs if not a['hit']],'A_ms')
    outside = []
    for rank,spec,name in ((0,True,'rank0_speculative'),(0,False,'rank0_corrected'),(1,False,'rank1_target')):
        values=spans[(rank,spec)]
        require(values, 'missing complete half/layer span: '+name)
        measured=stats([r['outside_us'] for r in values])
        remainder=measured['mean_us']*factor
        outside.append(dict(rank=rank,role=name,control_half_mean_us=st.mean(r['control_half_us'] for r in values),
            instrumented_half_mean_us=st.mean(r['instrumented_half_us'] for r in values),
            instrumented_layer_span=stats([r['layer_span_us'] for r in values]),
            instrumented_outside_layer=measured,estimated_scaled_outside_layer_us=remainder,
            negative_remainder=measured['min_us']<0,measured=True,
            excluded_partial_or_cancelled_spans=excluded_spans[(rank,spec)],
            definition='host half command duration minus same-card first-layer-start to last-layer-end GPU span; includes snapshot, preparation, head and handoff outside the layer region; not GPU idle'))
        levers.append(dict(rank=rank,role=name,layer_type='outside_layers',category='remainder',
                           estimated_cost_us=remainder,multiplicity=1,measured=False))
    levers.sort(key=lambda r:r['estimated_cost_us'],reverse=True)
    for n,row in enumerate(levers,1): row['rank_order']=n
    full = [b for a,b in selected_pairs if b.get('S_ms') is not None]
    return dict(schema='packet64.attribution.summary.v1',passed=True,diagnostic=True,
        submission_eligible=False,qualifying=False,sources=sources,prompts=prompt_rows,
        sampled_cycles=cycle,full_cycles=paired_stats(pairs,'cycle_ms'),draft_wall=draft,
        classes=classes,draft_breakdown=[r for r in classes if r['layer_type']=='draft'],
        rank_halves=halves,outside_layers=outside,ranked_levers=levers,
        rank_balance=dict(complete_cycles=len(full),rank0_finishes_last=sum(c['rank0_finishes_last'] for c in full),
                          rank1_finishes_last=sum(not c['rank0_finishes_last'] for c in full)),
        transfers=[dict(rank=r,category=c,event_duration=stats(v)) for (r,c),v in sorted(boundaries.items())],
        scaling='Target classes multiply paired sampled control/instrumented cycle median ratio; draft uses paired D-wall ratio. Estimates only.',
        limitations=['One loaded pair; fixed control-then-attribution order. No independent fresh-server speed verdict.',
            'Representative class totals extrapolate 18 GDN + 6 QSA per half; these are estimates, not measurements of every layer.',
            'Outside-layer duration subtracts a same-card layer span from its host half command duration. It is not GPU idle; scaled values are estimates and negative residuals remain visible.',
            'Class names follow surviving fused launch labels; mixed fused kernels cannot be split into original operator costs.',
            'Partial cancelled layers excluded from class means; rank0 corrected work occurs only on misses.',
            'Rank host times share the monotonic clock; GPU timestamps are never compared across cards.',
            'No prompt/KV/response reuse, but repeated full-suite control/observation is diagnostic only.',
            'Co-running lane A may affect costs; this is lever screening, never headline throughput.'])


def markdown(report):
    lines = ['# Packet64 in-engine attribution', '', 'Diagnostic only. All times below are microseconds.', '',
             '| Rank | Type | Speculative | Class | Measured mean / operation | Scaled estimate |',
             '| --- | --- | --- | --- | ---: | ---: |']
    for r in report['classes']:
        lines.append(f"| {r['rank']} | {r['layer_type']} | {r['speculative']} | {r['category']} | {r['measured']['mean_us']:.2f} | {r['estimated_scaled_mean_us']:.2f} |")
    lines += ['', '| Half | Control mean | Instrumented mean | Measured outside layers |', '| --- | ---: | ---: | ---: |']
    for r in report['outside_layers']:
        lines.append(f"| {r['role']} | {r['control_half_mean_us']:.2f} | {r['instrumented_half_mean_us']:.2f} | {r['instrumented_outside_layer']['mean_us']:.2f} |")
    lines += ['', 'Ranked cost buckets (overlapping roles; not additive savings):', '',
              '| Order | Rank / role | Type / class | Estimated cost |', '| ---: | --- | --- | ---: |']
    for r in report['ranked_levers']:
        lines.append(f"| {r['rank_order']} | {r['rank']} / {r['role']} | {r['layer_type']} / {r['category']} | {r['estimated_cost_us']:.2f} |")
    lines += ['', report['scaling'], '', *['- '+s for s in report['limitations']]]
    return '\n'.join(lines)+'\n'


_base_markdown=markdown
def summarize(root):
    from outside import breakdown
    result=base_summarize(root)
    result['rank1_outside_breakdown']=breakdown(root,result)
    return result

def markdown(report):
    text=_base_markdown(report)
    detail=report.get('rank1_outside_breakdown')
    if not detail:return text
    text+='\n## Rank 1 outside layers (raw measured microseconds)\n\n| Part | Mean |\n| --- | ---: |\n'
    for name,row in detail['measured'].items():text+=f"| {name} | {row['mean_us']:.3f} |\n"
    text+='\n| Part | Logical resident bytes | GB/s | 540–590 GB/s floor (µs) |\n| --- | ---: | ---: | ---: |\n'
    for name,row in detail['roofline'].items():text+=f"| {name} | {row['logical_bytes']} | {row['logical_GB_s']:.1f} | {row['floor_us_at_590']:.1f}–{row['floor_us_at_540']:.1f} |\n"
    return text+'\n'+'\n'.join(detail['limitations'])+'\n'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    report=summarize(args.run)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    args.output.with_suffix('.md').write_text(markdown(report))

if __name__=='__main__':main()
