#!/usr/bin/env python3
import json, statistics
from pathlib import Path
R=Path('/dev/shm/ownrt-lab-r0-c23/runs')
def summary(name): return json.loads((R/name/'summary.json').read_text())
def half(name):
    v=summary(name)['half_ms']; return sorted(v)[len(v)//2]
def profile(name):
    rows=[json.loads(x) for x in (R/name/'rank0'/'decode-device-profile.jsonl').read_text().splitlines()]
    rows=[x for x in rows if not x['speculative'] and not x['cancelled']]
    return {
        'halves':len(rows),
        'qkv_us_per_half':statistics.median(x['sites']['gemv:Q6_K:gdn.qkv']['busy_us'] for x in rows),
        'span_us':statistics.median(x['span_us'] for x in rows),
    }
refs=['ab-ref1','ba-ref2','ab-ref3']; cands=['ab-cand1','ba-cand2','ab-cand3']
pairs=list(zip(refs,cands))
out={
    'reference_half_ms':{n:half(n) for n in refs},
    'candidate_half_ms':{n:half(n) for n in cands},
    'paired_delta_ms':{f'{a}-{b}':half(a)-half(b) for a,b in pairs},
    'reference_median_of_run_medians_ms':statistics.median(half(n) for n in refs),
    'candidate_median_of_run_medians_ms':statistics.median(half(n) for n in cands),
    'median_paired_delta_ms':statistics.median(half(a)-half(b) for a,b in pairs),
    'profile_reference':profile('prof-ref'),
    'profile_candidate':profile('prof-cand'),
}
print(json.dumps(out,indent=2))
