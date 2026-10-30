#!/usr/bin/env python3
"""Site x M table, roofline, glue census and tok/s projection (research/decode-site-census-2026-10-30). CPU only.

  python3 -B census.py            reads results/rank{0,1}-sites.json, results/rank{0,1}-routes.json,
                                  results/token-wall.json, results/tp-roles.json; writes results/census.json and prints tables

Every input number is a measurement in results/ (device time from the OWNRT_SITE_TRACE runs, routes from the route-dump
runs, host overheads from the unprofiled runs) or a cited lab record (acceptance); everything computed here is labelled
'projection' in the output."""
import json, statistics
from pathlib import Path

import weights as WT

HERE = Path(__file__).resolve().parent
RES = HERE / 'results'
RUNS = next((p for p in (Path('/dev/shm/decode-census-20261030/runs'),
                         Path('/mnt/raid-models/ownrt-experiment-archives/2026-10-30/decode-site-census-runs')) if p.exists()),
            Path('/dev/shm/decode-census-20261030/runs'))   # raw runs (archived to the RAID after the census)
ROOF_GBS = 590.0          # measured in this census: the target head (521 MB Q6_K) streams at ~590 GB/s on one B70
RANKS = {0: range(0, 23), 1: range(23, 48)}
EXPERT_ROLES = ('expsgate', 'expsup', 'expsdown')
# roles that already have native multi-row kernels (the prefill path's row loops) and touch per-row state, not weights
STATEFUL = ('gdn.recurrence', 'gdn.conv', 'qsa.attention', 'qsa.select', 'qsa.prepare', 'qsa.pool', 'gdn.gated')


def load(name):
    return json.loads((RES / name).read_text())


def role_bytes_total(role, rank):
    if role.startswith(('ple.', 'final.')) or role in ('logits', 'argmax'):   # one site per rank, not per layer
        b, ty = WT.role_bytes(role, -1)
        return float(b), sorted(set(ty))
    total, types = 0.0, set()
    for layer in RANKS[rank]:
        b, ty = WT.role_bytes(role, layer)
        if role in EXPERT_ROLES:
            b *= 10                    # ten routed experts per row at M = 1
        total += b; types.update(ty)
    return total, sorted(types)


def classify(us, launches, nbytes, launch_us):
    """bandwidth-bound: weight bytes / device time >= 65% of ROOF_GBS; minimum-duration: median launch under 10 us (the
    shortest kernels in the trace take 2-3 us); instruction-bound: reads weights below 65% of the roofline;
    state/latency-bound: no weight tensor (recurrence state, KV, routing, reductions)."""
    gbs = nbytes / (us * 1e3) if us else 0.0
    if nbytes and gbs >= 0.65 * ROOF_GBS:
        return 'bandwidth-bound', gbs
    if launch_us < 10.0:
        return 'minimum-duration (tiny)', gbs
    if nbytes:
        return 'instruction-bound', gbs
    return 'state/latency-bound', gbs


def table(rank, sites):
    """Per role: decode M=1 and prefill-path M=1..4 device us (summed over the rank's layers), ratios, bytes, class."""
    d = sites['modes']['d']['half']['roles']
    pre = {m: sites['modes'][m]['prefill']['roles'] for m in ('1', '2', '3', '4') if m in sites['modes']}
    rows = []
    for role in sorted(set(d) | set().union(*[set(v) for v in pre.values()])):
        t1 = d.get(role, {}).get('us', 0.0)
        n1 = d.get(role, {}).get('launches', 0)
        lu = d.get(role, {}).get('launch_us_median', 0.0)
        nbytes, types = role_bytes_total(role, rank)
        cls, gbs = classify(t1, n1, nbytes, lu) if t1 else ('prefill-only site', 0.0)
        r = dict(role=role, decode_us=t1, decode_launches=n1, launch_us_median=lu, weight_bytes_m1=nbytes, formats=types,
                 decode_gbs=gbs, decode_roofline_fraction=gbs / ROOF_GBS if nbytes else None, decode_class=cls)
        for m, v in pre.items():
            r[f'prefill{m}_us'] = v.get(role, {}).get('us', 0.0)
            r[f'prefill{m}_launches'] = v.get(role, {}).get('launches', 0)
            r[f'prefill{m}_vs_decode1'] = (r[f'prefill{m}_us'] / t1) if t1 else None
        p1 = r.get('prefill1_us', 0.0)
        for m in ('2', '3', '4'):
            if f'prefill{m}_us' in r:
                r[f'prefill{m}_vs_prefill1'] = (r[f'prefill{m}_us'] / p1) if p1 else None
        rows.append(r)
    rows.sort(key=lambda r: -r['decode_us'])
    return rows


