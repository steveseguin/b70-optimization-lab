#!/usr/bin/env python3
"""Exact two-card within-layer split sizing (CPU-only; reads retained device profiles, writes sizing.json).

Run: python3 -B size_within_layer.py   (no GPU, no engine, no service)
"""
import collections, gzip, json, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, '..', '..'))          # .../research
REL = lambda p: os.path.relpath(p, os.path.normpath(os.path.join(RES, '..', '..', '..')))

# ---------------------------------------------------------------- inputs (every number has a source path)
SRC = {
    'b19_rank0_profile': os.path.join(HERE, 'evidence', 'b19-rank0-prof-b19-decode-device-profile.jsonl.gz'),
    'b19_rank0_profile_origin': '/dev/shm/ownrt-lab-r0-c27prefill/runs/prof-b19/rank0/decode-device-profile.jsonl '
                                '(sha256 843c0434...; B19 binary 51f32b2655cc, OWNRT_DECODE_PROFILE=2, card 27, '
                                '4096-row prompt, 2026-10-26 18:53)',
    'rank1_profile': os.path.join(RES, 'decode-next2', 'profile-final.json'),
    'calib_profile': os.path.join(HERE, 'evidence', 'calib-rank1-prof-a-20261026-decode-device-profile.jsonl.gz'),
    'calib_profile_origin': '/dev/shm/ownrt-lab-20261026/rank1-prof-a/rank1/decode-device-profile.jsonl '
                            '(sha256 1c81913a...; build-prof, 2026-10-26 00:33, split 23, 1079 buffers, '
                            'decode rows at positions 302-347 after a 300-row prompt)',
    'tp_evidence': os.path.join(RES, 'tp', 'evidence'),
}
T1 = {  # measured unprofiled halves (ms)
    'b19_rank0': (10.673, 'research/rank0-gdn-c43/RESULT.md (median of 3, card 43); CURRENT.md "10.875 -> 10.673"'),
    'b19_rank0_draft': (1.734, 'research/rank0-iq4-c47/results-gdn.json gdn_prep_on.draft_median_ms'),
    'b19_rank1': (12.473, 'research/long-context-c43/RESULT.md (B19 binary, 4096 positions)'),
    'b19_toks': (66.21, 'CURRENT.md "B19 51f32b2655cc, 66.21 tok/s exact"'),
}
F_LAUNCH_US = 5.0   # fixed per-launch excess: research/decode-next2/RESULT.md "about 5-6 us over the 10.9 us floor"
G_GRID = [3, 5, 7, 13, 26]
ROUTE_BY_ID_BUSIEST = 6.23  # research/2026-10-24-exact-multicard-design.md route statistics, 2 cards by id


def opn(p):
    return gzip.open(p, 'rt') if p.endswith('.gz') else open(p)


def profile_jsonl(path, keep):
    rows = [json.loads(l) for l in opn(path)]
    rows = [r for r in rows if not r['cancelled'] and keep(r)]
    acc, cnt = collections.defaultdict(list), {}
    for r in rows:
        for k, v in r['sites'].items():
            acc[k].append(v['busy_us']); cnt[k] = v['count']
    sites = {k: {'launches': cnt[k], 'us': round(st.mean(v), 2)} for k, v in acc.items()}
    return sites, {'halves': len(rows), 'span_us_median': round(st.median(r['span_us'] for r in rows), 1),
                   'positions': [rows[0]['position'], rows[-1]['position']]}


def load_profiles():
    b0, b0m = profile_jsonl(SRC['b19_rank0_profile'], lambda r: r['position'] >= 4098)  # skip first 2 halves
    d = json.load(open(SRC['rank1_profile']))
    r1 = {r['site']: {'launches': r['launches'], 'us': r['us']} for r in d['rows']}
    r1m = {'halves': d['halves'], 'span_us_median': d['span_us_median']}
    ca, cam = profile_jsonl(SRC['calib_profile'], lambda r: r['fixture'] == 1 and r['position'] >= 302)
    return (b0, b0m), (r1, r1m), (ca, cam)


