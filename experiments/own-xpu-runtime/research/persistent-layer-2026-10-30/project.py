#!/usr/bin/env python3
"""Persistent-layer projection (CPU arithmetic over measured numbers, not a measurement).

Inputs: the decode-site census (launch counts per class), this study's barrier and chain measurements, the four-card
stage overhead (exchange kernels per half) and the fixed-cost campaign (current four-card half times).
Writes results/projection.json and prints a short table.
"""
import json, os

D = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(D, '..')
census = json.load(open(os.path.join(R, 'decode-site-census-2026-10-30/results/census.json')))
bar = json.load(open(os.path.join(D, 'results/barrier-full2-c43.json')))
chain = json.load(open(os.path.join(D, 'results/chain-final-c43.json')))

def bar_us(variant, wg, nwg):
    for b in bar['barrier']:
        if b['variant'] == variant and b['wg'] == wg and b['nwg'] == nwg:
            return b['us_per_barrier']
    raise KeyError((variant, wg, nwg))

def boundary(kernel, nwg):
    for b in bar['boundary']:
        if b['kernel'] == kernel and b['nwg'] == nwg:
            return b['period_us']
    raise KeyError((kernel, nwg))

t = {(x['version'], x['wg'], x['nwg']): x['us_per_block'] for x in chain['timing']}
A = t[('A', 128, 0)]
persist = {k: v for k, v in t.items() if k[0] == 'B'}
best_key = min(persist, key=persist.get)
B = persist[best_key]
NB = 5  # boundaries removed per HC block (6 launches -> 1 phase sequence)
c_best = bar_us('counter/wg-fence', best_key[1], best_key[2])
net_per_boundary = (A - B) / NB                     # measured on the real chain (negative = loss)
b_chain = (A - B + NB * c_best) / NB                # boundary saving implied by the chain, barrier cost added back
b_empty = boundary('empty', 256)                    # empty-kernel period with the host ahead
b_upper = max(b_chain, b_empty)                     # zero-cost-barrier upper bound per absorbed launch

g = census['glue']
four = {  # per card per decode half on four cards: exchange kernels (stage-overhead) and current half (fixed-cost)
    'rank0': {'exchanges': 69, 'half_ms': 8.605},
    'rank1': {'exchanges': 76, 'half_ms': 9.515},
}
one_card_span = {'rank0': 10.12, 'rank1': 11.92}
hc_blocks = {'rank0': 46, 'rank1': 51}  # hc.a + hc.f per layer (23 / 25 layers) + rank 1's final hc

out = {'inputs': {
    'A_us_per_hc_block': A, 'best_persistent': {'wg': best_key[1], 'nwg': best_key[2], 'us_per_hc_block': B},
    'barrier_us_at_best_layout': c_best, 'net_us_per_absorbed_boundary_measured': net_per_boundary,
    'boundary_saving_us_implied_by_chain': b_chain, 'empty_kernel_period_us': b_empty,
    'upper_bound_us_per_absorbed_launch_free_barrier': b_upper},
    'ranks': {}}
for rk in ('rank0', 'rank1'):
    c = g[rk]
    total, small = c['half_launches'], c['small_launches']
    big = total - small
    scen = {
        'hc_blocks_only': hc_blocks[rk] * NB,
        'all_small_kernels (one persistent kernel per run between big kernels)': small - (big + 1),
        'whole_half (one persistent kernel, big GEMVs inside)': total - 1,
    }
    rows = {}
    for name, n in scen.items():
        rows[name] = {
            'absorbed_launches': n, 'fraction_of_launches': n / total,
            'one_card_ms_measured_net': n * net_per_boundary / 1e3,
            'one_card_ms_upper_free_barrier': n * b_upper / 1e3,
            'one_card_pct_upper': 100 * n * b_upper / 1e3 / one_card_span[rk],
            # four cards: the same launches on each card, plus the exchange kernels (absorbable only in the
            # whole-half case, and then only their launch, not their fence/flag time)
        }
        n4 = n + (four[rk]['exchanges'] if name.startswith('whole') else 0)
        rows[name].update({
            'four_card_absorbed_per_card': n4,
            'four_card_ms_measured_net': n4 * net_per_boundary / 1e3,
            'four_card_ms_upper_free_barrier': n4 * b_upper / 1e3,
            'four_card_pct_upper': 100 * n4 * b_upper / 1e3 / four[rk]['half_ms'],
            'four_card_pct_measured_net': 100 * n4 * net_per_boundary / 1e3 / four[rk]['half_ms'],
        })
    out['ranks'][rk] = {'launches': total, 'small_launches': small, 'big_launches': big,
                        'one_card_span_ms': one_card_span[rk], 'four_card_half_ms': four[rk]['half_ms'],
                        'scenarios': rows}
json.dump(out, open(os.path.join(D, 'results/projection.json'), 'w'), indent=1)
print(json.dumps(out['inputs'], indent=1))
for rk, v in out['ranks'].items():
    print(rk, 'launches', v['launches'], 'small', v['small_launches'], 'big', v['big_launches'])
    for name, r in v['scenarios'].items():
        print('  %-75s absorbed %4d (%.0f%%)  one card: net %+.2f ms, upper %+.2f ms (%.1f%%)  four cards: net %+.2f ms '
              '(%.1f%%), upper %+.2f ms (%.1f%%)' % (
                  name, r['absorbed_launches'], 100 * r['fraction_of_launches'], r['one_card_ms_measured_net'],
                  r['one_card_ms_upper_free_barrier'], r['one_card_pct_upper'], r['four_card_ms_measured_net'],
                  r['four_card_pct_measured_net'], r['four_card_ms_upper_free_barrier'], r['four_card_pct_upper']))