def phase_summary(sites, kind_by_mode):
    out = {}
    for m, kind in kind_by_mode.items():
        v = sites['modes'].get(m, {}).get(kind)
        if v:
            out[m] = dict(kind=kind, phases=v['phases'], span_us=v['span_us'], busy_us=v['busy_us'], gap_us=v['gap_us'],
                          max_gap_us=v['max_gap_us'], span_without_max_gap_us=v['span_without_max_gap_us'], events=v['events'],
                          small_launches=v['small']['launches'], small_us=v['small']['us'])
    return out


def expert_join(rank, run_dir, routes):
    """Per (window chunk, layer): summed device us of the three routed expert sites in the traced prefill-path run, joined
    with the distinct experts of the same chunk and layer from the route-dump run; least-squares fit
    t = a + b * distinct + c * rows (rows = M) per mode set. The route-dump run reads the same tokens/rows, so chunk i of
    mode M covers the same positions in both runs."""
    import collections, re
    phases, ev = {}, collections.defaultdict(lambda: collections.defaultdict(float))
    with open(Path(run_dir) / f'rank{rank}' / 'site-trace.jsonl') as f:
        for line in f:
            d = json.loads(line)
            if 'phase' in d:
                phases[d['phase']] = d
            else:
                m = re.match(r'^blk\.(\d+)\.(expsgate|expsup|expsdown)$', d['c'])
                if m:
                    ev[d['p']][int(m.group(1))] += (d['e'] - d['s']) / 1000.0
    s = json.loads((Path(run_dir) / 'summary.json').read_text())
    K = s['prefix']
    pts = []
    for mode, v in routes.items():
        M = int(mode)
        chunk_phases = sorted((p for p, d in phases.items() if d['kind'] == 'prefill' and d['rows'] == M and d['position'] >= K),
                              key=lambda p: p)
        for i, (p, ch) in enumerate(zip(chunk_phases, v['per_chunk_layer'])):
            if phases[p]['position'] < K + 8:
                continue
            for layer, distinct in ch.items():
                if int(layer) in ev[p]:
                    pts.append((M, distinct, ev[p][int(layer)]))
    # least squares with numpy-free normal equations (3 unknowns)
    def fit(points):
        X = [(1.0, d, m) for m, d, _ in points]; y = [t for *_, t in points]
        A = [[sum(x[i] * x[j] for x in X) for j in range(3)] for i in range(3)]
        bvec = [sum(x[i] * t for x, t in zip(X, y)) for i in range(3)]
        n = 3
        for c in range(n):
            piv = max(range(c, n), key=lambda r: abs(A[r][c])); A[c], A[piv] = A[piv], A[c]; bvec[c], bvec[piv] = bvec[piv], bvec[c]
            for r in range(n):
                if r != c and A[c][c]:
                    f = A[r][c] / A[c][c]
                    A[r] = [a - f * b for a, b in zip(A[r], A[c])]; bvec[r] -= f * bvec[c]
        coef = [bvec[i] / A[i][i] for i in range(n)]
        res = [t - (coef[0] + coef[1] * d + coef[2] * m) for m, d, t in points]
        return dict(a_us=coef[0], per_distinct_expert_us=coef[1], per_row_us=coef[2], points=len(points),
                    rms_us=(sum(r * r for r in res) / len(res)) ** 0.5)
    by_m = collections.defaultdict(list)
    for m, d, t in pts:
        by_m[m].append((d, t))
    return dict(fit=fit(pts) if len(pts) > 10 else None,
                per_mode={str(m): dict(points=len(v), mean_distinct=statistics.fmean(d for d, _ in v),
                                       mean_us_per_layer=statistics.fmean(t for _, t in v)) for m, v in sorted(by_m.items())})


