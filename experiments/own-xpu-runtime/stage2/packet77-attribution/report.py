#!/usr/bin/env python3
"""Current-selection effective-read accounting; no invented device measurements."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics as st

from byte_formulas import accounting
from outside import breakdown
from summarize import summarize, read_events, require, stats
from timeline import sha

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
REFERENCE_GBS = 555


def site_rows(root, tensors):
    account = accounting(tensors)
    samples = defaultdict(list)
    sources = {}
    for directory in sorted((root / 'attribution').iterdir()):
        if not (directory / 'receipt.json').is_file():
            continue
        events = read_events(directory, sources)
        groups = defaultdict(list)
        for e in events:
            if e['speculative'] or not e['label'].startswith(('blk.22.', 'blk.23.', 'blk.24.', 'blk.27.')):
                continue
            groups[e['rank'], e['fixture'], e['position'], e['label'].split('.')[1]].append(e)
        for (rank, fixture, position, layer), rows in groups.items():
            require(any(e['label'] == f'blk.{layer}.ffn.combine' for e in rows),
                    'incomplete corrected layer')
            calls = defaultdict(list)
            for e in rows:
                calls['.'.join(e['label'].split('.')[2:])].append(e)
            for site, call in calls.items():
                us = sum(e['end_ns'] - e['start_ns'] for e in call) / 1000
                require(us > 0, 'zero compute site duration')
                samples[rank, int(layer), site].append(dict(us=us, position=position,
                    event_count=len(call), bytes=account(int(layer), site, position)))
    result = []
    for (rank, layer, site), calls in sorted(samples.items()):
        kind = 'QSA' if layer % 4 == 3 else 'GDN'
        count = 6 if kind == 'QSA' else 18
        us = st.median(c['us'] for c in calls)
        b = dict(calls[0]['bytes'])
        for key in ('read_bytes', 'write_bytes', 'gguf_weight_bytes', 'runtime_weight_read_bytes', 'activation_state_read_bytes'):
            b[key] = st.median(c['bytes'][key] for c in calls)
        floor = b['read_bytes'] / (REFERENCE_GBS * 1000)
        result.append(dict(rank=rank, layer=layer, site=site, kind=kind,
            measured_call_median_us=us, calls=len(calls),
            events_per_call=sorted({c['event_count'] for c in calls}),
            positions=[min(c['position'] for c in calls), max(c['position'] for c in calls)],
            occurrences_per_half=count, estimated_us_per_half=us*count,
            effective_read_GBs=b['read_bytes']/us/1000,
            reference_floor_us=floor, headroom_us_per_call=us-floor,
            estimated_headroom_us_per_half=(us-floor)*count, **b))
    require({(r['rank'], r['kind']) for r in result} == {(0,'GDN'),(0,'QSA'),(1,'GDN'),(1,'QSA')},
            'missing sampled rank/type')
    ranking = []
    for rank, site in sorted({(r['rank'],r['site']) for r in result}):
        members = [r for r in result if r['rank']==rank and r['site']==site]
        cost = sum(r['estimated_us_per_half'] for r in members)
        reads = sum(r['read_bytes']*r['occurrences_per_half'] for r in members)
        ranking.append(dict(rank=rank, site=site, occurrences_per_half=sum(r['occurrences_per_half'] for r in members),
            estimated_us_per_half=cost, effective_read_GBs=reads/cost/1000,
            estimated_headroom_us_per_half=sum(r['estimated_headroom_us_per_half'] for r in members),
            sampled_layers=[r['layer'] for r in members], measured=False))
    return result, ranking, sources


def generate(root):
    root = Path(root)
    base = summarize(root)  # validates paired tokens, acceptance, events and cancellations
    selection = P / 'selection.json'
    require(all(json.loads(f.read_text())['selection_sha256']==sha(selection)
                for f in root.glob('*/*/receipt.json')), 'not packet70 selected view')
    build = json.loads((P/'build-device-receipt.json').read_text())
    require(all(json.loads(f.read_text())['binary_sha256']==build['artifacts']['build/device/own-rt-iq3']
                for f in root.glob('*/*/receipt.json')), 'not packet77 instrumented binary')
    census = P.parent / 'packet72-occupancy/header-census.json'
    pins = json.loads((P/'dependency-pins.json').read_text())
    require(sha(census)==pins[str(census.relative_to(ROOT))], 'tensor census changed')
    tensors = json.loads(census.read_text())['tensors']
    rows, ranking, sources = site_rows(root, tensors)
    out = breakdown(root, base)
    # Same expanded representation and activation/scratch reads as packet72.
    def weight_reads(names):
        total = 0
        for name in names:
            t = tensors[name]
            if t['type'] in ('Q6_K','Q8_0'):
                import math
                total += math.prod(t['dimensions']) * (1+4/(16 if t['type']=='Q6_K' else 32))
            else:
                total += t['bytes']
        return total
    reads = dict(target_head=weight_reads(['output.weight'])+5120,
        final_norm_merge=weight_reads([n for n in tensors if n.startswith('output_hc_')])+21760+20480+640+40960,
        argmax=496640+1944+486)
    outside = []
    for site in ('target_head','final_norm_merge','argmax','transfers','host_wait_submission_and_unattributed_us'):
        timing = out['measured'].get(site, {'count':0})
        require(timing['count'] > 0 or site=='transfers', 'missing outside measurement: '+site)
        us = timing.get('mean_us',0)
        n = reads.get(site)
        outside.append(dict(site=site, measured=timing, read_bytes=n,
            effective_read_GBs=n/us/1000 if n is not None and us>0 else None,
            headroom_us=n is not None and us-n/(REFERENCE_GBS*1000) if n is not None else None))
        if n is not None:
            ranking.append(dict(rank=1, site=site, occurrences_per_half=1,
                estimated_us_per_half=us, effective_read_GBs=n/us/1000,
                estimated_headroom_us_per_half=us-n/(REFERENCE_GBS*1000), measured=True))
    ranking.sort(key=lambda r:(r['rank'],-r['estimated_headroom_us_per_half']))
    for rank in (0,1):
        for order,row in enumerate((r for r in ranking if r['rank']==rank),1):
            row['order_within_rank']=order
    base.update(schema='packet77.attribution.v1', selected_view='packet70 1-draft-hc-batch + experts=wide64, placement 1',
        selection_sha256=sha(selection), binary_sha256=build['artifacts']['build/device/own-rt-iq3'],
        reference_GBs=REFERENCE_GBS, sites=rows, lever_ranking=ranking, rank1_outside_split=outside,
        rank1_outside_samples=out['samples'], actual_dram_GBs=None, actual_dram_bytes=None,
        byte_formula_sha256=sha(P/'byte_formulas.py'), tensor_census_sha256=sha(census))
    base['sources'].update(sources)
    base['limitations'] += [
        'Effective read GB/s uses useful expanded/packed tensor reads plus activation/state/scratch reads. It is not measured DRAM traffic.',
        '555 GB/s is a reference, not an attainable kernel floor. Headroom is call time minus read bytes / 555000, multiplied by occurrences.',
        'Layer times are sampled at 22/23 and 24/27. Per-half class costs are estimates; no unsampled layer timing or model speed is invented.',
        'Rank0 corrected calls are miss-conditioned. Rank costs overlap and must not be summed into an end-to-end speedup.',
        'Outside split uses paired same-command samples. Signed residual includes host waits, submission, gaps and other unsampled work; no bandwidth is assigned to it.',
        'Use raw instrumented timings for bandwidth; control/attribution ratios are reported separately, never silently corrected.']
    return base


def markdown(r):
    lines = ['# Packet77 current-record attribution', '', r['selected_view'], '',
        'Diagnostic lane-B screen; not a speed record. Raw event times. Effective useful-read bandwidth, not DRAM counters. Per-half class times multiply sampled call medians by occurrences.', '',
        '| Rank | Order | Class | Occurrences/half | ms/half | Read GB/s | Headroom vs 555 GB/s, ms/half |',
        '| ---: | ---: | --- | ---: | ---: | ---: | ---: |']
    for v in r['lever_ranking']:
        lines.append(f"| {v['rank']} | {v['order_within_rank']} | {v['site']} | {v['occurrences_per_half']} | {v['estimated_us_per_half']/1000:.4f} | {v['effective_read_GBs']:.2f} | {v['estimated_headroom_us_per_half']/1000:.4f} |")
    lines += ['', 'Rank 1 outside layers (mean of complete command samples; microseconds):', '',
        '| Part | Mean us | Read GB/s |', '| --- | ---: | ---: |']
    for v in r['rank1_outside_split']:
        rate='not applicable' if v['effective_read_GBs'] is None else f"{v['effective_read_GBs']:.2f}"
        lines.append(f"| {v['site']} | {v['measured'].get('mean_us',0):.3f} | {rate} |")
    lines += ['', 'Instrumentation overhead (control / instrumented median):', '',
        '| Scope | Ratio |', '| --- | ---: |']
    for name in ('sampled_cycles','full_cycles','draft_wall'):
        lines.append(f"| {name} | {r[name]['all']['control_over_instrumented']:.4f} |")
    lines += ['', *['- '+v for v in r['limitations']]]
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    result=generate(a.run)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    a.output.with_suffix('.md').write_text(markdown(result))
