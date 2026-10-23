"""Preregistered host-boundary attribution; never a performance promotion.

Packet191 variants (all un-split head, all with a boundary command every cycle, head scopes ABSENT, boundary scopes
`boundary_total`/`boundary_body` MANDATORY): `v3` (record selection, rank 0 runs 24-25), `v3k` (k3 storage run as V3),
`k3x`, `k3trims`, `k3x-off` and `k3x-on` (rank 0 runs 24-26; rank0_prepare=async stages rank 0's inputs inside
`token_prep`, so the separate `token_history` readback scope is ABSENT there and MANDATORY elsewhere). An absent stream
is never a zero. The host-scope split is the same for sites off and on (the instrumentation is inside layer_body).

Use only complete scopes inside timestamps 1..64, excluding prefill and the
incident request. Sum each scope over those 63 cycles, then median prompts.
Replay-minus-skip estimates incremental duplicate service, not safe removal.
"""
import json
import math
import statistics
from pathlib import Path

SEGMENTS = {
    'token_prep': ('token_prep', 'token_history'),
    'capture_snapshot': ('snapshot', 'accept', 'rollback'),
    'suffix_head': ('suffix_head',),
    'merge_handoff_waits': ('head_hidden_wait', 'head_import', 'head_export',
                            'handoff_export', 'handoff_host', 'remote_reply_wait'),
    'draft_wait': ('draft_wait',),
    'v3_boundary': ('boundary_total',),
}
REPLAYS = {'token_prep': 'token_prep_duplicate',
           'capture_snapshot': 'snapshot_duplicate',
           'suffix_head': 'suffix_duplicate',
           'merge_handoff_waits': 'head_zero_wait',
           'draft_wait': 'draft_zero_wait'}
THRESHOLD_MS = 0.4


def demand(value, reason):
    if not value:
        raise ValueError(reason)


BOUNDARY = {'boundary_total', 'boundary_body'}
HEAD_ONLY = {'suffix_head','head_service_total','head_hidden_wait','head_import','head_export','suffix_duplicate','head_zero_wait'}


STAGED = {'k3trims', 'k3x', 'k3x-off', 'k3x-on'}  # rank0_prepare=async: token_history captured by an ordered copy inside token_prep


def request_split(root, request, variant='v3'):
    split = False
    native_path = root / request['prompt_id'] / 'native-result.json'
    native = json.loads(native_path.read_text()) if native_path.exists() else request
    stamps = request['token_timestamps']
    demand(len(stamps) in (64,128) and all(math.isfinite(x) for x in stamps)
           and all(b > a for a, b in zip(stamps, stamps[1:])), '64/128 monotone timestamps required')
    stamps=stamps[:100]
    intervals=len(stamps)-1
    clock = root / request['prompt_id'] / 'rank0/timings.jsonl'
    demand(clock.is_file(), 'missing rank0 timing receipt')
    records = [json.loads(line) for line in clock.read_text().splitlines() if line.strip()]
    samples = [r for r in records if 'p150_segment' in r]
    demand(samples, 'missing packet150 scopes; old traces cannot answer this split')
    demand(all(r['rank'] == 0 and math.isfinite(r['ms']) and r['ms'] >= 0
               and r['start'] <= r['end'] for r in samples), 'invalid scope clock')
    measured = [r for r in samples if stamps[0] <= r['start'] <= r['end'] <= stamps[-1]]
    totals = {}
    for r in measured:
        name = r['p150_segment']
        totals[name] = totals.get(name, 0.) + r['ms']
    demand(all(any(r['p150_segment'] == n for r in samples)
               for n in ('token_prep', 'snapshot', 'draft_wait', 'remote_reply_wait') + (('suffix_head',) if split else ())),
           'incomplete scope census')
    mandatory={'token_prep','snapshot','draft_wait',
               'remote_reply_wait','half_total','layer_body','handoff_export','handoff_host'}|BOUNDARY
    demand(variant in ('v3','v3k','k3x','k3trims','k3x-off','k3x-on'),'packet191 variant required')
    if variant in STAGED:demand(not any(r['p150_segment']=='token_history' for r in samples),'staged view recorded a synchronous token_history readback')
    else:mandatory.add('token_history')
    demand(not any(r['p150_segment'] in HEAD_ONLY for r in samples),'un-split view recorded a rank-0 head service')
    demand(sum(r['p150_segment']=='boundary_total' for r in measured)>=intervals-1,'every packet189 view must run the boundary every cycle')
    demand(mandatory <= {r['p150_segment'] for r in measured},'missing measured comparison scope')
    guessed=native.get('guess_rows',[])
    if any(g['hit'] for g in guessed):demand(any(r['p150_segment']=='accept' for r in samples),'missing accept scope')
    if any(not g['hit'] for g in guessed):demand(any(r['p150_segment']=='rollback' for r in samples),'missing rollback scope')
    # Snapshot includes its duplicate internally. Subtract this nested scope
    # before combining disjoint original-work segments; retain both raw values.
    original = dict(totals)
    def exclusive(parent, children):
        value = 0.
        for scope in measured:
            if scope['p150_segment'] != parent:
                continue
            nested = sum(r['ms'] for r in samples if r['p150_segment'] in children
                         and scope['start'] <= r['start'] <= r['end'] <= scope['end'])
            demand(nested <= scope['ms'] + 0.01, 'nested clocks exceed parent')
            value += max(0., scope['ms']-nested)
        return value
    original['snapshot'] = exclusive('snapshot', {'snapshot_duplicate'})
    half_other = exclusive('half_total', {'layer_body', 'snapshot', 'token_prep',
                                          'token_history', 'handoff_export', 'token_prep_duplicate'})
    head_other = exclusive('head_service_total', {'suffix_head', 'suffix_duplicate', 'head_import',
                                                 'head_export', 'head_hidden_wait', 'head_zero_wait'})
    boundary_ms=sum(r['ms'] for r in measured if r['p150_segment']=='boundary_total')/intervals
    return dict(prompt_id=request['prompt_id'], interval_count=intervals, split_head=bool(split), variant=variant, boundary_ms_per_cycle=boundary_ms,
                first_timestamp=stamps[0], last_timestamp=stamps[-1],
                complete_scopes=len(measured), boundary_or_prefill_scopes=len(samples)-len(measured),
                segments_ms_per_cycle={k: sum(original.get(n, 0.) for n in names)/intervals
                                       for k, names in SEGMENTS.items()},
                replay_ms_per_cycle={k: totals.get(n, 0.)/intervals for k, n in REPLAYS.items()},
                other_outside_ms_per_cycle=(half_other+head_other)/intervals,
                residual_definition='exclusive half setup/finalization/report plus suffix setup/publication',
                raw_scope_totals_ms=totals,
                cancelled_halves=sum(bool(r.get('cancelled')) for r in records
                                     if 'p150_segment' not in r and r.get('fixture', 0) > 0),
                hits=native.get('stats', {}).get('hits', request.get('hits')),
                misses=native.get('stats', {}).get('misses', request.get('misses')))