HEAD_ROLES = ('final.norm', 'final.low', 'final.gate', 'final.mix', 'final.act', 'final.inject', 'logits', 'argmax')
# Acceptance (cited lab records, not measured here): a1 = 76.1% of guesses on the 12-prompt suite (four-card service,
# research/tp/miss-stall-2026-10-29/ANALYSIS.md); conditional a2 = 0.718 given an accepted first guess (packet66 depth-2
# probe as used by stage2/packet71c-depth2-engine/DESIGN.md, a1 = 0.787 there, older UD-IQ3_XXS lane); a3: no record,
# assumed equal to a2; top-2 at the first position rescues 48.3% of misses (stage2/packet96-dual-guess-model/DECISION.md:
# packet31 top-1 77.34%, top-2 88.28%, CPU draft reference), applied to a1: 0.761 + 0.483 * 0.239 = 0.876.
A1, A2, A3 = 0.761, 0.718, 0.718
TOP2 = A1 + (28 / 58) * (1 - A1)


# Four-card layout (tptsxqc record): roles split between the two cards of a stage; every other role is replicated
# (source mapping: stage TP transform in state-bundle/build/source-v4/rank.hpp:700-942, see RESULT.md)
TP_SPLIT = {'gdn.qkv', 'gdn.z', 'gdn.a', 'gdn.conv', 'gdn.recurrence', 'gdn.gated', 'attention', 'qsa.qgate', 'qsa.k', 'qsa.v',
            'qsa.attention', 'expsgate', 'expsup', 'expsact', 'expsdown', 'expsdown.check', 'logits', 'argmax'}
RECORD_FOUR_CARD = dict(tok_s=78.29, hit_cycle_ms=10.82, miss_ms=10.08,
                        source='research/tp/fault-ladder-2026-10-29/RESULT.md; research/tp/miss-stall-2026-10-29/ANALYSIS.md')
RECORD_TWO_CARD_TOK_S = 66.42


def components(c, routes, rank, M, glue=1.0, experts=1.0, ideal_state=True):
    """Device ms of one rank's target pass over M rows under ideal multi-row kernels, split into TP-split and
    TP-replicated parts. Dense/glue roles cost their one-row time (weight-stationary, one launch for all rows); routed
    experts cost their one-row time x distinct(M)/10; recurrence/attention-like roles their measured native multi-row
    ratio; head: one-row head + (M-1) argmax. glue scales every minimum-duration role (idea #3), experts every expert role
    (idea #4)."""
    roles = c[f'rank{rank}']['roles']
    dist = 10.0 if M == 1 else routes[rank][str(M)]['distinct_mean']
    split = rep = 0.0
    for r in roles:
        role, t = r['role'], r['decode_us'] / 1000.0
        if not t:
            continue
        if role in EXPERT_ROLES:
            t *= dist / 10.0 * experts
        elif role in STATEFUL and ideal_state and M > 1:
            t *= r.get(f'prefill{M}_vs_prefill1') or 1.0
        elif role == 'argmax':
            t *= M
        if r['decode_class'].startswith('minimum-duration') and role not in EXPERT_ROLES:
            t *= glue
        if role in TP_SPLIT:
            split += t
        else:
            rep += t
    gaps = (c[f'rank{rank}']['phases']['d']['span_us'] - c[f'rank{rank}']['phases']['d']['busy_us']) / 1000.0 if rank == 0 else \
        (c['rank1']['phases']['d']['span_without_max_gap_us'] - c['rank1']['phases']['d']['busy_us']) / 1000.0
    return dict(split=split, replicated=rep, gaps=gaps, distinct=dist)


