"""Same-card event accounting; no inferred target-head time or GPU-idle claim."""
from collections import defaultdict
import json
from pathlib import Path
import statistics as st

P=Path(__file__).resolve().parent
CENSUS=P.parents[3]/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'

def byte_counts():
    tensors=json.loads(CENSUS.read_text())['tensors']
    head=next(t for t in tensors if t['name']=='output.weight')
    assert head['type']=='Q6_K' and head['dimensions']==[2560,248320]
    # arithmetic.hpp -> expanded.hpp: one int8 per weight and F32 scale per 16.
    return dict(head=head,head_resident_bytes=248320*(2560+2560//16*4),
                draft_prefix_packed_bytes=head['bytes']*91392//248320,
                draft_prefix_resident_bytes=91392*(2560+2560//16*4),
                final_weights=[t for t in tensors if t['name'].startswith('output_hc_')])

def stats(v):
    return dict(count=len(v),mean_us=st.mean(v),median_us=st.median(v)) if v else dict(count=0)

def roofline(n,t):
    return dict(logical_bytes=n,measured_us=t,logical_GB_s=n/t/1000 if t>0 else None,
                bandwidth_reference_GB_s=[540,590],floor_us_at_540=n/540000,floor_us_at_590=n/590000,
                definition='logical bytes/time, not hardware memory-counter traffic')

def breakdown(root, report):
    samples=[];by_label=defaultdict(list)
    for directory in sorted((Path(root)/'attribution').glob('*')):
        if not (directory/'receipt.json').exists():continue
        receipt=json.loads((directory/'receipt.json').read_text())
        events=[json.loads(s) for s in (directory/'rank1/sites.jsonl').read_text().splitlines()]
        events=[e for e in events if e.get('schema')=='packet57.event.v1' and not e['label'].startswith('draft.')]
        groups=defaultdict(list)
        for e in events:groups[e['position']].append(e)
        commands={r['position']:r for r in receipt['rank_trace'] if r['rank']==1 and r['op']==1}
        for pos,rows in groups.items():
            begin=[e['start_ns'] for e in rows if e.get('layer_boundary')=='begin'];end=[e['end_ns'] for e in rows if e.get('layer_boundary')=='end']
            if not begin or not end:continue
            lo,hi=min(begin),max(end);c=commands[pos]
            outside=(c['rank_completed']-c['rank_received'])*1e6-(hi-lo)/1000
            costs=defaultdict(float)
            for e in rows:
                if e['label'].startswith('blk.'):continue
                # Clip copies to outside of the layer span; kernels are wholly outside.
                ns=max(0,min(e['end_ns'],lo)-e['start_ns'])+max(0,e['end_ns']-max(e['start_ns'],hi))
                costs[e['class']]+=ns/1000
                by_label[e['label']].append(ns/1000)
            for required in ('target_head','final_norm_merge','argmax'):
                if required not in costs:raise ValueError('missing outside-layer site: '+required)
            samples.append(dict(prompt=directory.name,position=pos,outside_us=outside,**costs,
                host_wait_submission_and_unattributed_us=outside-sum(costs.values())))
    if not samples:raise ValueError('no complete rank1 outside-layer samples')
    keys=set().union(*(r.keys() for r in samples))-{'prompt','position'}
    measured={k:stats([r.get(k,0) for r in samples]) for k in sorted(keys)}
    b=byte_counts();rates={'target_head':roofline(b['head_resident_bytes'],measured['target_head']['mean_us'])}
    draft=next(r for r in report['draft_breakdown'] if r['category']=='head_prefix')
    rates['draft_head_prefix']=roofline(b['draft_prefix_resident_bytes'],draft['measured']['mean_us'])
    # Final HC Q8_0 also expands, F32 norm stays F32.
    final_bytes=sum((t['dimensions'][0]+t['dimensions'][0]//32*4)*t['dimensions'][1] if t['type']=='Q8_0' else t['bytes'] for t in b['final_weights'])
    rates['final_norm_merge']=roofline(final_bytes,measured['final_norm_merge']['mean_us'])
    rates['argmax']=roofline(248320*2,measured['argmax']['mean_us'])
    return dict(samples=samples,measured=measured,sites={k:stats(v) for k,v in sorted(by_label.items())},roofline=rates,tensor_identity=b,
                limitations=['No cross-card timestamp subtraction. Negative residuals remain visible.',
                  'Residual includes host submission, waits, gaps and unsampled work; it is not GPU idle.',
                  'No GB/s assigned to host waits. Transfers need payload accounting; attention/HC aggregate traffic needs per-site tensor and context accounting.',
                  'Head bandwidth uses expanded resident bytes; GGUF bytes are separately recorded.'])