# ---------------------------------------------------------------- classification
CLASS_DOC = {
    'gdn_head': 'split by independent GDN heads (8 key + 24 value heads per card); per-head rows/state/norm, exact',
    'qsa_head': 'split by the two QSA KV groups (12 query heads + 1 KV head per card); per-head arithmetic, exact',
    'qsa_shared': 'replicated: shared index query/pool/selector (qsa-kv-head-shard-feasibility.txt)',
    'out_proj': 'split by output rows (1280/1280) of the 6144->2560 projection; full K per row, exact',
    'routed': 'split by slot (each slot computed whole on one card; combine order unchanged)',
    'shared_expert': 'whole unit on one card (gate/up rows could split, but down would need a K split)',
    'hc_gemv': 'replicated in H (row split possible but adds 2 exchanges per HC block)',
    'head_rows': 'rank 1 only: vocabulary-row split + merged argmax (exact-head-row-shard-feasibility.txt)',
    'replicated': 'replicated glue: norms, HC mix/combine/act, router+shared gate, route, gather, combine, status, PLE',
    'other': 'replicated: inter-kernel gaps and host start/finish (T1 minus profiled busy)',
}


def classify(site):
    if site.startswith('routed_gemv:'):
        return 'routed'
    name = site.split(':')[-1]
    if site.startswith('gemv:'):
        return {'gdn.qkv': 'gdn_head', 'gdn.z': 'gdn_head', 'gdn.a': 'gdn_head', 'qsa.qgate': 'qsa_head',
                'qsa.k': 'qsa_head', 'qsa.v': 'qsa_head', 'qsa.iq': 'qsa_shared', 'attention': 'out_proj',
                'shexpgate': 'shared_expert', 'shexpup': 'shared_expert', 'shexpdown': 'shared_expert',
                'hc.a.low': 'hc_gemv', 'hc.f.low': 'hc_gemv', 'hc.a.gate': 'hc_gemv', 'hc.f.gate': 'hc_gemv',
                'logits': 'head_rows'}.get(name, 'replicated')
    return {'gdn': 'gdn_head', 'gdn_norm_gate': 'gdn_head', 'qsa_attention': 'qsa_head', 'qsa_prepare': 'qsa_head',
            'qsa_select': 'qsa_shared', 'qsa_append_pool': 'qsa_shared', 'argmax': 'head_rows'}.get(name, 'replicated')


