#!/usr/bin/env python3
"""CPU-only model of four-card (TP) batched-prefill work per 256-row chunk (research/tp/prefill-tp-overhead-2026-10-30).

Sources:
- the plan builder (stage2/packet3/step/plan.hpp: hc(), gdn(), qsa(), moe(), ffn(), ple());
- the TP transform (gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp, the tptsxqckh flags: OWNRT_TP_SPLIT=.attention,.gdn.qkv,
  OWNRT_TP_GDN=heads, OWNRT_TP_QSA_SPLIT=1, OWNRT_TP_EXPERTS=compact, OWNRT_TP_EXCHANGE=direct);
- the batched prefill's exchange geometry (prefill_engine.hpp prefill_exchange: F32 rows, each card stores its part of every
  row into the peer).

For every site of one layer it records the class, whether TP splits it (each card does half: rows, heads or slots) or
replicates it (both cards do all M rows), and its multiply-accumulates per row. It then lists each layer's exchanges and
their bytes per card, and calibrates the MAC model against the measured one-card chunk (rank 1: 682.7 ms,
prefill-draft-batch t1c o-r1-one). MACs are a first-order proxy: formats (IQ3 experts, Q6/Q8 dense, BF16 HC) and
small-kernel fixed costs differ; the device measurements (run after the decode agent's gate) replace it.
Usage: tp_work_model.py [--json OUT]"""
import json, sys
g = dict(h=2560, low=320, experts=512, top=10, mid=640, kh=16, vh=48, d=128, qh=24, kvh=2, ad=256, ih=4, id=128)
h, low, mid, top = g['h'], g['low'], g['mid'], g['top']
M = 256
def hc_block(tag):  # plan.hpp hc(): norm (4 x h), low (low x 4h), silu/4, gate (4h x low), mix
    return [(f'{tag}.norm', 'replicated', 0), (f'{tag}.low', 'replicated', low * 4 * h), (f'{tag}.act', 'replicated', 0),
            (f'{tag}.gate', 'replicated', 4 * h * low), (f'{tag}.mix', 'replicated', 0)]
def moe_block():
    return [('router', 'replicated', g['experts'] * h), ('route+gather', 'replicated', 0), ('route_compact', 'per card', 0),
            ('expsgate+up', 'split (slots)', top * 2 * mid * h), ('expsact', 'split (slots)', 0), ('expsdown', 'split (slots)', top * h * mid),
            ('shexp gate+up', 'replicated', 2 * mid * h), ('shexpact', 'replicated', 0), ('shexpdown', 'replicated', h * mid),
            ('shared_gate', 'replicated', h), ('check_status', 'replicated', 0), ('moe_combine', 'replicated', 0)]
