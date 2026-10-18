"""Measured per-site limiter bounds. Never a speed/quality qualification."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
from policy import VIEWS, NONEXACT, labels, classify
from summarize import read_events, require
from timeline import sha
P=Path(__file__).resolve().parent
LIMITATIONS=[
 'diagnostic_nonexact: true. Changed outputs, activations, routing and acceptance confound model-level comparisons.',
 'Per-half estimates multiply measured call medians by 18 GDN or 6 QSA occurrences; unsampled layers are not measured.',
 'Rank0 speculative and corrected work are separate. Missing corrected samples remain missing, never interpolated.',
 'Nodeq retains arithmetic reductions, activation loads and stores: a raw-byte surrogate floor, not a pure DRAM-copy floor.',
 'Volatile global reads retain otherwise dead weight operands. Loadkeep controls quantify changed load lowering.',
 'constgrid changes IQ2_S gate/up only; IQ4_NL down is a negative control for this mechanism.',
 'onecached maps all selected slots to expert 0 within each layer. Cache residency is a hypothesis: intervening layers may evict it; no DRAM counters were collected.',
 'Deltas are signed, non-additive ablation bounds. Achievable LOSSLESS savings remain unmeasured until a real implementation passes quality and repeat gates.',
 'Ranks overlap; do not sum half deltas or turn them into tok/s. No bundle, chain, submission or headline is eligible.'
]

def aggregate_events(requests):
    """Sum a site's stages per complete layer call, median within prompt, then across prompts."""
    samples=defaultdict(lambda:defaultdict(list))
    for prompt,events in requests:
        groups=defaultdict(list)
        for e in events:
            if e['label'].startswith(('blk.22.','blk.23.','blk.24.','blk.27.')):
                groups[e['rank'],e['fixture'],e['position'],e['speculative'],int(e['label'].split('.')[1])].append(e)
        for (rank,fixture,position,spec,layer),rows in groups.items():
            if not any(e['label']==f'blk.{layer}.ffn.combine' for e in rows):continue
            bysite=defaultdict(float)
            for e in rows:bysite['.'.join(e['label'].split('.')[2:])]+=(e['end_ns']-e['start_ns'])/1e6
            for site,ms in bysite.items():
                require(ms>0,'nonpositive compute site')
                samples[rank,'speculative' if spec else 'corrected',layer,site][prompt].append(ms)
    rows=[]
    for (rank,path,layer,site),prompts in sorted(samples.items()):
        med=statistics.median(statistics.median(v) for v in prompts.values())
        occurrences=6 if layer%4==3 else 18
        rows.append(dict(rank=rank,path=path,layer=layer,site=site,call_ms=med,
                         estimated_ms_per_half=med*occurrences,occurrences=occurrences,
                         prompts=len(prompts),calls=sum(map(len,prompts.values()))))
    require({r['rank'] for r in rows}=={0,1},'no complete sampled layer calls for both ranks')
    return rows

def view_report(output):
    output=Path(output);identity=json.loads((output/'identity.json').read_text())
    view=Path(identity['lineage']).name
    from run_screen import expected_quality_refusal
    window=json.loads((output/'window.json').read_text())
    require(window.get('device_complete') is True and window.get('lease_released') is True,'report requires safe device completion and released lane')
    require(json.loads((output/'run/teardown.json').read_text()).get('drained') is True,'report requires completed drain')
    if window.get('passed') is not True:
        failure=json.loads((output/'report-failure.json').read_text())
        require(expected_quality_refusal(view,window,failure),'not an expected diagnostic quality refusal')
    safety=json.loads((output/'run/report-inputs.json').read_text())
    require(safety.get('passed') is True and safety.get('device_isolation',{}).get('passed') is True,'report requires safety/isolation proof')
    seal=Path(identity['seal']);require(sha(seal)==identity['seal_sha256'],'seal identity changed')
    require(json.loads(seal.read_text()).get('diagnostic_nonexact') is True,'not diagnostic seal')
    require(sha(Path(identity['binary']))==identity['binary_sha256'],'binary changed')
    require(sha(Path(identity['lineage'])/'selection.json')==identity['selection_sha256'],'selection changed')
    proof=json.loads((output/'run/paired-inputs.json').read_text())
    require(proof['passed'] and proof['view']==view and proof['diagnostic_nonexact'],'invalid paired evidence')
    sources={str(output/n):sha(output/n) for n in ('identity.json','window.json','run/teardown.json','run/report-inputs.json','run/paired-inputs.json')}
    if (output/'report-failure.json').exists():sources[str(output/'report-failure.json')]=sha(output/'report-failure.json')
    requests=[];outcomes=[];prompt_sets=[]
    from run_screen import screen
    from common import D
    ids=list(D.CHECK.PROMPT_IDS)
    for arm in ('control','attribution'):
        require([r['prompt_id'] for r in proof['arms'][arm]]==ids,'full ordered prompt suite required')
        for row in proof['arms'][arm]:
            d=output/'run'/arm/row['prompt_id'];receipt=d/'receipt.json'
            require(json.loads(receipt.read_text())==row,'paired/retained receipt differs')
            require(row['binary_sha256']==identity['binary_sha256'] and row['selection_sha256']==identity['selection_sha256'], 'mixed runtime identity')
            require(row.get('passed') is True and row.get('diagnostic_nonexact') is True,'failed/unlabelled row')
            oracle=D.CHECK.token_record(D.ORACLE/'results'/row['prompt_id'])
            compared=classify(view,row['tokens'],oracle,128)
            require(compared['exact_oracle']==row['exact_oracle'],'incorrect exactness label')
            sources[str(receipt)]=sha(receipt)
            events=read_events(d,sources,control=arm=='control')
            if arm=='attribution':requests.append((row['prompt_id'],events));outcomes.append(compared)
        prompt_sets.append([(r['prompt_id'],r['prompt_token_sha256']) for r in proof['arms'][arm]])
    require(prompt_sets[0]==prompt_sets[1],'paired input identities differ')
    return dict(schema='packet86.limiter-view.v1',passed=True,**labels(view),
                lane=identity['lane'],binary_sha256=identity['binary_sha256'],selection_sha256=identity['selection_sha256'],
                seal_sha256=identity['seal_sha256'],prompt_identity=prompt_sets[0],sites=aggregate_events(requests),
                outcomes=outcomes,sources=sources,limitations=LIMITATIONS)

