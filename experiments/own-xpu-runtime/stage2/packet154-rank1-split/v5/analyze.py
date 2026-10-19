"""Correlate two host-monotonic streams. Overlap is counted once, never GPU time."""
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

GROUPS = {
    'b_issue': 'b_half', 'b_completion': 'b_half',
    'target_tail_issue': 'merge_compute', 'prefix_pack': 'merge_compute',
    'merge_compute': 'merge_compute',
    'b_import': 'transport', 'hidden_export_issue': 'transport',
    'hidden_export_completion': 'transport', 'prefix_export': 'transport',
    'merge_import': 'transport', 'reply_publication': 'transport',
    'draft_issue': 'draft', 'draft_completion_host': 'draft',
    'draft_publication': 'draft', 'draft_completion_pending': 'draft_pending',
    'wait_rank0_command': 'wait_rank0', 'wait_rank0_suffix': 'wait_rank0',
    'merge_duplicate': 'replay', 'export_duplicate': 'replay', 'suffix_zero_wait': 'replay',
}
REQUIRED = {'b_issue', 'b_completion', 'b_import', 'target_tail_issue',
            'hidden_export_issue', 'hidden_export_completion', 'prefix_pack',
            'prefix_export', 'wait_rank0_suffix', 'merge_compute', 'merge_import',
            'draft_issue', 'draft_completion_pending', 'draft_completion_host',
            'draft_publication', 'reply_publication', 'wait_rank0_command'}
BUCKETS = sorted(set(GROUPS.values()) | {'unassigned'})


def demand(ok, reason):
    if not ok:
        raise ValueError(reason)


def stream(path, rank):
    demand(path.is_file(), f'missing rank{rank} timing stream')
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    rows = [r for r in rows if 'p154_segment' in r]
    demand(rows, f'empty rank{rank} scope stream')
    for r in rows:
        demand(r['rank'] == rank and all(math.isfinite(r[k]) for k in ('start','end','ms'))
               and r['start'] <= r['end'] and r['ms'] >= 0
               and abs((r['end']-r['start'])*1000-r['ms']) < .02,
               'invalid scope clock')
        demand(type(r['sequence']) is int and type(r['op']) is int, 'missing command identity')
    return rows


def overlap(wait, scopes):
    """Partition interval endpoints, deepest host scope first; pending is fallback.

    A pending device event covers queue residence and host polling delay, not
    isolated device compute. It remains a separate bucket and cannot select a
    draft optimization by itself.
    """
    start, end = wait['start'], wait['end']
    active = [r for r in scopes if r['p154_segment'] in GROUPS
              and r['start'] < end and r['end'] > start]
    edges = sorted({start,end,*[max(start,r['start']) for r in active],
                              *[min(end,r['end']) for r in active]})
    out = dict.fromkeys(BUCKETS,0.)
    for a,b in zip(edges,edges[1:]):
        covering = [r for r in active if r['start'] <= a and r['end'] >= b]
        if covering:
            # Prefer real host activity over asynchronous pending residence.
            r = min(covering,key=lambda r:(r['p154_segment']=='draft_completion_pending',
                                           r['end']-r['start']))
            key = GROUPS[r['p154_segment']]
        else:
            key = 'unassigned'
        out[key] += (b-a)*1000
    demand(abs(sum(out.values())-(end-start)*1000)<.001,'overlap conservation')
    return out