def gdn_layer():
    ch = (2 * g['kh'] + g['vh']) * g['d']
    sites = hc_block('hc.a') + [
        ('gdn.qkv', 'split (heads)', ch * h), ('gdn.z', 'split (heads)', g['vh'] * g['d'] * h), ('gdn.a+b', 'split (heads)', 2 * g['vh'] * h),
        ('gdn.conv', 'split (heads)', ch * 4), ('gdn.recurrence', 'split (heads)', g['vh'] * g['d'] * g['d'] * 2), ('gdn.gated', 'split (heads)', 0),
        ('attention (out proj)', 'split (rows)', h * g['vh'] * g['d']), ('attn.combine', 'replicated', 0)] + hc_block('hc.f') + moe_block() + [('ffn.combine', 'replicated', 0)]
    exchanges = [('gdn.gated tp_xheads', g['vh'] * g['d'] // 2 * 4), ('attention tp_xgather', h // 2 * 4), ('expsdown tp_xcompact', top // 2 * h * 4)]
    return sites, exchanges
def qsa_layer():
    sites = hc_block('hc.a') + [
        ('qsa.qgate', 'split (heads)', 2 * g['qh'] * g['ad'] * h), ('qsa.k+v', 'split (heads)', 2 * g['kvh'] * g['ad'] * h),
        ('qsa.iq+ik', 'replicated', (g['ih'] * g['id'] + g['id']) * h), ('qsa.prepare/pool', 'split (heads)', 0), ('qsa.select', 'replicated', 0),
        ('qsa.attention', 'split (heads)', 0), ('attention (out proj)', 'split (rows)', h * g['qh'] * g['ad']), ('attn.combine', 'replicated', 0)] + \
        hc_block('hc.f') + moe_block() + [('ffn.combine', 'replicated', 0)]
    exchanges = [('qsa.attention tp_xgather', g['qh'] * g['ad'] // 2 * 4), ('attention tp_xgather', h // 2 * 4), ('expsdown tp_xcompact', top // 2 * h * 4)]
    return sites, exchanges
def rank(layers):
    qsa = [i for i in layers if i % 4 == 3]
    out = dict(layers=len(layers), qsa_layers=len(qsa), gdn_layers=len(layers) - len(qsa), classes={}, exchanges={}, exchanges_per_card=0, exchange_bytes_per_card=0)
    for i in layers:
        sites, ex = qsa_layer() if i % 4 == 3 else gdn_layer()
        for name, kind, macs in sites:
            c = out['classes'].setdefault(name, dict(kind=kind, macs_per_row=0, layers=0)); c['macs_per_row'] += macs; c['layers'] += 1
        for name, b in ex:
            e = out['exchanges'].setdefault(name, dict(bytes_per_row_per_card=b, layers=0)); e['layers'] += 1
            out['exchanges_per_card'] += 1; out['exchange_bytes_per_card'] += b * M
    if 1 in layers:  # rank 0, layer 1: PLE (replicated): key 4h x h, value h x h
        out['classes']['ple key+value'] = dict(kind='replicated', macs_per_row=4 * h * h + h * h, layers=1)
    one = sum(c['macs_per_row'] for c in out['classes'].values())
    rep = sum(c['macs_per_row'] for c in out['classes'].values() if c['kind'] == 'replicated')
    out.update(macs_per_row_one_card=one, macs_per_row_replicated=rep, replicated_share=rep / one,
               per_card_over_one_card=(rep + (one - rep) / 2) / one)
    return out
r1 = rank(list(range(23, 48))); r0 = rank(list(range(0, 23)))
measured = dict(rank1_one_card_ms=682.7, rank1_tp_ms=462.8, rank0_tp_ms_harness=412.7, rank1_tp_long_ms=466.4, rank0_prefill_long_ms=446.2)
for r, name in ((r1, 'rank1'), (r0, 'rank0')):
    r['exchange_mb_per_card_per_chunk'] = r['exchange_bytes_per_card'] / 1e6
r1['model'] = dict(one_card_ms=measured['rank1_one_card_ms'], perfect_split_ms=measured['rank1_one_card_ms'] / 2,
                   compute_only_tp_ms=measured['rank1_one_card_ms'] * r1['per_card_over_one_card'],
                   replicated_excess_ms=measured['rank1_one_card_ms'] * r1['replicated_share'] / 2,
                   measured_tp_ms=measured['rank1_tp_ms'])
r1['model']['unexplained_ms'] = r1['model']['measured_tp_ms'] - r1['model']['compute_only_tp_ms']
ms_per_mac = measured['rank1_one_card_ms'] / (r1['macs_per_row_one_card'] * M)
r0_one_est = r0['macs_per_row_one_card'] * M * ms_per_mac
r0['model'] = dict(one_card_ms_estimated=r0_one_est, perfect_split_ms=r0_one_est / 2, compute_only_tp_ms=r0_one_est * r0['per_card_over_one_card'],
                   replicated_excess_ms=r0_one_est * r0['replicated_share'] / 2, measured_tp_ms_harness=measured['rank0_tp_ms_harness'])
r0['model']['unexplained_ms'] = r0['model']['measured_tp_ms_harness'] - r0['model']['compute_only_tp_ms']
def lever_ms(r, classes, frac=0.5):  # ms per chunk saved per card if these replicated classes were split in half
    one = r['model'].get('one_card_ms', r['model'].get('one_card_ms_estimated'))
    return one * sum(r['classes'][c]['macs_per_row'] for c in classes if c in r['classes']) / r['macs_per_row_one_card'] * frac
levers = {}
for r, name in ((r1, 'rank1'), (r0, 'rank0')):
    L = r['layers']
    levers[name] = dict(
        hc_gate_mix_split=dict(saved_compute_ms=lever_ms(r, ['hc.a.gate', 'hc.f.gate']), extra_exchanges=2 * L, extra_mb_per_card=2 * L * (h // 2 * 4) * M / 1e6),
        hc_low_split=dict(saved_compute_ms=lever_ms(r, ['hc.a.low', 'hc.f.low']), extra_exchanges=2 * L, extra_mb_per_card=2 * L * (low // 2 * 4) * M / 1e6),
        shared_expert_split=dict(saved_compute_ms=lever_ms(r, ['shexp gate+up', 'shexpdown']), extra_exchanges=L, extra_mb_per_card=L * (h // 2 * 4) * M / 1e6),
        router_split=dict(saved_compute_ms=lever_ms(r, ['router']), extra_exchanges=L, extra_mb_per_card=L * (g['experts'] // 2 * 4) * M / 1e6))
out = dict(schema='prefill-tp-overhead.work-model.v1', chunk_rows=M, geometry=g, measured=measured, rank1=r1, rank0=r0, levers_model_only=levers,
           ms_per_gmac_rank1_one_card=ms_per_mac * 1e9)
if '--json' in sys.argv:
    open(sys.argv[sys.argv.index('--json') + 1], 'w').write(json.dumps(out, indent=1) + '\n')
for name, r in (('rank1', r1), ('rank0', r0)):
    print(f"{name}: {r['layers']} layers ({r['qsa_layers']} QSA), exchanges per card per chunk {r['exchanges_per_card']} ({r['exchange_mb_per_card_per_chunk']:.0f} MB per card), "
          f"replicated share of MACs {r['replicated_share']:.1%}, per card / one card {r['per_card_over_one_card']:.3f}")
    print('  model:', {k: round(v, 1) for k, v in r['model'].items()})
    for c, v in sorted(r['classes'].items(), key=lambda x: -x[1]['macs_per_row']):
        if v['macs_per_row']: print(f"   {c:24s} {v['kind']:15s} {v['macs_per_row']/1e6:8.1f} M MAC/row")
    for e, v in r['exchanges'].items(): print(f"   exchange {e:28s} {v['bytes_per_row_per_card']/1e3:6.1f} KB/row/card x {v['layers']} layers")
print('levers (compute saved per card per chunk, model only):', json.dumps({k: {n: {a: round(b, 1) for a, b in d.items()} for n, d in v.items()} for k, v in levers.items()}, indent=1))
