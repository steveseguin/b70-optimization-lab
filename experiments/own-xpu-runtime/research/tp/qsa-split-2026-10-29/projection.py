#!/usr/bin/env python3
"""Stage 3 (QSA split by KV group) projection for rank 1, from retained per-site profiles (CPU only).

Inputs (repo-relative to experiments/own-xpu-runtime/research/):
- decode-next2/profile-final.json: rank-1 per-site device profile, split 23, 4096-row prompt (positions ~4.1K),
  B17-era kernels with the QSA attention restructure (OWNRT_ATTN_HEADS/COMBINE2) on; 7 QSA layers (23, 27, ..., 47).
- pp4-review-2026-10-28/within-layer-sizing/evidence/b19-rank0-prof-b19-decode-device-profile.jsonl.gz: the B19 binary
  itself (rank 0, 5 QSA layers, positions 4096-4143), a cross-check of the per-layer QSA kernel costs.
- qsa-attention/results.json: in-engine attention passes at 4096 (admit 3.65, tiles 32.3, combine 7.9 us per layer).
- direct-exchange-2026-10-28/RESULT.md: in-engine direct exchange 6.1 us each (both cards, skew included).
Writes projection.json."""
import gzip, json, statistics as st
from pathlib import Path
R = Path(__file__).resolve().parents[2]
prof = json.load(open(R / 'decode-next2/profile-final.json'))
site = {r['site']: r for r in prof['rows']}
L = 7  # rank-1 QSA layers at split 23
qg6, qg5 = site['gemv:Q6_K:qsa.qgate'], site['gemv:Q5_K:qsa.qgate']
k, v, iq = site['gemv:Q6_K:qsa.k'], site['gemv:Q6_K:qsa.v'], site['gemv:BF16:qsa.iq']
prep, pool, sel, att = site['qsa_prepare'], site['qsa_append_pool'], site['qsa_select'], site['qsa_attention']
admit = 3.65  # us per layer, replicated
qgate = qg6['us'] + qg5['us']
splittable = {'qsa.qgate': qgate, 'qsa.k': k['us'], 'qsa.v': v['us'], 'qsa_prepare': prep['us'],
              'qsa_attention tiles+combine': att['us'] - L * admit}
replicated = {'qsa.iq (iq+ik)': iq['us'], 'qsa_select': sel['us'], 'qsa_append_pool': pool['us'], 'qsa_attention admit': L * admit}
g = 6.1; exch = L * g
f = 5.0  # fixed per-launch cost (us), sizing calibration
ideal = sum(splittable.values()) / 2 - exch
low = sum((r['us_per_launch'] - f) / 2 * r['launches'] for r in (qg6, qg5)) - exch  # only the qgate GEMV halves
def central(att_scale):
    s_qgate = qgate / 2  # bandwidth-bound: half the bytes at the same rate (target head split, draft qgate split)
    s_kv = sum((r['us_per_launch'] - f) / 2 * r['launches'] for r in (k, v))
    s_prep = (prep['us_per_launch'] - f) / 2 * L
    s_att = 0.25 * (att['us'] - L * admit) * att_scale  # 130 -> 65 work-groups, about one wave either way
    return s_qgate + s_kv + s_prep + s_att - exch
# B19 rank-0 cross-check (same kernels; positions 4096+)
rows = [json.loads(l) for l in gzip.open(R / 'pp4-review-2026-10-28/within-layer-sizing/evidence/b19-rank0-prof-b19-decode-device-profile.jsonl.gz', 'rt')][2:]
b19 = {}
for name in ('qsa_attention', 'qsa_prepare', 'qsa_append_pool', 'qsa_select', 'gemv:Q5_K:qsa.qgate', 'gemv:Q6_K:qsa.k', 'gemv:Q6_K:qsa.v', 'gemv:BF16:qsa.iq'):
    xs = [r['sites'][name] for r in rows if name in r['sites']]
    b19[name] = round(st.median(x['busy_us'] for x in xs) / st.median(x['count'] for x in xs), 2)
out = dict(schema='ownrt.qsa-split-projection.v1', date='2026-10-29', cpu_only=True, rank=1, qsa_layers=L,
           note='Rank 1 has 7 QSA layers at split 23 (23, 27, ..., 47); rank 0 has 5 (3, 7, 11, 15, 19).',
           rank1_qsa_us_per_half_replicated_today=round(sum(splittable.values()) + sum(replicated.values()), 1),
           splittable_us={k_: round(v_, 1) for k_, v_ in splittable.items()},
           replicated_us={k_: round(v_, 1) for k_, v_ in replicated.items()},
           qgate_bytes_per_layer={'Q6_K': qg6['bytes'] // qg6['launches'], 'Q5_K': qg5['bytes'] // qg5['launches']},
           qgate_gbps={'Q6_K': round(qg6['bytes'] / qg6['launches'] / qg6['us_per_launch'] / 1e3, 1), 'Q5_K': round(qg5['bytes'] / qg5['launches'] / qg5['us_per_launch'] / 1e3, 1)},
           extra_exchanges=L, exchange_us=g, exchange_total_us=round(exch, 1),
           projection_saving_us={'ideal_exact_halving': round(ideal, 1), 'central_4k_positions': round(central(1.0), 1),
                                 'central_1100_positions': round(central(35 / 65), 1),
                                 'low_qgate_only_5us_fixed': round(low, 1)},
           b19_rank0_per_layer_us_crosscheck=b19,
           threshold_us=150, decision='build' if central(35 / 65) >= 150 else 'stop')
Path(__file__).with_name('projection.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps(out, indent=1))