def projection(c, routes, walls):
    """tok/s projections (CPU arithmetic over the measured tables; acceptance from cited records)."""
    w = {x['rank']: x for x in walls if not x['trace']}
    W0, W1, Wdr = w[0]['modes']['d']['half_ms'], w[1]['modes']['d']['half_ms'], w[0]['modes']['d']['draft_ms']
    D0 = c['rank0']['phases']['d']['span_us'] / 1000.0
    D1 = c['rank1']['phases']['d']['span_without_max_gap_us'] / 1000.0
    o0, o1 = W0 - D0, W1 - D1                      # host/sync overhead per call: unprofiled wall - device span
    Ddr = c['rank0']['draft']['draft_head']['span_us'] / 1000.0
    odr = Wdr - Ddr
    # today's two-card pipeline (one guess): hit cycle = max(rank-0 half + draft, rank-1 half); a miss adds a rank-0 redo
    # and the 0.55 ms rollback (miss-stall ANALYSIS)
    hit = max(W0 + Wdr, W1)
    today2 = 1000.0 / (hit + (1 - A1) * (W0 + 0.55))
    # four-card calibration: per-stage TP overhead = record hit cycle - modelled TP2 rank-0 stage (split/2 + replicated
    # + gaps + host overhead + draft, the draft on card 0 as recorded)
    c0 = components(c, routes, 0, 1, ideal_state=False)
    tp_x = RECORD_FOUR_CARD['hit_cycle_ms'] - (c0['split'] / 2 + c0['replicated'] + c0['gaps'] + o0 + Wdr)

    tiles = {r: load(f'rank{r}-tiles.json') for r in (0, 1) if (RES / f'rank{r}-tiles.json').exists()}
    H1 = sum(x['decode_us'] for x in c['rank1']['roles'] if x['role'] in HEAD_ROLES) / 1000.0

    def best_tiles(rank, M, tp):
        # existing exact kernels with the best measured tile per site (results/rank<r>-tiles.json); the head has no
        # multi-row kernel, so rank 1 runs it once per row; decode gaps and host overhead as at M = 1
        if M == 1:
            return None
        rows = [x for x in tiles[rank]['sites'] if x['rows'] == M]
        split = sum(x['best_us'] for x in rows if x['role'] in TP_SPLIT) / 1000.0
        rep = sum(x['best_us'] for x in rows if x['role'] not in TP_SPLIT) / 1000.0
        k = components(c, routes, rank, 1, ideal_state=False)
        head = M * H1 if rank == 1 else 0.0
        o = o0 if rank == 0 else o1
        return (split / 2 + rep + head * (0.5 if tp else 1.0) + k['gaps'] + o + tp_x) if tp else (split + rep + head + k['gaps'] + o)

    def stage(rank, M, tp, glue, experts, ideal_kernels=True, existing_best=False):
        if existing_best and M > 1:
            return best_tiles(rank, M, tp)
        if not ideal_kernels or existing_best:     # today's kernels: M serial one-row passes
            base = (D0 if rank == 0 else D1) + (o0 if rank == 0 else o1)
            if tp:
                k = components(c, routes, rank, 1, ideal_state=False)
                base = k['split'] / 2 + k['replicated'] + k['gaps'] + (o0 if rank == 0 else o1) + tp_x
            return M * base
        k = components(c, routes, rank, M, glue=glue, experts=experts)
        o = o0 if rank == 0 else o1
        if tp:
            return k['split'] / 2 + k['replicated'] + k['gaps'] + o + tp_x
        return k['split'] + k['replicated'] + k['gaps'] + o

    # (name, verify rows M, draft steps, expected tokens per cycle, probability that every guess is accepted)
    specs = [('one guess (chain depth 1)', 2, 1, 1 + A1, A1), ('chain depth 2', 3, 2, 1 + A1 + A1 * A2, A1 * A2),
             ('chain depth 3', 4, 3, 1 + A1 + A1 * A2 + A1 * A2 * A3, A1 * A2 * A3),
             ('top-2 tree at the first position', 3, 1, 1 + TOP2, TOP2),
             ('top-2 tree + depth 2 on the top-1 branch', 4, 2, 1 + TOP2 + A1 * A2, A1 * A2)]
    levers = [('today kernels (M serial one-row passes)', dict(ideal_kernels=False, glue=1.0, experts=1.0)),
              ('existing exact multi-row kernels, best tile per site', dict(existing_best=True, glue=1.0, experts=1.0)),
              ('#1 ideal multi-row kernels', dict(glue=1.0, experts=1.0)),
              ('#1 + #3 glue halved', dict(glue=0.5, experts=1.0)),
              ('#1 + #3 + #4 experts 2x faster', dict(glue=0.5, experts=0.5)),
              ('#1 + #3 + #4 experts at roofline (3.3x)', dict(glue=0.5, experts=0.3))]
    rows = []
    for layout, tp in (('two cards (PP2)', False), ('four cards (PP2 x TP2)', True)):
        for lname, lv in levers:
            for sname, M, drafts, E, p_all in specs:
                kw = dict(lv)
                t0 = stage(0, M, tp, **kw)
                t1 = stage(1, M, tp, **kw)
                draft = drafts * Wdr
                # rank 0 speculates the next block (computed on the guessed continuation while rank 1 verifies this one): it
                # stays valid only if every guess of this block is accepted AND the next block's first guess (one chain
                # step deeper, acceptance A2) matches rank 1's bonus token; otherwise rank 0 redoes the block and its drafts
                p_valid = p_all * A2
                piped_redo = max(t0 + draft, t1) + (1 - p_valid) * (t0 + draft)
                serial = t0 + t1 + draft
                piped_draft_on_rank0 = max(t0 + draft, t1)
                piped_draft_separate = max(t0, t1, draft)
                rows.append(dict(layout=layout, levers=lname, speculation=sname, rows=M, draft_steps=drafts, tokens_per_cycle=E,
                                 rank0_ms=t0, rank1_ms=t1, drafts_ms=draft, serial_tok_s=1000 * E / serial,
                                 pipelined_with_redo_tok_s=1000 * E / piped_redo, next_block_valid_probability=p_valid,
                                 pipelined_tok_s=1000 * E / piped_draft_on_rank0, pipelined_separate_draft_tok_s=1000 * E / piped_draft_separate))
    # Idea #5, one stage over all four cards (TP4): no pipeline, so a rejected guess costs nothing beyond its rows; every
    # layer's split work over four cards, replicated work on each card, both halves in series. TP exchange cost: twice the
    # calibrated per-stage TP2 overhead (both halves' exchanges, assumed no dearer with four parties) and, as a floor, zero.
    def tp4(M, glue, experts, ideal_kernels=True, x=1.0):
        if not ideal_kernels:
            k0, k1 = components(c, routes, 0, 1, ideal_state=False), components(c, routes, 1, 1, ideal_state=False)
            base = (k0['split'] + k1['split']) / 4 + k0['replicated'] + k1['replicated'] + k0['gaps'] + k1['gaps'] + max(o0, o1) + x * 2 * tp_x
            return M * base
        k0, k1 = components(c, routes, 0, M, glue=glue, experts=experts), components(c, routes, 1, M, glue=glue, experts=experts)
        return (k0['split'] + k1['split']) / 4 + k0['replicated'] + k1['replicated'] + k0['gaps'] + k1['gaps'] + max(o0, o1) + x * 2 * tp_x
    for lname, lv in levers:
        if lv.get('existing_best'):
            continue
        for sname, M, drafts, E, p_all in [('no speculation (target only)', 1, 0, 1.0, 1.0)] + specs:
            kw = dict(lv)
            for xname, x in (('exchange 2 x TP2 calibrated', 1.0), ('exchange free (floor)', 0.0)):
                t = tp4(M, kw['glue'], kw['experts'], kw.get('ideal_kernels', True), x)
                rows.append(dict(layout='four cards (TP4, one stage)', exchange=xname, levers=lname, speculation=sname, rows=M,
                                 draft_steps=drafts, tokens_per_cycle=E, stage_ms=t, drafts_ms=drafts * Wdr,
                                 serial_tok_s=1000 * E / (t + drafts * Wdr)))
    sweep = []
    for a in (0.70, 0.761, 0.80, 0.85, 0.90, 0.95):  # every chain position at acceptance a
        for d in (1, 2, 3):
            E = sum(a ** i for i in range(d + 1))
            for layout, tp in (('two cards (PP2)', False), ('four cards (PP2 x TP2)', True)):
                t0, t1 = stage(0, d + 1, tp, glue=0.5, experts=0.5), stage(1, d + 1, tp, glue=0.5, experts=0.5)
                p_valid = a ** (d + 1)
                sweep.append(dict(acceptance=a, depth=d, layout=layout, levers='#1 + #3 + #4 (2x)', tokens_per_cycle=E,
                                  pipelined_tok_s=1000 * E / max(t0 + d * Wdr, t1), serial_tok_s=1000 * E / (t0 + t1 + d * Wdr),
                                  pipelined_with_redo_tok_s=1000 * E / (max(t0 + d * Wdr, t1) + (1 - p_valid) * (t0 + d * Wdr))))
    return dict(label='projection: CPU arithmetic over the measured per-site device times, host overheads and route counts; '
                      'acceptance from cited lab records; not a measurement',
                inputs=dict(rank0_half_wall_ms=W0, rank1_half_wall_ms=W1, draft_wall_ms=Wdr, rank0_device_ms=D0, rank1_device_ms=D1,
                            draft_device_ms=Ddr, rank0_overhead_ms=o0, rank1_overhead_ms=o1, draft_overhead_ms=odr,
                            tp2_overhead_ms_calibrated=tp_x, a1=A1, a2=A2, a3_assumed=A3, top2=TOP2,
                            distinct={r: {m: (10.0 if m == 1 else routes[r][str(m)]['distinct_mean']) for m in (1, 2, 3, 4)} for r in (0, 1)}),
                today=dict(two_card_model_tok_s=today2, two_card_measured_tok_s=RECORD_TWO_CARD_TOK_S, hit_cycle_ms=hit,
                           four_card_record=RECORD_FOUR_CARD),
                scenarios=rows, acceptance_sweep=sweep)


