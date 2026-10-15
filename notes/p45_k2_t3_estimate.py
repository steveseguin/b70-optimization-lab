"""Read-only T3 census; python3 -B. Metadata/receipts only; JSON to stdout.

M=3 forecasts are scenarios, not device measurements. The audit hook forbids
writes (including import caches) and subprocesses after imports.
"""
import collections
import gzip
import hashlib
import json
import statistics as st
import sys
from pathlib import Path
import p45_roofline_structural_analyze as roof

P = roof.P
inputs = {}


def read(p):
    b = p.read_bytes()
    inputs[str(p.relative_to(roof.ROOT))] = hashlib.sha256(b).hexdigest()
    return b


def load(p):
    return json.loads(read(p))


def census(root):
    files = sorted((root/'run/repeat-1').glob('*/receipt.json'))
    if not files:
        files = [root/'run/receipt.json']
    groups = collections.defaultdict(list)
    gaps = []; residuals = []; triples = []; prompt_lengths = []; prefill_bytes = 0; route_hashes = 0
    for f in files:
        r = load(f)
        prompt_lengths.append(r['prompt_tokens'])
        traces = {}
        for rank in (0, 1):
            pf = f.parent/f'rank{rank}/prefill-timings.jsonl'
            if pf.exists():
                prefill_bytes += len(read(pf))
            ts = [t for t in r['rank_trace'] if t['rank']==rank and t['op']==1]
            xs = [json.loads(x) for x in read(f.parent/f'rank{rank}/timings.jsonl').splitlines()]
            assert len(ts) == len(xs)
            for t,x in zip(ts,xs):
                assert (t['position'],t['fixture'],t['speculative']) == (x['position'],x['fixture'],x['speculative'])
                if x['cancelled']: continue
                kind = 'prompt' if t['fixture']==0 else 'spec' if t['speculative'] else 'decode'
                if kind != 'prompt' and t['position']<100: continue
                groups[f'r{rank}-{kind}'].append(dict(
                    forward=sum(x[k] for k in ('prepare_ms','enqueue_loop_ms','wait_ms')),
                    command=1000*(t['rank_completed']-t['rank_received']),
                    launches=x['launches_issued']))
                if kind=='prompt': traces[rank,t['position']]=t
        for (rank,pos),t in traces.items():
            if rank==1:
                gaps.append(1000*(t['rank_received']-traces[0,pos]['rank_completed']))
                prerequisites=[z['rank_completed'] for z in r['rank_trace'] if z['rank']==1 and z['rank_completed']<=t['rank_received']]
                ready=max([traces[0,pos]['rank_completed']]+prerequisites)
                residuals.append(1000*(t['rank_received']-ready))
                if pos>=16 and (1,pos+2) in traces:
                    triples.append(1000*(traces[1,pos+2]['rank_completed']-traces[0,pos]['rank_received']))
        archive=f.parent/'state-evidence.json.gz'
        if archive.exists():
            a=json.loads(gzip.decompress(read(archive)))
            route_hashes += sum(x['path'].endswith('.routes.bin') for x in a['files'])
    return dict(requests=len(files),prompt_lengths=prompt_lengths,prefill_file_bytes=prefill_bytes,
                retained_route_hash_entries=route_hashes,prompt_handoff_median_ms=st.median(gaps),
                ready_to_half_median_ms=st.median(residuals),
                prompt_three_row_span_median_ms=st.median(triples),
                groups={k:dict(n=len(v),**{field:st.median(x[field] for x in v) for field in v[0]}) for k,v in groups.items()})