def request_split(root, request):
    stamps=request['token_timestamps']
    demand(len(stamps)==64 and all(math.isfinite(x) for x in stamps)
           and all(b>a for a,b in zip(stamps,stamps[1:])), '64 monotone timestamps required')
    folder=root/request['prompt_id']
    r0=stream(folder/'rank0/timings.jsonl',0)
    r1=stream(folder/'rank1/timings.jsonl',1)
    demand(REQUIRED <= {r['p154_segment'] for r in r1}, 'incomplete rank1 scope census')
    waits=[r for r in r0 if r['p154_segment']=='remote_reply_wait'
           and stamps[0]<=r['start']<=r['end']<=stamps[-1]]
    demand(waits,'no complete remote reply waits')
    commands={(r['sequence'],r['op']) for r in r1 if r['p154_segment']=='command'}
    demand(all((r['sequence'],r['op']) in commands for r in waits),'unmatched remote command')
    cycles=[];total=dict.fromkeys(BUCKETS,0.)
    for w in waits:
        parts=overlap(w,r1)
        for k,n in parts.items():total[k]+=n
        cycles.append(dict(sequence=w['sequence'],op=w['op'],position=w['position'],
                           start=w['start'],end=w['end'],wait_ms=(w['end']-w['start'])*1000,
                           rank1_overlap_ms=parts))
    scope_totals=defaultdict(float)
    for r in r1:
        if stamps[0]<=r['start']<=r['end']<=stamps[-1]:scope_totals[r['p154_segment']]+=r['ms']
    return dict(prompt_id=request['prompt_id'],interval_count=63,waits=cycles,
                remote_reply_wait_ms_per_cycle=sum(total.values())/63,
                overlap_ms_per_cycle={k:n/63 for k,n in total.items()},
                rank1_scope_ms_per_cycle={k:n/63 for k,n in scope_totals.items()},
                boundary_excluded_waits=sum(r['p154_segment']=='remote_reply_wait' for r in r0)-len(waits))


def analyze(views, synthetic=False, smoke=False):
    if synthetic:
        return dict(status='synthetic wiring only; scope proof separately required',
                    device_evidence=False,speed_evidence_eligible=False)
    expected=['candidate'] if smoke else ['control','candidate','control','candidate','control']
    demand([v['choice'] for v in views]==expected,'complete smoke or C/X/C/X/C required')
    rows=[]
    for v in views:
        demand(len(v['requests'])==12,'all twelve prompts required')
        req=[request_split(Path(v['output']),r) for r in v['requests']]
        rows.append(dict(index=v['index'],choice=v['choice'],requests=req,
                         overlap_ms_per_cycle={k:statistics.median(r['overlap_ms_per_cycle'][k] for r in req) for k in BUCKETS},
                         rank1_scope_ms_per_cycle={k:statistics.median(r['rank1_scope_ms_per_cycle'].get(k,0.) for r in req) for k in sorted(set(GROUPS))},
                         remote_reply_wait_ms_per_cycle=statistics.median(r['remote_reply_wait_ms_per_cycle'] for r in req)))
    controls=[r for r in rows if r['choice']=='control']
    decision='smoke proves streams only'
    if controls:
        # A majority must hold in every control; partial/pending residence cannot vote.
        def majority(keys):
            return all(sum(r['overlap_ms_per_cycle'][k] for k in keys) > r['remote_reply_wait_ms_per_cycle']/2 for r in controls)
        if majority(['draft']):decision='packet152 draft brief: confirmed draft host issue/completion/publication'
        elif majority(['b_half','merge_compute']):decision='B-half issue/completion or prefix/merge compute; no transport-only build'
        elif majority(['transport']):decision='packet152 merge brief: transfer/publication path'
        else:decision='mixed, pending device residence, rank0 dependency or unassigned; no mechanism selected'
    scope_summary={}
    if controls:
        for name in sorted(GROUPS):
            values=[r['rank1_scope_ms_per_cycle'][name] for r in controls]
            scope_summary[name]=dict(control_median_ms_per_cycle=statistics.median(values),
                control_range_ms=max(values)-min(values),
                replay_minus_skip_ms_per_cycle=[r['rank1_scope_ms_per_cycle'][name]-statistics.mean(values)
                    for r in rows if r['choice']=='candidate'],removable=False)
    return dict(schema='packet154.rank1-split.v1',scope_summary=scope_summary,device_evidence=True,
                speed_evidence_eligible=False,removable_segments=[],views=rows,decision=decision,
                clock='same-host steady monotonic; exact command sequence and op join',
                limitation='Host submission/completion intervals include queue and polling delay. Pending draft is not GPU compute. Medians of components are not additive. No wait is removable by observation.')


if __name__=='__main__':
    import argparse,resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);a=ap.parse_args()
    proof=json.loads((a.output/'run/bracket-inputs.json').read_text())
    print(json.dumps(analyze(proof['views'],smoke=proof['kind']=='smoke'),indent=2))