WEIGHTLESS_GLUE = ('norm', 'act', 'mix', 'combine', 'moe', 'gather', 'check', 'route', 'gated', 'conv', 'prepare', 'pool',
                   'select', 'begin', 'commit', 'streams', 'ple.hash', 'ple.add', 'ple.gated', 'ple.conv', 'ple.kn', 'ple.cn', 'ple.qn')


def glue(c, sites):
    """Kernels under 20 us per decode half (and per draft step): count, summed us, by role; which of them the four-card
    layout replicates on both cards of a stage."""
    out = {}
    for rank in (0, 1):
        h = sites[rank]['modes']['d']['half']
        small = h['small']['roles']
        roles = {r['role']: r for r in c[f'rank{rank}']['roles']}
        rows = []
        for role, v in sorted(small.items(), key=lambda x: -x[1]['us']):
            weight = roles.get(role, {}).get('weight_bytes_m1', 0) > 0
            rows.append(dict(role=role, launches=v['launches'], us=v['us'], has_weights=weight,
                             kind='small weight GEMV' if weight else 'weightless glue',
                             four_card='split' if role in TP_SPLIT else 'replicated on both cards'))
        tot = lambda f: (sum(r['launches'] for r in rows if f(r)), sum(r['us'] for r in rows if f(r)))
        out[f'rank{rank}'] = dict(
            half_busy_us=h['busy_us'], half_launches=h['events'], small_launches=h['small']['launches'], small_us=h['small']['us'],
            weightless=tot(lambda r: not r['has_weights']), small_gemv=tot(lambda r: r['has_weights']),
            replicated_small=tot(lambda r: r['four_card'] != 'split'), split_small=tot(lambda r: r['four_card'] == 'split'),
            replicated_all_us=sum(r['decode_us'] for r in c[f'rank{rank}']['roles'] if r['role'] not in TP_SPLIT),
            replicated_all_launches=sum(r['decode_launches'] for r in c[f'rank{rank}']['roles'] if r['role'] not in TP_SPLIT),
            split_all_us=sum(r['decode_us'] for r in c[f'rank{rank}']['roles'] if r['role'] in TP_SPLIT),
            roles=rows)
    dh = sites[0]['modes']['d'].get('draft_head')
    if dh:
        out['draft'] = dict(step_busy_us=dh['busy_us'], launches=dh['events'], small_launches=dh['small']['launches'], small_us=dh['small']['us'])
    return out