def data_proof(root, request, variant='v3'):
    # Every stream used by the comparison is mandatory, including native miss
    # traces and both rank clocks. Do not turn an absent stream into a zero.
    name=request['prompt_id'];dest=Path(root)/name
    for rank in (0,1):
        path=dest/f'rank{rank}/timings.jsonl'
        demand(path.is_file() and path.stat().st_size>0,'missing rank timing stream: '+str(path))
        rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        demand(any('half_completion_ms' in x and x.get('fixture',0)>0 for x in rows),'missing HALF timing records')
    native_path=dest/'native-result.json'
    native=json.loads(native_path.read_text()) if native_path.is_file() else request
    demand('rank_trace' in native and 'guess_rows' in native,'missing native correction stream')
    demand(native['rank_trace'] and native['guess_rows'],'empty native correction stream')
    from timing_report import summarize
    v=dict(index=0,choice='candidate' if variant=='k3trims' else 'control',output=str(root),requests=[request])
    timing=summarize(Path(root),[v])
    demand(timing['views'][0]['status']=='measured','unmeasured native correction stream')
    scopes=request_split(Path(root),request,variant)
    return dict(passed=True,host_scopes=scopes,correction_stream=timing,device_evidence=True)

def first_minute_proof(root, request, started, variant='v3'):
    import time
    row=dict(request,prompt_id='incident64')
    proof=data_proof(root,row,variant)
    proof['seconds_after_view_start']=(time.time_ns()-started)/1e9
    # Run on the first completed request; cold prefill or a freeze may take
    # longer than a minute. Elapsed wall time is diagnostic, never admission.
    (Path(root)/'first-minute-data-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

def analyze(views, synthetic=False, variants=None):
    if synthetic:return dict(passed=True,status='synthetic report wiring only',device_evidence=False)
    demand(variants is not None and len(variants)==len(views),'packet189 analysis needs the variant of every view')
    rows=[]
    for v,variant in zip(views,variants):
        proof=json.loads((Path(v['output'])/'first-minute-data-proof.json').read_text())
        demand(proof['passed'],'first-request data proof absent/failed')
        requests=[data_proof(Path(v['output']),r,variant)['host_scopes'] for r in v['requests']]
        rows.append(dict(index=v['index'],choice=v['choice'],variant=variant,requests=requests,
            segments_ms_per_cycle={k:statistics.median(r['segments_ms_per_cycle'][k] for r in requests) for k in SEGMENTS}))
    if len(rows)==1:
        demand(rows[0]['variant'] in ('v3','k3x','k3trims','k3x-on'),'packet191 single-view row is a fresh V3 control or the k3x-on smoke')
        return dict(passed=True,schema='packet191.host-boundary.v1',status='single-view row: timing data complete',views=rows,device_evidence=True,
            clock='host scopes; async snapshot copy is not isolated GPU latency',rate_scope='first 100 events / 99 intervals')
    controls=[r for r in rows if r['choice']=='control'];candidates=[r for r in rows if r['choice']=='candidate']
    demand(len(controls)==3 and len(candidates)==2 and [r['variant'] for r in rows]==['k3x-off','k3x-on','k3x-off','k3x-on','k3x-off'],'complete off/on/off/on/off (sites) required')
    decisions=[]
    for segment in SEGMENTS:
        values=[r['segments_ms_per_cycle'][segment] for r in controls]
        decisions.append(dict(segment=segment,control_ms_per_cycle=values,
            candidate_ms_per_cycle=[r['segments_ms_per_cycle'][segment] for r in candidates],
            saved_ms_per_cycle=[statistics.median(values)-r['segments_ms_per_cycle'][segment] for r in candidates],
            control_range_ms=max(values)-min(values)))
    return dict(passed=True,schema='packet191.host-boundary.v1',views=rows,decisions=decisions,
        device_evidence=True,clock='host scopes; async snapshot copy is not isolated GPU latency',
        rate_scope='first 100 events / 99 intervals for 128-token views; smoke 64/63',speed_evidence_eligible=False)

if __name__=='__main__':
    import argparse,resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);a=ap.parse_args()
    proof=json.loads((a.output/'run/bracket-inputs.json').read_text())
    variants=[Path(v).parent.name for v in proof.get('selections',[])] or None
    print(json.dumps(analyze(proof['views'],variants=variants),indent=2))