def main():
    probe=load(P/'build/k2probe-c4096-dr1-s23-cards01-gpu/k2-acceptance.json')['all']
    p=probe['p_g1']; q=probe['p_g2_given_g1']; d=probe['first_drafter_ms_median']+probe['extra_drafter_ms_median']
    tokens=1+p+p*q
    runs={}
    for speed in (6,7):
        for cards in ('01','23'):
            for window in ('WS','WS128'):
                path=P/f'build/speed{speed}-c4096-dr1-s23-cards{cards}-gpu/{window}'
                if (path/'window.json').exists(): runs[f's{speed}-{cards}-{window}']=census(path)
    runs['s7-01-W2m']=census(P/'build/speed7-c4096-dr1-s23-cards01-gpu/W2m')
    k2=load(P/'build/speed7-c4096-dr1-s23-cards01-gpu/K2/run0/summary.json')
    timings={}
    for name in ('gemv:gdn.qkv','gemv:logits','gemv:expsgate','gemv:expsdown',
                 'fusion:p39.expert-checks-iq2','fusion:p39.expert-checks-iq3',
                 'fusion:p39.down-status','fusion:small.ffn'):
        c=k2['classes'].get(name)
        if not c: continue
        comp=c['comparisons'][c['selected_comparison'] or next(iter(c['comparisons']))]
        variant='specialised' if c['selected_comparison'] else 'packet18'
        timings[name]=dict(selected=c['selected'],
            workloads={k:v['variants'][variant]['execution_sum']['median_ns']/1e6 for k,v in comp['workloads'].items()},
            aggregate_ms=comp['variants'][variant]['execution_sum']['median_ns']/1e6,
            reread_aggregate_ms=(comp['reread'][variant]['execution_sum']['median_ns']/1e6
                                 if comp.get('reread') else None))
    target,draft=roof.weights()
    dense=[r['bytes']-r['classes']['routed_experts']['bytes'] for r in target]
    uni=512*(1-(1-10/512)**3)
    assert 10 <= uni <= 30
    scenarios=[]
    for key,r in runs.items():
        if not key.endswith('WS128'): continue
        a=r['groups']['r0-decode']['command']; b=r['groups']['r1-decode']['command']; h=r['ready_to_half_median_ms']
        # Three rows, in order on each card, with the rank0->rank1 transfer.
        done0=0.; done1=0.
        for _ in range(3):
            done0+=a; done1=max(done0+h,done1)+b
        scenarios.append(dict(run=key,A=a,B=b,handoff=h,T3=done1,
                              tok_s=1000*tokens/(done1+d),
                              ideal_draft_overlap_tok_s=1000*tokens/done1))
    sensitivity=[]
    base=scenarios[0]
    early=base['A']+base['handoff']+base['B']+(tokens-1)*max(base['A'],base['B'])
    for union in (10,20,uni,30):
        # Optimistic bandwidth-only subtraction from THREE SERIAL forwards:
        # removes every duplicate dense/expert byte read, but not dot products.
        expert=[r['classes']['routed_experts']['bytes'] for r in target]
        removed=[2*dense[i]+(3-union/10)*expert[i] for i in (0,1)]
        rank_ms=[3*base[k]-removed[i]/600e6 for i,k in enumerate(('A','B'))]
        t=sum(rank_ms)+base['handoff']
        sensitivity.append(dict(union3=union,rank_ms=rank_ms,T3=t,tok_s=1000*tokens/(t+d)))
    print(json.dumps(dict(runs=runs,K2_M1_workload_ms=timings,
        dense_bytes=dense,target=target,independent_uniform_union3=uni,
        tokens=tokens,drafter_ms=d,break_even_T3=1000*tokens/39.422009-d,
        streaming=scenarios,perfect_weight_reuse_serial_scenarios=sensitivity,
        ideal_early_exit=dict(expected_verifier_ms=early,tok_s=1000*tokens/(early+d),
                             ideal_draft_overlap_tok_s=1000*tokens/early),
        forecast_sensitivity=[dict(T3=t,tok_s=1000*tokens/(t+d),
                                  ideal_overlap_tok_s=1000*tokens/t) for t in (48,52.903278588543984,60,72,76,95,111.4)],
        input_digest=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest(),
        input_files=len(inputs),roof_input_files=roof.INPUTS),indent=2))


if __name__=='__main__': main()