def main():
    s0, s1 = load('rank0-sites.json'), load('rank1-sites.json')
    t0, t1 = table(0, s0), table(1, s1)
    out = dict(schema='decode-site-census.v1', roofline_gbs=ROOF_GBS, rank0=dict(roles=t0), rank1=dict(roles=t1))
    km = {'d': 'half', '1': 'prefill', '2': 'prefill', '3': 'prefill', '4': 'prefill'}
    out['rank0']['phases'] = phase_summary(s0, km)
    out['rank1']['phases'] = phase_summary(s1, km)
    out['rank0']['draft'] = {k: s0['modes']['d'][k] | {'sites': None}
                             for k in ('draft_head', 'draft') if k in s0['modes']['d']}
    routes = {0: load('rank0-routes.json'), 1: load('rank1-routes.json')} if (RES / 'rank0-routes.json').exists() else None
    if (RES / 'token-wall.json').exists() and routes:
        out['projection'] = projection(out, routes, load('token-wall.json'))
        out['experts'] = {f'rank{r}': dict(routes={m: {k: v for k, v in routes[r][m].items() if k != 'per_chunk_layer'} for m in routes[r]},
                                            prefill_kernel_fit=expert_join(r, RUNS / ('B0' if r == 0 else 'A1'), routes[r]))
                          for r in (0, 1)}
    out['glue'] = glue(out, {0: s0, 1: s1})
    (RES / 'census.json').write_text(json.dumps(out, indent=1))
    for rank, t in ((0, t0), (1, t1)):
        pass
        print(f'\nrank {rank}: role | decode us (launches) | GB/s | class | prefill M=1..4 us | M/decode1')
        for r in t[:40]:
            pm = ' '.join(f"{r.get(f'prefill{m}_us', 0):7.0f}" for m in '1234')
            rt = ' '.join(f"{(r.get(f'prefill{m}_vs_decode1') or 0):5.2f}" for m in '1234')
            print(f"{r['role']:16s} {r['decode_us']:7.1f} ({r['decode_launches']:3.0f}) {r['decode_gbs']:5.0f} {r['decode_class'][:14]:14s} | {pm} | {rt}")