def compare(reports):
    require(set(reports)==set(VIEWS),'all views including load-retention controls required')
    base=reports['production'];require(all(r['lane']==base['lane'] and r['binary_sha256']==base['binary_sha256'] and r['prompt_identity']==base['prompt_identity'] for r in reports.values()),'mixed lane/binary/input identity')
    table=[];totals=defaultdict(dict)
    for name,report in reports.items():
        require(report['passed'] and report['diagnostic_nonexact'],'invalid diagnostic view')
        grouped=defaultdict(list)
        for row in report['sites']:grouped[row['rank'],row['path'],row['site']].append(row)
        for (rank,path,site),rows in grouped.items():
            # Missing a sampled layer must never masquerade as a lower half cost.
            layers={r['layer'] for r in rows};required={22,23} if rank==0 else {24,27}
            ms=sum(r['estimated_ms_per_half'] for r in rows) if layers==required else None
            table.append(dict(view=name,rank=rank,path=path,site=site,estimated_ms_per_half=ms,sampled_layers=sorted(layers)))
            totals[rank,path,site][name]=ms
    budgets=[]
    mechanisms=[('byte_read_surrogate','exp-loadkeep','exp-nodeq'),('IQ2_grid_and_sign','exp-loadkeep','exp-constgrid'),
                ('remaining_dequant','exp-constgrid','exp-nodeq'),('repeated_expert_cache_hypothesis','production','exp-onecached'),
                ('HC_dequant','hc-loadkeep','hc-nodeq'),('HC_scale','hc-loadkeep','hc-constscale'),
                ('expert_load_lowering_control','production','exp-loadkeep'),('HC_load_lowering_control','production','hc-loadkeep')]
    for (rank,path,site),values in sorted(totals.items()):
        for mechanism,a,b in mechanisms:
            is_hc=site in ('hc.a.gate','hc.f.gate');is_expert=site in ('ffn.expert_gate_up','ffn.expert_down') or site in ('expsgate','expsdown')
            if ('HC' in mechanism and not is_hc) or ('HC' not in mechanism and not is_expert):continue
            av,bv=values.get(a),values.get(b);delta=av-bv if av is not None and bv is not None else None
            if mechanism=='IQ2_grid_and_sign' and site!='expsgate':continue
            if mechanism=='remaining_dequant' and site!='expsgate':continue
            budgets.append(dict(rank=rank,path=path,site=site,mechanism=mechanism,control=a,ablation=b,
                 signed_delta_ms_per_half=delta,ablation_bound_ms=max(0,delta) if delta is not None else None,
                 remaining_floor_ms=bv,achievable_lossless_budget_ms=None))
    for row in table:
        baseline=totals[row['rank'],row['path'],row['site']].get('production');value=row['estimated_ms_per_half']
        row['delta_vs_production_ms']=baseline-value if baseline is not None and value is not None else None
    return dict(schema='packet86.limiter-comparison.v1',diagnostic_nonexact=True,qualifying=False,submission_eligible=False,
                sites=table,mechanisms=budgets,limitations=LIMITATIONS)

def markdown(r):
    lines=['# Packet86 limiter diagnostic','', 'diagnostic_nonexact: true. No lossless speed claim.','',
           '| View | Rank/path | Site | Estimated ms/half | Saved vs production, ms |','| --- | --- | --- | ---: | ---: |']
    fmt=lambda v:'not measured' if v is None else f'{v:.5f}'
    for v in r['sites']:lines.append(f"| {v['view']} | {v['rank']}/{v['path']} | {v['site']} | {fmt(v['estimated_ms_per_half'])} | {fmt(v['delta_vs_production_ms'])} |")
    lines+=['','| Mechanism | Rank/path/site | Signed bound, ms/half | Achievable lossless budget |','| --- | --- | ---: | --- |']
    for v in r['mechanisms']:lines.append(f"| {v['mechanism']} | {v['rank']}/{v['path']}/{v['site']} | {fmt(v['signed_delta_ms_per_half'])} | not measured |")
    return '\n'.join(lines+['']+['- '+x for x in LIMITATIONS])+'\n'

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runs',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    reports={name:view_report(a.runs/name) for name in VIEWS};result=compare(reports)
    result['input_summaries']={n:dict(sources=r['sources'],seal_sha256=r['seal_sha256']) for n,r in reports.items()}
    a.output.write_text(json.dumps(result,indent=2)+'\n');a.output.with_suffix('.md').write_text(markdown(result))