def class_totals(sites, t1_us, layers, gdn_layers):
    """Per-class (us, launches). conv: GDN layers' share is head-local, the rest (PLE conv) replicated.
    silu_product: half routed activation, half shared-expert activation (equal launch counts)."""
    tot = collections.defaultdict(lambda: [0.0, 0])
    per_site = []
    for s, v in sites.items():
        us, n = v['us'], v['launches']
        if s == 'conv':
            g = us * gdn_layers / n
            parts = [('gdn_head', g, gdn_layers), ('replicated', us - g, n - gdn_layers)]
        elif s == 'silu_product':
            parts = [('routed', us / 2, n // 2), ('shared_expert', us / 2, n - n // 2)]
        else:
            parts = [(classify(s), us, n)]
        for c, u, k in parts:
            tot[c][0] += u; tot[c][1] += k
        per_site.append({'site': s, 'launches': n, 'us': us, 'class': '+'.join(sorted({p[0] for p in parts}))})
    busy = sum(v['us'] for v in sites.values())
    tot['other'] = [max(0.0, t1_us - busy), 0]
    return {c: {'us': round(u, 1), 'launches': k} for c, (u, k) in tot.items()}, sorted(per_site, key=lambda r: -r['us']), busy


# ---------------------------------------------------------------- timing model
def split_time(us, launches, scen):
    """Critical-card time of a row/head-split site."""
    if scen['dense'] == 'ideal':
        return us / 2
    if scen['dense'] == 'fixed':
        f = min(F_LAUNCH_US * launches, us)
        return f + (us - f) / 2
    return us * (1 - scen['eta_cons'] / 2)  # conservative: same efficiency as the measured expert split


def slot_t(frac, a):
    return 0.0 if frac <= 0 else a + (1 - a) * frac


def moe_time(routed, shared, a, shared_mode, k_fixed=None):
    """Critical-card MoE time. shared_mode: 'rep' (both cards), 'unit' (one card)."""
    best = None
    for k in ([k_fixed] if k_fixed is not None else range(0, 11)):
        ta, tb = slot_t(k / 10, a) * routed, slot_t((10 - k) / 10, a) * routed
        if shared_mode == 'rep':
            c = max(ta, tb) + shared
        else:
            c = max(ta, tb + shared)
        if best is None or c < best[0]:
            best = (c, k)
    return best


LAYOUTS = {
    'O1_slot_only': dict(split=[], routed='slot', shared='rep', n=1, head=False,
                         desc='Oct-25 measured best: experts by slot 5/5, one gather per layer, all else replicated'),
    'O2_slot_attn_qkv': dict(split=['out_proj', 'qkv_only'], routed='slot', shared='rep', n=None, head=False,
                             desc='Oct-25 built pieces combined: slot experts + row-split attention and gdn.qkv, '
                                  'one gather per split site'),
    'H_head_split': dict(split=['gdn_head', 'qsa_head', 'out_proj'], routed='slot', shared='unit', n=3, head=True,
                         desc='asked layout: GDN heads, QSA KV groups, out-proj rows, slots + shared unit; 3 exchanges'),
    'H2_no_outproj': dict(split=['gdn_head', 'qsa_head'], routed='slot', shared='unit', n=2, head=True,
                          desc='as H but the out-projection replicated after the head gather; 2 exchanges'),
    'H_plus_HC': dict(split=['gdn_head', 'qsa_head', 'out_proj', 'hc_gemv'], routed='slot', shared='unit', n=7,
                      head=True, desc='H plus HC low/gate row splits; 2 extra exchanges per HC block = 7'),
}
SCEN = {
    'ideal': dict(dense='ideal', a=0.0, o_rep=0.0, eta_cons=None,
                  desc='user model: every split halves exactly, no replication overhead'),
    'calibrated': dict(dense='fixed', a=None, o_rep=None, eta_cons=None,
                       desc='Oct-25 calibration: expert slot efficiency and replicate overhead measured; dense/head '
                            'sites halve except a 5 us fixed launch cost'),
    'conservative': dict(dense='cons', a=None, o_rep=None, eta_cons=None,
                         desc='every split site realises only the measured expert efficiency'),
}


def project(cls, layout, scen, g_us, layers, qkv_only_us=None, qkv_only_launches=0, k_fixed=None):
    lay = LAYOUTS[layout]
    t = 0.0
    split_keys = set(lay['split'])
    for c, v in cls.items():
        if c in ('routed', 'shared_expert'):
            continue
        if c == 'head_rows':
            t += split_time(v['us'], v['launches'], scen) if lay['head'] else v['us']
            continue
        if c in split_keys:
            t += split_time(v['us'], v['launches'], scen)
        else:
            t += v['us']
    n_ex = lay['n'] * layers if lay['n'] is not None else 0
    if 'qkv_only' in split_keys:  # O2: the Q6_K gdn.qkv sites move from replicated to split, one gather each
        t += split_time(qkv_only_us, qkv_only_launches, scen) - qkv_only_us
        n_ex = cls['out_proj']['launches'] + qkv_only_launches + layers
    if lay['head'] and cls.get('head_rows', {}).get('us', 0) > 0:
        n_ex += 1
    mt, k = moe_time(cls['routed']['us'], cls.get('shared_expert', {'us': 0})['us'], scen['a'], lay['shared'], k_fixed)
    t += mt
    t += n_ex * g_us + scen['o_rep'] * 1000
    return t / 1000, n_ex, k


def main():
    (b0, b0m), (r1, r1m), (ca, cam) = load_profiles()
    # -------- Oct-25 measurements (steady medians, halves 3..16)
    tp = {}
    for name, f in [('one_card', 'step2b-pf84-one-card-summary.json'), ('replicated', 'step2b-pf84-tp-replicate-summary.json'),
                    ('attn_qkv_split', 'step3-pf87-split-attention-qkv-summary.json'),
                    ('id_pull', 'step4-pf88-tp-e1-summary.json'), ('id_pull_plus_attn', 'step4-pf88-tp-e2-summary.json'),
                    ('id_push', 'step4b-pf90-tp-y-1-summary.json'), ('gather_only_push', 'step4b-pf90-tp-y-gather-summary.json'),
                    ('slot', 'step4c-pf91-slot-summary.json')]:
        tp[name] = round(st.median(json.load(open(os.path.join(SRC['tp_evidence'], f)))['half_ms'][2:]), 3)
    # -------- calibration profile classes (rank 1, 25 layers, 18 GDN)
    t1c = tp['one_card'] * 1000
    ccls, csites, cbusy = class_totals(ca, t1c, 25, 18)
    attn_us, attn_n = ca['gemv:Q8_0:attention']['us'], ca['gemv:Q8_0:attention']['launches']
    q6_us, q6_n = ca['gemv:Q6_K:gdn.qkv']['us'], ca['gemv:Q6_K:gdn.qkv']['launches']
    routed_gemv_us = sum(v['us'] for s, v in ca.items() if s.startswith('routed_gemv:'))
    o_rep = tp['replicated'] - tp['one_card']
    g_exp = (tp['gather_only_push'] - tp['replicated']) / 25 * 1000
    gross_slot = tp['replicated'] + g_exp * 25 / 1000 - tp['slot']
    t_half = 1 - gross_slot * 1000 / routed_gemv_us          # slot_t(0.5)
    a = 2 * t_half - 1                                       # fixed fraction of a routed launch
    eta_exp = 1 - a
    pred_id_push = tp['gather_only_push'] - (1 - slot_t(ROUTE_BY_ID_BUSIEST / 10, a)) * routed_gemv_us / 1000
    l2_gross = tp['replicated'] - tp['attn_qkv_split']       # = saving - 33 g
    ideal_save_l2 = (attn_us + q6_us) / 2
    fixed_save_l2 = ((attn_us - F_LAUNCH_US * attn_n) + (q6_us - F_LAUNCH_US * q6_n)) / 2
    n_l2 = attn_n + q6_n
    calib = {
        'source_profile': SRC['calib_profile_origin'], 'source_profile_meta': cam,
        'calib_profile_busy_us': round(cbusy, 1),
        'note_t1': 'TP one-card 16.732 ms was at positions 2-15 with no prompt; the profile is at positions 302-347. '
                   'Only context-independent sites (attention, Q6_K qkv, routed experts) enter the deltas.',
        'S_L2_attention_plus_q6k_qkv_us': round(attn_us + q6_us, 1), 'L2_split_sites': n_l2,
        'per_site_us': {'attention': round(attn_us / attn_n, 1), 'q6k_qkv': round(q6_us / q6_n, 1)},
        'S_L3_routed_gemv_us': round(routed_gemv_us, 1),
        'O_rep_ms_measured': round(o_rep, 3), 'g_expert_push_us_measured': round(g_exp, 1),
        'slot_gross_saving_ms': round(gross_slot, 3), 'slot_half_time_fraction': round(t_half, 3),
        'eta_expert_slot': round(eta_exp, 3), 'fixed_fraction_a': round(a, 3),
        'check_id_push_predicted_ms': round(pred_id_push, 3), 'check_id_push_measured_ms': tp['id_push'],
        'L2_net_ms_measured': round(l2_gross, 3),
        'L2_implied_g_if_ideal_us': round((ideal_save_l2 / 1000 - l2_gross) / n_l2 * 1000, 1),
        'L2_implied_g_if_fixed5_us': round((fixed_save_l2 / 1000 - l2_gross) / n_l2 * 1000, 1),
        'L2_implied_eta_if_g13': round((l2_gross + n_l2 * 0.013) / (ideal_save_l2 / 1000), 3),
    }
    # naive-model errors for the measured arms (ideal halving, O_rep=0)
    def naive(arm, g):
        if arm == 'replicated':
            return tp['one_card']
        if arm == 'attn_qkv_split':
            return tp['one_card'] - ideal_save_l2 / 1000 + n_l2 * g / 1000
        if arm == 'slot':
            return tp['one_card'] - routed_gemv_us / 2000 + 25 * g / 1000
        if arm == 'id_push':
            return tp['one_card'] - routed_gemv_us * (1 - ROUTE_BY_ID_BUSIEST / 10) / 1000 + 25 * g / 1000
    errs = []
    for arm, g in [('replicated', 0), ('attn_qkv_split', 13), ('slot', 26), ('id_push', 26)]:
        p = naive(arm, g)
        errs.append({'arm': arm, 'g_us': g, 'measured_ms': tp[arm], 'naive_predicted_ms': round(p, 3),
                     'error_ms': round(p - tp[arm], 3)})
    for arm, g in [('slot', 26), ('id_push', 26)]:
        p = naive(arm, g) + o_rep
        errs.append({'arm': arm + '+O_rep', 'g_us': g, 'measured_ms': tp[arm], 'naive_predicted_ms': round(p, 3),
                     'error_ms': round(p - tp[arm], 3)})
    calib['naive_model_errors'] = errs
    SCEN['calibrated'].update(a=a, o_rep=o_rep)
    SCEN['conservative'].update(a=a, o_rep=o_rep, eta_cons=eta_exp)
    # out-of-sample checks on the pull-gather arms. Pull gather-only 18.15 ms is design-doc text
    # (research/2026-10-24-exact-multicard-design.md, step 4b table), not an evidence/ file.
    g_pull = (18.15 - tp['replicated']) / 25 * 1000
    id_save = (1 - slot_t(ROUTE_BY_ID_BUSIEST / 10, a)) * routed_gemv_us / 1000
    p_e1 = tp['replicated'] + 25 * g_pull / 1000 - id_save
    p_e2 = p_e1 + (tp['attn_qkv_split'] - tp['replicated'])
    calib['checks_out_of_sample'] = [
        {'arm': 'id_push (pf90)', 'predicted_ms': round(pred_id_push, 3), 'measured_ms': tp['id_push'],
         'error_ms': round(pred_id_push - tp['id_push'], 3)},
        {'arm': 'id_pull (pf88 e1), g_pull from 18.15 doc text', 'g_pull_us': round(g_pull, 1),
         'predicted_ms': round(p_e1, 3), 'measured_ms': tp['id_pull'], 'error_ms': round(p_e1 - tp['id_pull'], 3)},
        {'arm': 'id_pull + attn/qkv split (pf88 e2), additive', 'predicted_ms': round(p_e2, 3),
         'measured_ms': tp['id_pull_plus_attn'], 'error_ms': round(p_e2 - tp['id_pull_plus_attn'], 3)}]
    # replay of the slot arm through the projection code (routed activation now also split by slot)
    SCEN['calibrated'].update(a=a, o_rep=o_rep)
    rep_t2, _, _ = project(ccls, 'O1_slot_only', SCEN['calibrated'], g_exp, 25)
    calib['replay_slot_arm_through_projection_ms'] = round(rep_t2, 3)
    # -------- B19 rank 0 and rank 1
    out = {'schema': 'ownrt.within-layer-sizing.v1', 'date': '2026-10-28', 'cpu_only': True,
           'inputs': {k: (REL(v) if isinstance(v, str) and v.startswith('/home') else v) for k, v in SRC.items()},
           't1': {k: {'value': v[0], 'source': v[1]} for k, v in T1.items()},
           'tp_oct25_steady_medians_ms': tp, 'f_launch_us': F_LAUNCH_US,
           'class_doc': CLASS_DOC, 'layouts': {k: v['desc'] for k, v in LAYOUTS.items()},
           'scenarios': {k: v['desc'] for k, v in SCEN.items()}, 'calibration': calib, 'ranks': {}}
    for rank, sites, meta, t1, layers, gdn in [('rank0', b0, b0m, T1['b19_rank0'][0], 23, 18),
                                               ('rank1', r1, r1m, T1['b19_rank1'][0], 25, 18)]:
        cls, per_site, busy = class_totals(sites, t1 * 1000, layers, gdn)
        head_split = {'gdn_head', 'qsa_head', 'out_proj', 'routed', 'shared_expert', 'head_rows'}
        S = sum(v['us'] for c, v in cls.items() if c in head_split)
        S_rows = S - cls.get('shared_expert', {'us': 0})['us']
        rec = {'profile_meta': meta, 'profile_busy_us': round(busy, 1), 'T1_ms': t1, 'layers': layers,
               'classes': cls, 'sites': per_site,
               'S_head_split_us': round(S, 1), 'S_split_excluding_shared_unit_us': round(S_rows, 1),
               'shared_expert_unit_us': cls.get('shared_expert', {'us': 0})['us'],
               'R_head_split_us': round(t1 * 1000 - S, 1),
               'S_share': round(S / t1 / 1000, 3), 'table': {}}
        q6 = sites.get('gemv:Q6_K:gdn.qkv', {'us': 0, 'launches': 0})
        for lay in LAYOUTS:
            for sc in SCEN:
                row = {}
                for g in G_GRID:
                    t2, n_ex, k = project(cls, lay, SCEN[sc], g, layers, q6['us'], q6['launches'])
                    row[str(g)] = {'T2_ms': round(t2, 3), 'speedup': round(t1 / t2, 3), 'exchanges': n_ex, 'routed_split': f'{k}/{10-k}'}
                fixed = {}
                if lay.startswith('H'):
                    t2, n_ex, _ = project(cls, lay, SCEN[sc], 5, layers, k_fixed=5)
                    fixed = {'T2_ms_g5_routed_5_5_shared_on_one_card': round(t2, 3)}
                # break-even g: T2(g)=T1 and g for a 15% gain (T2 linear in g)
                t0, n0, _ = project(cls, lay, SCEN[sc], 0, layers, q6['us'], q6['launches'])
                be = (t1 - t0) / n0 * 1000 if n0 else None
                g15 = (t1 / 1.15 - t0) / n0 * 1000 if n0 else None
                s_all = sum(v['us'] for c, v in cls.items() if c in head_split | ({'hc_gemv'} if 'HC' in lay else set()))
                eta_eff = (t1 + SCEN[sc]['o_rep'] - t0) * 1000 / (s_all / 2) if lay.startswith('H') else None
                rec['table'][f'{lay}|{sc}'] = {'by_g_us': row, 'break_even_g_us': round(be, 1) if be is not None else None,
                                               'g_for_15pct_us': round(g15, 1) if g15 is not None and g15 >= 0 else None,
                                               'realised_fraction_of_S_over_2': round(eta_eff, 3) if eta_eff else None,
                                               **fixed}
        # share of T1 that must be splittable for >=15% at g=5, n=3: s >= 2*(1-1/1.15 + X/T1)/eta,
        # X = exchanges + replication overhead, eta = realised fraction of S/2 for layout H in that scenario
        need = {}
        for sc in SCEN:
            eta = rec['table'][f'H_head_split|{sc}']['realised_fraction_of_S_over_2']
            x = layers * 3 * 0.005 + SCEN[sc]['o_rep']
            need[sc] = {'eta': eta, 'X_ms': round(x, 3), 'share_needed': round(2 * (t1 * (1 - 1 / 1.15) + x) / (eta * t1), 3),
                        'share_available_H': rec['S_share']}
        rec['share_needed_for_15pct_g5_n3'] = need
        out['ranks'][rank] = rec
    # -------- tok/s (four cards, TP2 per stage), proportional scaling = upper bound
    d0, base = T1['b19_rank0_draft'][0], max(T1['b19_rank0'][0] + T1['b19_rank0_draft'][0], T1['b19_rank1'][0])
    toks = {}
    for lay in ('O1_slot_only', 'H_head_split', 'H_plus_HC'):
        for sc in SCEN:
            k = f'{lay}|{sc}'
            r0 = out['ranks']['rank0']['table'][k]['by_g_us']['5']['T2_ms']
            r1t = out['ranks']['rank1']['table'][k]['by_g_us']['5']['T2_ms']
            cyc = max(r0 + d0, r1t)
            toks[k] = {'rank0_half_ms': r0, 'rank1_half_ms': r1t, 'cycle_ms': round(cyc, 3),
                       'toks_upper_bound': round(T1['b19_toks'][0] * base / cyc, 2)}
    out['toks_g5_four_cards'] = {'baseline_cycle_ms': round(base, 3), 'draft_ms_unsplit': d0,
                                 'note': 'tok/s scaled by max(stage) only; per-position controller and hand-off '
                                         'time do not shrink, so these are upper bounds', 'rows': toks}
    # host submission floor (one thread drives both cards)
    host = json.load(open(os.path.join(HERE, 'evidence', 'b19-rank0-unprofiled-host-timings.json')))
    enq = st.median(v['enqueue_loop_ms_median'] for v in host['runs'].values())
    ex_submit = 69 * 2 * 6.7 / 1000  # rank-0 H exchanges x (push + wait) x 6.7 us per cross-queue submit
    out['host_floor'] = {'b19_rank0_enqueue_ms_one_card': round(enq, 3), 'launches_per_half': 863,
                         'one_thread_two_cards_ms_scaled_from_oct25': round(7.4 * 863 / 758, 2),
                         'two_threads_ms': round(863 * 5.32 / 1000, 2),
                         'H_exchange_submits_per_card_ms': round(ex_submit, 2),
                         'one_thread_total_ms': round(7.4 * 863 / 758 + 2 * ex_submit, 2),
                         'two_threads_total_ms': round(863 * 5.32 / 1000 + ex_submit, 2),
                         'sources': ['evidence/b19-rank0-unprofiled-host-timings.json',
                                     'research/2026-10-24-exact-multicard-design.md (7.4 ms one thread at ~758 '
                                     'launches/card; 5.32 us per pair with two threads; 6.7 us per submit with a '
                                     'cross-queue dependency)']}
    json.dump(out, open(os.path.join(HERE, 'sizing.json'), 'w'), indent=1)
    return out


if __name__ == '__main__':
    o = main()
    c = o['calibration']
    print(json.dumps({k: c[k] for k in c if k not in ('naive_model_errors', 'checks_out_of_sample')}, indent=1))
    for e in c['naive_model_errors'] + c['checks_out_of_sample']:
        print(e)
    for rank in ('rank0', 'rank1'):
        r = o['ranks'][rank]
        print(rank, 'T1', r['T1_ms'], 'S', r['S_head_split_us'], 'R', r['R_head_split_us'], 'share', r['S_share'], 'need15', r['share_needed_for_15pct_g5_n3'])
        for c2, v in sorted(r['classes'].items(), key=lambda x: -x[1]['us']):
            print('   %-14s %8.1f %4d' % (c2, v['us'], v['launches']))
        for k, v in r['table'].items():
            print('  %-34s be=%-7s ' % (k, v['break_even_g_us']) + ' '.join('%s:%.2f(%.3fx,%d,%s)' % (g, x['T2_ms'], x['speedup'], x['exchanges'], x['routed_split']) for g, x in v['by_g_us'].items()), {k2: v2 for k2, v2 in v.items() if k2.startswith('T2_ms_g5') or k2 in ('g_for_15pct_us', 'realised_fraction_of_S_over_2')})
    print(json.dumps(o['toks_g5_four_cards'], indent=1))
    print(o['host_floor'])
