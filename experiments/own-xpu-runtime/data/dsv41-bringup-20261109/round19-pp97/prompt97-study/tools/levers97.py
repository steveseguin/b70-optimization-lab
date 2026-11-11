"""Lever estimates for the 3K prompt read (DeepSeek V4.1 Flash, six B70, tp97), from the pp97 profiles + model97.

usage: python3 -I levers97.py [OUTDIR]      (default: ../tables) -> lever_estimates.txt

Every saving is seconds off the 3,323-token read at today's 6.80 s (blocks of 64, card 2 = the pace proxy).
Each lever prints the arithmetic it rests on. Inputs that are not in the profiles:
  - xov1 six-card pre-check (runs/xov1/summary.txt, 2026-11-11): pulls on a second queue beside compute hide
    74-95 % (16 groups) / 50-78 % (64 groups) when both kernels use the same register mode, ~0 % across modes;
    an act-sized pull longer than the compute beside it hides only 27-43 %.
  - unprofiled 3K reads (runs/tg96b, tg97b, tg97c): 6.80-6.87 s at 64, 256 about 0.04 s faster (tok/s 497 vs 494).
  - register modes of the forms (pa/grf_pr.txt census): the dense WS forms at T = 8 / 16, R = 2 build at 256.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import budget97 as B  # noqa: E402
import model97 as M  # noqa: E402
import prof97 as P  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tables')
WALL = 6.80
NB64 = math.ceil(M.NTOK / 64)
PS_FP32 = 2 / M.ISSUE * 1e12          # ps per multiply-add at the FP32 issue rate (card-wide)
PS_PORT_R2 = 2 / M.PORT * 1e12        # ps per multiply-add when every x float feeds 2 rows (4 / R bytes)


def s(roles, *names):
    return sum(roles.get(n, [0, 0])[0] for n in names) / 1e3


def fam(roles, f):
    return sum(v[0] for k, v in roles.items() if B.FAM.get(k) == f) / 1e3


def main():
    B.IDS = M.read_ids()
    R = P.runs()
    r64 = B.roles_of(R['pp97/c2_b64'])
    r256 = B.roles_of(R['pp97/c2_b256'])
    run64 = R['pp97/c2_b64']
    cd = M.Card(2)
    out = ['# Lever estimates, 3K read (3,323 tokens), seconds off today\'s 6.80 s (tp97, blocks of 64, card 2 pace proxy)',
           '# FP32 rate 11.47 T ops/s = 5.73 T multiply-adds/s (a multiply then an add; no FMA, no DPAS); '
           'x port 8.28 TB/s; link 25 GB/s.', '']
    L = []

    # ---------------------------------------------------------------- floors of the whole read
    fl = B.floors(cd, 64)
    dense_fp = sum(v[0] for k, v in fl.items() if B.FAM.get(k) == 'dense rows')
    rr = {'router rows': 1, 'shared down': (27 * 4 + 13 * 2) / 40.0}   # rows per x read (DenseRowsG = 1; down Q8 R = 4)
    dense_port = sum(v[2] * 4.0 / rr.get(k, 2) for k, v in fl.items() if B.FAM.get(k) == 'dense rows') / M.PORT
    exf = {(b, c): M.expert_read(cd, b, c, B.IDS) for b, c in ((64, 6), (256, 6), (256, 16))}
    eiss = {k: sum((2 * o[p]['macs'] + B.DECODE_OPS * o[p]['gweights']) / M.ISSUE for p in o) for k, o in exf.items()}
    efp = sum(2 * exf[(64, 6)][p]['macs'] / M.ISSUE for p in exf[(64, 6)])
    rest = sum(v[0] for k, v in fl.items() if B.FAM.get(k) in ('attention', 'compressor + indexer', 'norms + dot rows'))
    xf0 = sum(v[2] for v in B.exch_floor(cd, 64).values())
    strict = dense_fp + efp + rest
    prac64 = max(dense_fp, dense_port) + eiss[(64, 6)] + rest
    prac256 = max(dense_fp, dense_port) + eiss[(256, 16)] + rest
    out += ['Floors of the whole read on card 2 (s):',
            '  strict FP32 (every multiply-add at 5.73 T/s, nothing else): dense %.3f + experts %.3f + attention / index / '
            'norms %.3f = %.3f s -> today is %.1fx' % (dense_fp, efp, rest, strict, WALL / strict),
            '  + exchange bytes at 25 GB/s, not overlapped: %.3f s -> %.1fx' % (strict + xf0, WALL / (strict + xf0)),
            '  today\'s tile shapes (dense x through the L1 port at R = 2: %.3f s; expert decode per group: %.3f s at 64, '
            '%.3f s at 256 cap 16), exchanges hidden: %.3f s at 64, %.3f s at 256 -> %.1fx / %.1fx' %
            (dense_port, eiss[(64, 6)], eiss[(256, 16)], prac64, prac256, WALL / prac64, WALL / prac256),
            '  (a "5x" figure comes from counting a multiply-add as one fused instruction: compute floor %.2f s, %.2f s '
            'with the exchange bytes -> 6.9x / 4.0x; the fused FMA rounds once, differently from the reference, and is '
            'not allowed)' % (strict / 2, strict / 2 + xf0), '']

    # ---------------------------------------------------------------- E: exchanges overlapped
    x64 = fam(r64, 'exchanges')
    xf = sum(v[2] for v in B.exch_floor(cd, 64).values())
    lo_h, c_h, hi_h = 0.50, 0.65, 0.85
    lo_c, c_c, hi_c = 0.08, 0.05, 0.03
    d = ['card 2 exchange kernels: %.3f s per read (243 launches per 64-block: 80 XchgPull2, 83 XchgPull, 80 XchgPair); '
         'byte + sync floor %.3f s at 25 GB/s; nothing overlaps today, so all of it is on the critical path.' % (x64, xf),
         'hidden fraction %.0f-%.0f %% (xov1: 74-95 %% same register mode, 16 groups; 50-78 %% at 64 groups; ~0 %% across modes; '
         'the pulls here are 40-150 us beside 0.2-1 ms phases of the other half)' % (100 * lo_h, 100 * hi_h),
         'cost %.2f-%.2f s: pull work-groups share threads (xov1 compute +1.6-5 %% while overlapped), ~12.6K cross-queue '
         'barriers per read, two expert-group copies' % (hi_c, lo_c),
         'halves are 64-token halves of a 128-token block, so every kernel keeps today\'s 64-token cost; '
         'saving = %.3f x hidden - cost' % x64]
    L.append(dict(name='E: exchanges overlapped (two 64-token halves in flight; pulls on a second queue in the register '
                       'mode of the kernels beside them, or as riders inside them)',
                  kind='scheduling', now=x64, floor=0.0,
                  lo=x64 * lo_h - lo_c, c=x64 * c_h - c_c, hi=x64 * hi_h - hi_c,
                  effort='L (700-900 lines of backend_sycl_v41_mt.inc: per-half state, every exchange moved to a '
                         'second in-order queue, two pull builds 128 / 256)',
                  conf='medium-low', exact='arithmetic unchanged (halves = two consecutive 64-token blocks; traces are '
                                           'byte-identical across block sizes); the risk is ordering (a race gives '
                                           'wrong values or a hang), which the gate and xchg_pull_test catch', d=d))

    # ---------------------------------------------------------------- 256 done right
    mins, today64, today256 = 0.0, 0.0, 0.0
    pen = []
    for role in set(r64) | set(r256):
        if B.FAM.get(role) is None:
            continue
        a, b = r64.get(role, [0, 0])[0], r256.get(role, [0, 0])[0]
        mins += min(a, b)
        today64 += a
        today256 += b
        if b > a + 5:
            pen.append((b - a, role))
    pen.sort(reverse=True)
    gaps = 0.075   # unprofiled: 256 is ~0.04 s faster with +0.034 s more kernel time -> ~0.075 s fewer gaps
    kern = (today64 - mins) / 1e3
    d = ['every role at the cheaper of its 64- and 256-token cost: %.3f s of kernels vs %.3f at 64 today and %.3f at 256 '
         'today (card 2)' % (mins / 1e3, today64 / 1e3, today256 / 1e3),
         'the 256-token penalties to remove (ms per read): ' + ', '.join('%s +%.0f' % (r, v) for v, r in pen),
         'causes: the form table picks T = 4, R = 4 dense forms at 256 (0.35 ps per mul-add vs 0.30 for the 64-token '
         'T = 8, R = 2 forms), the router / compressor / engram rows use forms without weight reuse (router 420 us per '
         'launch at 256 vs 67 at 64: x 6.2 for x 4 tokens), ExpertGroupM 336 us vs 47',
         'gaps: ~%.3f s fewer (unprofiled 256 reads ~0.04 s faster than 64 with 0.034 s more kernel time)' % gaps,
         'saving = %.3f kernels + %.3f gaps; the range allows for the combination not being measured' % (kern, gaps)]
    L.append(dict(name='Blocks of 256 done right (each role at its best per-token cost: 64-token dense forms looped '
                       'over 256 tokens, weight-reusing engram / router forms, a parallel expert grouping)',
                  kind='mostly scheduling (form table), plus 2 kernels', now=WALL, floor=None,
                  lo=0.30, c=kern + gaps, hi=0.50,
                  effort='M (WsTab picks at M = 256; engram WS form at 256; ExpertGroupM rewrite; H16 WS form shared '
                         'with the dense-forms lever)',
                  conf='medium', exact='none: per-token arithmetic does not depend on the block size (gate already '
                                       'runs 256 / 129 / 255-token blocks TRACE_IDENTICAL)', d=d))

    # ---------------------------------------------------------------- experts
    ex = M.expert_read(cd, 64, 6, B.IDS)
    fp = sum(2 * ex[k]['macs'] / M.ISSUE for k in ex)
    dec = sum(B.DECODE_OPS * ex[k]['gweights'] / M.ISSUE for k in ex)
    ex16 = M.expert_read(cd, 64, 16, B.IDS)
    dec16 = sum(B.DECODE_OPS * ex16[k]['gweights'] / M.ISSUE for k in ex16)
    e_now = fam(r64, 'experts gate+up') + fam(r64, 'experts down')
    e_fl = fp + dec
    eff = e_fl / e_now
    d = ['routed gate+up + down: %.3f s per read (41 %% of kernel time); FP32 floor %.3f s, + decode (7 instructions per '
         'weight per group of <= 6 slots) %.3f s = issue floor %.3f s; today at %.0f %% of it' % (e_now, fp, dec, e_fl, 100 * eff),
         'cap 16 instead of 6 at 64 tokens: decode %.3f -> %.3f s (needs forms that stay at 128 registers)' % (dec, dec16),
         'x through the L1 port at R = 2: 1.14 s (below the issue floor: not the binding limit)',
         'at 75 / 80 / 85 %% of the issue floor: %.2f / %.2f / %.2f s -> saves %.2f / %.2f / %.2f s' %
         (e_fl / .75, e_fl / .80, e_fl / .85, e_now - e_fl / .75, e_now - e_fl / .80, e_now - e_fl / .85),
         'at 256 the floor is lower (1.50 s cap 6, 1.25 s cap 16) and today\'s kernels run at 60 % of it: the same '
         'efficiency gain applies on top of the bigger-blocks lever']
    L.append(dict(name='Expert kernels (rux-2): spill-free two-row forms, four-row tiles at 128 registers, decode '
                       'shared by more slots (cap 8-16 where registers allow)',
                  kind='kernel', now=e_now, floor=e_fl,
                  lo=e_now - e_fl / .75, c=e_now - e_fl / .80 - 0.06, hi=e_now - e_fl / .85 + 0.05,
                  effort='M-L (sycl_v41_routed_rux.hpp; bench_rux.cpp exists with the real 3K picks)',
                  conf='low (the packed-lane K2 forms were all slower; rux-1 took -0.36 s in one step)',
                  exact='low risk: same decoded weights, same x addresses, same multiply-then-add order per output, '
                        'same final butterfly (rux-1 argument); bench_rux checks every output bitwise', d=d))

    # ---------------------------------------------------------------- dense forms that lag
    h16 = [(ms, n, us, name) for role, ms, n, us, name in run64.rows() if 'GemvH16P<160u' in name or 'GemvH16P<40u' in name]
    h16_now = sum(x[0] for x in h16) / 1e3
    h16_fl = 0.0
    for ms, n, us, name in h16:
        r, c = (384, 5120) if '160u' in name else (4096, 1280)
        h16_fl += n * 2 * r * c * M.NTOK / NB64 / M.ISSUE
    h16_tgt = h16_fl * 1.75
    q8 = {}
    for role, ms, n, us, name in run64.rows():
        if B.FAM.get(role) == 'dense rows' and 'GemvH16P' not in name:
            f = 'Q8' if 'Q8' in name else 'Q6' if 'Q6' in name else 'Q5'
            a = q8.setdefault((role, f), [0, 0])
            a[0] += ms
            a[1] += n
    q6gap = 0.0
    for role in ('q_a + kv rows', 'q_b rows', 'o_a rows', 'o_b rows', 'route pick + shared gate/up', 'shared down'):
        a, b = q8.get((role, 'Q8')), q8.get((role, 'Q6')) or q8.get((role, 'Q5'))
        if a and b:
            q6gap += b[0] - a[0] / 27 * 13
    q6gap /= 1e3
    reg = 0.049 + 0.010   # tp92 -> tp97, same code: WsQ6<32u> o_b +49 ms, WsQ6<24u> engram +10 ms (card 2)
    d = ['H16 rows (router, compressor, indexer proj in one kernel type; indexer q_b): %.3f s per read; DenseRowsG reads '
         'x once per row (4 B per mul-add through the port): 3.1x / 5.2x the FP32 floor (%.3f s). A WS form with R = 2 '
         'rows per x read at the Q8 forms\' 1.75x floor: %.3f s -> saves %.3f s at 64 (more at 256)' %
         (h16_now, h16_fl, h16_tgt, h16_now - h16_tgt),
         'Q6_K / Q5_K layers (13 of 40) take %.3f s more than the same shapes at the Q8 per-launch time; their decode is '
         'heavier (6-bit split + 16-weight scales), so count 40-60 %% of it: %.3f-%.3f s; the o_b Q6 form at 64 runs '
         'T = 4 (4.0x floor) while T = 8 is ~11 %% faster per token at 128' % (q6gap, 0.4 * q6gap, 0.6 * q6gap),
         'tp92 -> tp97 slowdown of unchanged Q6 forms (o_b WsQ6<32u> 244 -> 317 us, engram WsQ6<24u> 575 -> 670 us): '
         '%.3f s; check register mode / spills in the IGC dump, pin the mode' % reg]
    dl, dc, dh = (0.8 * (h16_now - h16_tgt) + 0.4 * q6gap + 0.5 * reg, (h16_now - h16_tgt) + 0.5 * q6gap + 0.8 * reg,
                  1.1 * (h16_now - h16_tgt) + 0.6 * q6gap + reg)
    L.append(dict(name='Dense forms that lag: a weight-reusing H16 form for router / compressor / indexer rows, '
                       'Q6_K / Q5_K forms closer to Q8_0, undo the tp97 Q6 slowdown',
                  kind='kernel', now=h16_now + q6gap + reg, floor=None, lo=dl, c=dc, hi=dh,
                  effort='S-M (WsH16 forms exist for checks of 2-3 tokens; extend to T = 8, R = 2 and the 4,096-row '
                         'indexer shape; Q6 / Q5 form tuning in bench_dense_ws; one IGC dump)',
                  conf='medium (H16 part medium-high)',
                  exact='low risk: WS forms keep each output\'s column order and butterfly (1,560 bitwise checks for '
                        'Q8 / Q6 / Q5); the H16 form needs its own bitwise bench against GemvH16P', d=d))

    # ---------------------------------------------------------------- D: replicated rows split
    rep = s(r64, 'q_a + kv rows')
    idx = s(r64, 'indexer q_b + proj + k rows')
    pulls = 40 * NB64
    by = 64 * 1792 * 4 * 5 / 6
    cp = by / M.LINK * 1e6 + 2.5
    lo = rep * (1 - 2.0 / 6) - pulls * (cp + 48) * 1e-6
    hi = rep * (1 - 1.4 / 6) - pulls * (cp + 20) * 1e-6
    d = ['q_a + kv rows run whole on every card: %.3f s per read on card 2 (2.1x their FP32 floor)' % rep,
         'split by 6 (213 / 85-row slices: fewer threads, 1.4-2.0x less efficient per row): %.3f-%.3f s' %
         (rep * 1.4 / 6, rep * 2.0 / 6),
         'one new pull per layer before the q_a / kv norms: %.0f KB per 64-block and layer = %.1f us + 2.5 us sync, '
         'plus 20-48 us of waiting (today\'s XchgPull on card 2 runs 48 us per launch above its floor); %d pulls per read'
         % (by / 1e3, by / M.LINK * 1e6, pulls),
         'net %.3f-%.3f s; the router (0.150 s) and compressor rows split for ~0 net (each needs its own pull), the indexer '
         'q_b for ~0.05 s before the H16 form and ~0 after it' % (lo, hi),
         'with E in place the new pull hides too: +0.05-0.1 s']
    L.append(dict(name='D: replicated q_a + kv rows (and the indexer q_b) split across the six cards',
                  kind='kernel table + one new exchange per layer', now=rep + idx, floor=None,
                  lo=lo, c=(lo + hi) / 2 + 0.02, hi=hi + 0.05,
                  effort='M-L (a third pull per layer, arena pointers for every q_a / kv reader, token strides at the '
                         'norm / StatePack / publish sites; pcd README item D)',
                  conf='medium-low', exact='none in the arithmetic (each row still computed whole on one card, same '
                                           'order); the pull copies bits', d=d))

    # ---------------------------------------------------------------- dense Q8 issue efficiency (G)
    d = ['Q8_0 WS forms at 64 tokens: 0.30-0.35 ps per mul-add against %.3f ps FP32 and %.3f ps for the x port at R = 2 '
         '(each x float loaded once per 2 rows: 2 B per mul-add) -> they run at ~1.25x the port bound, not 2x the '
         'FP32 bound' % (PS_FP32, PS_PORT_R2),
         'past the port needs R = 4 with T = 8 (port 0.121 ps, ALU 2.5 ops per mul-add = 0.218 ps): best case ~0.27 ps '
         'at 80 % of that -> ~10 % off the Q8 dense time (~1.2 s) = ~0.12 s; R = 4 x T = 8 needs ~80 registers per lane '
         '(256-register mode, half the threads), the existing T = 4, R = 4 forms run 0.35 ps',
         'T = 16 at R = 2 stays port-bound (no gain)']
    L.append(dict(name='Dense Q8_0 forms past the x-port cap (R = 4 x T = 8 tiles)', kind='kernel', now=1.2, floor=None,
                  lo=0.03, c=0.08, hi=0.15, effort='M (bench_dense_ws variants, IGC register check)', conf='low',
                  exact='low risk if each lane keeps its column order and the final butterfly', d=d))

    # ---------------------------------------------------------------- expert grouping
    g64 = s(r64, 'expert grouping')
    d = ['ExpertGroupM: %.3f s per read at 64 (47 us x 40 per block, 72x a launch); 336 us per launch at 256 (+0.077 s, '
         'counted in the bigger-blocks lever)' % g64,
         'a parallel counting sort of 384-1,536 slots should run in ~10 us: saves %.3f s at 64' % (g64 - 2080 * 10e-6)]
    L.append(dict(name='Expert grouping kernel (ExpertGroupM) parallel', kind='kernel', now=g64, floor=0.0014,
                  lo=0.05, c=g64 - 2080 * 10e-6, hi=0.085, effort='S (one kernel + test at 96-1,536 slots)',
                  conf='medium-high', exact='none: groups only decide which slots share one decode; each output and '
                                            'the combine\'s slot order are unchanged', d=d))

    # ---------------------------------------------------------------- 12 / 8 heads
    d = ['prompt blocks use 12,12,12,12,8,8 heads (OWN_TP_HEADS 3,3,3,3,2,2), not 16 / 8: cards 0 and 2 both hold 12',
         '12-head cards carry ~133 us more per layer in q_b / attention / o_a / pair swap; the 8-head cards take more '
         'mix dot rows (OWN_MT_DSPLIT weights 1,1,1,1,4,4: ~32 us) -> ~101 us per layer = ~0.21 s per read of slack '
         'on cards 4 / 5',
         'evening it out (an 11,11,11,11,10,10 layout with generalised pair swaps, or more dots on cards 4 / 5) takes '
         '~1/3 of it off the four heavy cards: 0.05-0.1 s; a free first test: OWN_MT_DSPLIT_WA=0,0,0,0,1,1 (~0.03 s)']
    L.append(dict(name='12 / 8 head imbalance in prompt blocks', kind='scheduling (runtime weights; layout)', now=0.21,
                  floor=0.0, lo=0.02, c=0.06, hi=0.12, effort='S (weights) / M (layout)', conf='low',
                  exact='none if every head stays whole on one card', d=d))

    # ---------------------------------------------------------------- ranked table
    L.sort(key=lambda z: -z['c'])
    out.append('| rank | lever | kind | saving s (low / central / high) | 3K read after it alone | effort | confidence | bit-exact |')
    out.append('|---|---|---|---|---|---|---|---|')
    for i, z in enumerate(L):
        out.append('| %d | %s | %s | %.2f / **%.2f** / %.2f | %.2f s (%d tok/s) | %s | %s | %s |' %
                   (i + 1, z['name'], z['kind'], z['lo'], z['c'], z['hi'], WALL - z['c'], M.NTOK / (WALL - z['c']),
                    z['effort'].split(' (')[0], z['conf'].split(' (')[0], 'yes'))
    tot_c = sum(z['c'] for z in L)
    tot_lo = sum(z['lo'] for z in L)
    tot_hi = sum(z['hi'] for z in L)
    out.append('')
    out.append('All of them (treated as additive; they touch different time): %.2f / %.2f / %.2f s -> %.2f / %.2f / %.2f s '
               '(%d / %d / %d tok/s)' % (tot_lo, tot_c, tot_hi, WALL - tot_lo, WALL - tot_c, WALL - tot_hi,
                                         M.NTOK / (WALL - tot_lo), M.NTOK / (WALL - tot_c), M.NTOK / (WALL - tot_hi)))
    out.append('')
    for i, z in enumerate(L):
        out.append('## %d. %s' % (i + 1, z['name']))
        out.append('   kind: %s; effort: %s; confidence: %s' % (z['kind'], z['effort'], z['conf']))
        out.append('   bit-exact: %s' % z['exact'])
        out.append('   saving: %.2f / %.2f / %.2f s' % (z['lo'], z['c'], z['hi']))
        for line in z['d']:
            out.append('   - ' + line)
        out.append('')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'lever_estimates.txt'), 'w') as f:
        f.write('\n'.join(out) + '\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
