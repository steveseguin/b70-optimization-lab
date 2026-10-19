"""Replay existing record intervals; head-time conversions are sensitivities."""
import ast
import csv
from collections import defaultdict
import hashlib
import json
import statistics as st
import math
from audit import P, guard


def main():
    guard()
    parent = P.parent/'packet160-critical-path/analyze.py'
    nodes = [n for n in ast.parse(parent.read_text()).body if isinstance(n, ast.FunctionDef)
             and n.name in ('model', 'aggregate', 'require')]
    scope = dict(defaultdict=defaultdict, st=st, math=math)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(parent), 'exec'), scope)
    model, aggregate = scope['model'], scope['aggregate']
    path = P.parent/'packet160-critical-path/evidence/record-intervals.csv'
    records = []
    for row in csv.DictReader(path.open()):
        records.append({k: (v if k in ('prompt_id', 'prompt_class') else float(v))
                        for k, v in row.items() if k in ('prompt_id', 'prompt_class', 'D', 'R', 'C', 'A', 'B', 'spec_start_offset_ms', 'unresolved_control_gaps_ms', 'elapsed_ms')})
    groups = defaultdict(list)
    for r in records:
        groups[r['prompt_id']].append(r)
    requests = [(v[0]['prompt_class'], v) for v in groups.values()]
    base = aggregate(requests, model)
    assert len(records)==1188 and abs(base-58.798108759)<1e-8
    assert max(abs(model(r)-r['elapsed_ms']) for r in records)<1e-7
    fractions = list(csv.DictReader((P/'evidence/fractions.csv').open()))
    draft_time = json.loads((P.parent/'packet158-draft-levers/roofline.json').read_text())
    dt = next(r['measured_ms'] for r in draft_time['ranked'] if r['group']=='head_gemv')
    tt = 1.403683854
    results = []
    for scheme in sorted({r['scheme'] for r in fractions}):
        dr = st.mean(float(r['read_equivalent_fraction']) for r in fractions if r['head']=='draft' and r['scheme']==scheme)
        for corpus in ('suite', 'independent'):
            fr = [r for r in fractions if r['head']=='target' and r['corpus']==corpus and r['scheme']==scheme]
            tr = st.mean(float(r['read_equivalent_fraction']) for r in fr)
            per_prompt = defaultdict(list)
            for r in fr:
                per_prompt[r['prompt']].append(float(r['read_equivalent_fraction']))
            metadata = 4*({'row_cs':1,'block256_cs':10,'quant16_cs':160,'partial256':10,'quant16_partial256':160}[scheme])+4
            for costs in ('free_metadata_and_ordering', 'metadata_bandwidth_sensitivity'):
                # A copy-bandwidth sensitivity, not a measured latency floor.
                dcost = 0 if costs.startswith('free') else metadata*80128/537_000_000
                tcost = 0 if costs.startswith('free') else metadata*248320/537_000_000
                d = dt*(1-dr)-dcost
                def predict(r):
                    f = st.mean(per_prompt[r['prompt_id']]) if corpus=='suite' else tr
                    # Donate the ENTIRE historical full-head saving to B,
                    # overgenerous compared with the unequal split/overlap.
                    return model(r, d=d, b=tt*(1-f)-tcost)
                rate = aggregate(requests, predict)
                results.append(dict(scheme=scheme,target_corpus=corpus,costs=costs,
                                    target_mean_read_fraction=tr,draft_incident_mean_read_fraction=dr,
                                    draft_gross_ms=dt*(1-dr),target_gross_ms=tt*(1-tr),
                                    draft_metadata_proxy_ms=dcost,target_metadata_proxy_ms=tcost,
                                    projected_tok_s=rate,gain_percent=100*(rate/base-1),
                                    measured_speed=False,position_matched_record_fractions=False))
    result = dict(schema='packet161.replay-sensitivities.v1',record_tok_s=base,
                  draft_head_historical_ms=dt,target_full_head_historical_ms=tt,
                  current_target_half_gpu_ms=None,intervals=1188,results=results,
                  source_pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                               (parent,path,P/'evidence/fractions.csv',P.parent/'packet158-draft-levers/roofline.json')},
                  caveats=['Not a device measurement or qualification.',
                           'Draft has 65 incident-only positions; independent draft absent.',
                           'Sampled target per-prompt means are not the record per-position fractions.',
                           'Target timing is historical full-head, donated entirely to B.',
                           'Bound computation, launches, disrupted coalescing and repeated metadata reads are unpriced nonnegative costs.'])
    (P/'evidence/pricing.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(record_tok_s=base,best_free_gain_percent=max(r['gain_percent'] for r in results if r['costs'].startswith('free')),
                         best_metadata_gain_percent=max(r['gain_percent'] for r in results if not r['costs'].startswith('free')))),flush=True)


if __name__=='__main__':
    main()