def markdown():
    c = load('census.json')
    L = []
    for rank in (0, 1):
        L.append(f'\n**Rank {rank}** (layers {"0-22 + draft" if rank == 0 else "23-47 + head"}): device us per decode half, summed over the rank\'s layers\n')
        L.append('| site | M=1 decode us (launches) | us/launch | weight MB | GB/s | class | prefill path M=1 / 2 / 3 / 4 us | t(M)/t_decode(1) M=2 / 3 / 4 | four cards |')
        L.append('| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |')
        for r in c[f'rank{rank}']['roles']:
            if r['decode_us'] < 15:
                continue
            pm = ' / '.join(f"{r.get(f'prefill{m}_us', 0):.0f}" for m in '1234')
            rt = ' / '.join(f"{(r.get(f'prefill{m}_vs_decode1') or 0):.2f}" for m in '234')
            mb = r['weight_bytes_m1'] / 1e6
            L.append(f"| {r['role']} | {r['decode_us']:.0f} ({r['decode_launches']:.0f}) | {r['launch_us_median']:.1f} | {mb:.1f} | "
                     f"{r['decode_gbs']:.0f} | {r['decode_class']} | {pm} | {rt} | {'split' if r['role'] in TP_SPLIT else 'replicated'} |")
    pr = c['projection']
    specs = ['one guess (chain depth 1)', 'chain depth 2', 'chain depth 3', 'top-2 tree at the first position',
             'top-2 tree + depth 2 on the top-1 branch']
    for layout in ('two cards (PP2)', 'four cards (PP2 x TP2)'):
        L.append(f'\n**{layout}**: tok/s as serial verify / pipelined with rank-0 redo on any reject / upper bound (perfect overlap, no miss cost)\n')
        L.append('| kernels and levers | ' + ' | '.join(f'{x} (M={next(r["rows"] for r in pr["scenarios"] if r["speculation"] == x)})' for x in specs) + ' |')
        L.append('| --- |' + ' ---: |' * len(specs))
        for lever in dict.fromkeys(r['levers'] for r in pr['scenarios'] if r['layout'] == layout):
            cells = []
            for sp in specs:
                r = next(r for r in pr['scenarios'] if r['layout'] == layout and r['levers'] == lever and r['speculation'] == sp)
                cells.append(f"{r['serial_tok_s']:.0f} / {r['pipelined_with_redo_tok_s']:.0f} / {r['pipelined_tok_s']:.0f}")
            L.append(f'| {lever} | ' + ' | '.join(cells) + ' |')
    L.append('\n**four cards as one stage (TP4, idea #5)**: serial tok/s (no pipeline, so no miss cost), exchanges at 2x the calibrated TP2 cost / free\n')
    sp4 = ['no speculation (target only)'] + specs
    L.append('| kernels and levers | ' + ' | '.join(sp4) + ' |')
    L.append('| --- |' + ' ---: |' * len(sp4))
    for lever in dict.fromkeys(r['levers'] for r in pr['scenarios'] if r['layout'].startswith('four cards (TP4')):
        cells = []
        for sp in sp4:
            v = [r for r in pr['scenarios'] if r['layout'].startswith('four cards (TP4') and r['levers'] == lever and r['speculation'] == sp]
            cells.append(' / '.join(f"{r['serial_tok_s']:.0f}" for r in v))
        L.append(f'| {lever} | ' + ' | '.join(cells) + ' |')
    L.append('\n**Acceptance sweep** (every chain position accepted with probability a; #1 + #3 + #4 2x; serial / with-redo / upper bound)\n')
    L.append('| layout | depth | ' + ' | '.join(f"a = {a}" for a in dict.fromkeys(x['acceptance'] for x in pr['acceptance_sweep'])) + ' |')
    L.append('| --- | ---: |' + ' ---: |' * len(dict.fromkeys(x['acceptance'] for x in pr['acceptance_sweep'])))
    for layout in ('two cards (PP2)', 'four cards (PP2 x TP2)'):
        for d in (1, 2, 3):
            v = [x for x in pr['acceptance_sweep'] if x['layout'] == layout and x['depth'] == d]
            L.append(f'| {layout} | {d} | ' + ' | '.join(f"{x['serial_tok_s']:.0f} / {x['pipelined_with_redo_tok_s']:.0f} / {x['pipelined_tok_s']:.0f}" for x in v) + ' |')
    L.append('\n**Which stacks reach a target** (best speculation scenario per stack; upper bound / with-redo estimate / serial)\n')
    L.append('| layout | kernels and levers | best upper bound | best with-redo | best serial | reaches 120 / 150 / 200 (redo estimate) | reaches 200 (upper bound) |')
    L.append('| --- | --- | ---: | ---: | ---: | --- | --- |')
    for layout in ('two cards (PP2)', 'four cards (PP2 x TP2)'):
        for lever in dict.fromkeys(r['levers'] for r in pr['scenarios'] if r['layout'] == layout):
            rs = [r for r in pr['scenarios'] if r['layout'] == layout and r['levers'] == lever]
            ub, rd, se = (max(rs, key=lambda r: r[k]) for k in ('pipelined_tok_s', 'pipelined_with_redo_tok_s', 'serial_tok_s'))
            reach = ' / '.join('yes' if rd['pipelined_with_redo_tok_s'] >= t else 'no' for t in (120, 150, 200))
            L.append(f"| {layout} | {lever} | {ub['pipelined_tok_s']:.0f} ({ub['speculation']}) | {rd['pipelined_with_redo_tok_s']:.0f} ({rd['speculation']}) | "
                     f"{se['serial_tok_s']:.0f} | {reach} | {'yes' if ub['pipelined_tok_s'] >= 200 else 'no'} |")
    print('\n'.join(L))


if __name__ == '__main__':
    import sys
    markdown() if sys.argv[1:] == ['--markdown'] else main()
