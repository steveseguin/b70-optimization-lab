"""CPU-only attribution from retained receipts; no cross-device clock arithmetic."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import statistics as st

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
RUN = P.parent/'packet69-rank1-head/screen/attr/evidence/p69-attribution-B-a/run'
SOURCES = {}

def read(path, lines=False):
    raw = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return [json.loads(x) for x in raw.splitlines()] if lines else json.loads(raw)

def stats(xs):
    return dict(count=len(xs), mean_us=st.mean(xs), median_us=st.median(xs),
                min_us=min(xs), max_us=max(xs)) if xs else dict(count=0)

def adjacent_gaps(rows):
    """Only consecutive owned events: never call an unobserved span idle."""
    rows = sorted(rows, key=lambda x:x['event'])
    gaps = []
    for a,b in zip(rows, rows[1:]):
        if b['event'] != a['event']+1:
            continue
        assert a['rank']==b['rank']==1
        assert a['start_ns'] < a['end_ns'] <= b['start_ns'] < b['end_ns']
        gaps.append((b['start_ns']-a['end_ns'])/1000)
    return gaps

def host_rows(receipt, timings):
    trace = {r['position']:r for r in receipt['rank_trace']
             if r['rank']==1 and r['op']==1 and 9<=r['fixture']<=16}
    result = {}
    for t in timings:
        if not 9<=t['fixture']<=16:
            continue
        r=trace[t['position']]
        result[t['position']] = dict(
            fixture=t['fixture'], busy_us=r['busy_ms']*1000,
            envelope_us=(r['rank_completed']-r['rank_received'])*1e6,
            mailbox_arrival_us=(r['rank_received']-r['sent'])*1e6,
            outer_setup_us=(r['rank_completed']-r['rank_received'])*1e6-r['busy_ms']*1000,
            prepare_us=t['prepare_ms']*1000, enqueue_us=t['enqueue_loop_ms']*1000,
            wait_us=t['wait_ms']*1000, host_waits=t['host_waits'],
            host_unclocked_us=(r['busy_ms']-t['prepare_ms']-t['enqueue_loop_ms']-t['wait_ms'])*1000)
    assert len(result)==8
    return result

def main():
    rows=[]; host=defaultdict(lambda:defaultdict(list)); copies=defaultdict(int)
    for receipt_path in sorted((RUN/'attribution').glob('*/receipt.json')):
        prompt=receipt_path.parent.name
        arms={}
        for arm in ('control','attribution'):
            d=RUN/arm/prompt
            r=read(d/'receipt.json')
            assert r['passed'] and r['exact_oracle'] and r['cached_tokens']==0
            arms[arm]=host_rows(r,read(d/'rank1/timings.jsonl',True))
            for x in arms[arm].values():
                for k,v in x.items():
                    if k!='fixture':host[arm][k].append(v)
        events=read(receipt_path.parent/'rank1/sites.jsonl',True)
        for pos,h in arms['attribution'].items():
            es=[e for e in events if e.get('position')==pos and not e['label'].startswith('draft.')]
            for e in es:
                if 'transfer' in e['label']:
                    copies['count']+=1
                    copies['zero_duration']+=int(e['start_ns']==e['end_ns'])
                    copies['constant_223696213281']+=int(e['start_ns']==e['end_ns']==223696213281)
            kernels=[e for e in es if 'transfer' not in e['label']]
            begin=min(e['start_ns'] for e in kernels if e['label']=='blk.24.hc.a.norm')
            last=max(e['end_ns'] for e in kernels if e['label']=='blk.47.ffn.combine')
            outside=[e for e in kernels if e['label'].startswith('final.') or e['label'] in ('logits','argmax')]
            end=max(e['end_ns'] for e in outside)
            layers_us=(last-begin)/1000
            kernel_us=sum((e['end_ns']-e['start_ns'])/1000 for e in outside)
            tail_gap=(end-last)/1000-kernel_us
            assert tail_gap>=0
            boundary=[e for e in kernels if e['label']=='blk.47.ffn.combine']+outside
            assert abs(sum(adjacent_gaps(boundary))-tail_gap)<1e-6
            residual=h['envelope_us']-layers_us-kernel_us
            rows.append(dict(prompt=prompt,position=pos,fixture=h['fixture'],
                residual_us=residual,outside_gap_us=tail_gap,
                sampled_intralayer_gap_us=sum(sum(adjacent_gaps([e for e in kernels if e['label'].startswith(prefix)])) for prefix in ('blk.24.','blk.27.')),
                host_post_enqueue_unclocked_us=h['host_unclocked_us'],
                outer_setup_us=h['outer_setup_us'],
                remainder_us=residual-tail_gap-h['host_unclocked_us']-h['outer_setup_us']))
    assert len(rows)==96
    summary={k:stats([r[k] for r in rows]) for k in rows[0] if k.endswith('_us')}
    ancillary={}
    for packet in ('packet64-record-bundle','packet70-record-bundle'):
        root=P.parent/packet/'build/device-cards01-a/WS128'
        values=defaultdict(list); count=0
        # Completed WS128 only; no writes and no model payload reads.
        for path in sorted(root.rglob('timings.jsonl')):
            if path.parent.name!='rank1':continue
            for r in read(path,True):
                if not 9<=r.get('fixture',0)<=16:continue
                count+=1
                for key in ('prepare_ms','enqueue_loop_ms','wait_ms'):
                    values[key.removesuffix('_ms')+'_us'].append(r[key]*1000)
        ancillary[packet]=dict(halves=count,host={k:stats(v) for k,v in values.items()},
                              comparable_to_p69=False,reason='different build/selection; context only, not subtracted from p69')
    result=dict(schema='packet76.rank1-attribution.v1',device_executed=False,diagnostic=True,
        complete_causal_split=False,summary=summary,host={a:{k:stats(v) for k,v in d.items()} for a,d in host.items()},
        transfers=dict(copies),ancillary=ancillary,halves=rows,sources=SOURCES,
        missing=['per-event submit timestamp and host/device clock correlation',
                 'all-layer event coverage including consecutive layer boundaries',
                 'valid target transfer timestamps', 'separate retirement/profiling host timers'],
        buckets=dict(a='measured adjacent outside gap; sampled intralayer gaps reported separately, already inside layer span',
                     b='rank0 handover precedes rank1 command send; mailbox arrival precedes measured rank1 receive; neither is in the residual; H2D timing unresolved',
                     c='host enqueue measured but overlaps GPU execution; causal idle attribution unavailable',
                     d='host work outside prepare/enqueue/wait, outer setup, remaining unattributed boundary time'),
        decision='Screen ordered-queue event retirement on rank1. Largest identified bucket is host housekeeping, not an observed device-starvation gap. Retirement share and benefit remain hypotheses.')
    (P/'ATTRIBUTION.json').write_text(json.dumps(result,indent=2)+'\n')
    s={k:v['mean_us'] for k,v in summary.items()}
    text=f'''# Packet 76: rank 1 host residual

CPU analysis of 96 instrumented halves (12 prompts, fixtures 9–16). No GPU ran.
The original residual is **{s['residual_us']:.3f} µs**, not measured device idle.

| Additive accounting of the residual | Mean µs |
| --- | ---: |
| (a) Consecutive device gaps from final layer end through argmax | {s['outside_gap_us']:.3f} |
| (d) Host work outside prepare, enqueue and wait timers | {s['host_post_enqueue_unclocked_us']:.3f} |
| (d) Outer command setup, including ordered half-input submission | {s['outer_setup_us']:.3f} |
| (b/c/d) Unresolved boundary time | {s['remainder_us']:.3f} |

The host work bucket follows the enqueue loop in `rank.hpp`: drain reporting,
profiling queries, event retirement, result copies outside the wait timer,
resource accounting and timing output. It is accounting, not a function-level
profile. Preparation is effectively zero in these asynchronous draft halves.
Its matched uninstrumented control is **{st.mean(host['control']['host_unclocked_us']):.3f} µs**;
instrumentation adds **{st.mean(host['attribution']['host_unclocked_us'])-st.mean(host['control']['host_unclocked_us']):.3f} µs** in that bucket.
That difference is observation overhead, not an available production speedup.

(a) The two fully sampled layers have {s['sampled_intralayer_gap_us']:.3f} µs of
adjacent gaps in total. These are already inside the subtracted layer span and
are not additive to the residual. Events for intermediate layers are missing;
the large interval between sampled layers contains kernels and cannot be called
idle. No full-device idle or inter-layer-gap total can be recovered.

(b) Host receipt clocks put mailbox arrival at
{st.mean(host['attribution']['mailbox_arrival_us']):.3f} µs after send. This precedes
rank_received, so it is outside the measured half. The controller copies the
rank0 hidden state before sending the half request. Rank0 completion and handover
waiting must not be charged to this residual. All {copies['count']} sampled target
copy events report the same zero-width timestamp, 223696213281 ns, while compute
events use a very different range. These cannot establish transfer latency or
arrival on the compute timeline; zero duration does not prove a free transfer.
Controller `bounded_spin_iterations` is null, not a measured spin count.

(c) Rank1's instrumented host enqueue loop averages
{st.mean(host['attribution']['enqueue_us']):.3f} µs, and its control averages
{st.mean(host['control']['enqueue_us']):.3f} µs. This overlaps device work. No
per-kernel submit times or clock correlation were retained, so late host issue
cannot be separated from device scheduling. The 1.61 ms cannot honestly be
divided into four fully causal, nonoverlapping numbers using these receipts.

The JSON hashes every input, retains all 96 half calculations and reports
packet64/70 host timings separately. No GPU timestamps are compared across
cards or subtracted from host timestamps. No extrapolated timing is used.

## Selected screen

The largest identified bucket is host housekeeping. The existing retirement
path polls every event again after waiting for the tail, then synchronizes and
releases events. Screen a rank1-only ordered-queue retirement path: one terminal
completion check proves the ordered prefix, retaining error propagation,
synchronization and event release. Kernels, their order and arithmetic stay
unchanged. Add host timers for retirement and profiling to distinguish this
mechanism from instrumentation overhead in the next screen. Retirement's share
is not measured yet; neither a speedup nor full attribution is claimed.
'''
    (P/'ATTRIBUTION.md').write_text(text)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
