"""The arithmetic behind the ranked levers of ../README.md section 4. Every input is a number from a table in
../tables (file named next to it) or from the source / notes named; nothing is measured here. Prints each lever's
saving per check size M (1 = the one-token path, also every zero-guess check) and the mean per guessing round
(weights: rounds by guess count, tables/rounds_by_guesses_attck.txt; M6 has no timeline, M5's value is used).
usage: python3 -I levers96.py"""

LAYERS = 40
# rounds by guesses 0..5 = checks of M = 1..6 tokens (tables/rounds_by_guesses_attck.txt, run 1 of each; run 2 equal)
ROUNDS = {'code': [63, 64, 41, 21, 14, 20], 'analysis': [27, 40, 32, 24, 21, 36]}


def per_round(by_m):
    """by_m: {M: (lo, hi)} ms saved per check; missing M = 0."""
    out = {}
    for k, w in ROUNDS.items():
        lo = sum(w[m - 1] * by_m.get(m, (0, 0))[0] for m in range(1, 7)) / sum(w)
        hi = sum(w[m - 1] * by_m.get(m, (0, 0))[1] for m in range(1, 7)) / sum(w)
        out[k] = (lo, hi)
    return out


def show(name, by_m, note=''):
    print('== ' + name)
    for m in sorted(by_m):
        lo, hi = by_m[m]
        print('   M=%d: %.2f to %.2f ms per check' % (m, lo, hi))
    for k, (lo, hi) in per_round(by_m).items():
        print('   per %s round: %.3f to %.3f ms' % (k, lo, hi))
    if note:
        print('   ' + note)


# ---- 1. one round trip per pull exchange (data and flag together)
# A pull costs ~12.2 us, the same in an idle bench where all cards arrive together (step-budget note, e81b 11.9 us):
# two PCIe round trips (flag, then data) + launch (>= 2.2 us, step budget) + bytes (27-46 KB at 25 GB/s: 1.1-1.8 us).
# tables/one_token_segments_xwait_att_vs_default.txt (tl_one, after-arrival per exchange kind, c2): output-a 422 /
# 40 = 10.6 us, expert act 447 / 40 = 11.2 us; light cards 11.1-11.8 us.
pull_after = (10.6 + 11.2) / 2
rt2 = pull_after - 2.2 - 1.5          # the two round trips
rt = (0.75 * rt2 / 2, 1.15 * rt2 / 2)  # one round trip, +-15-25 %
pulls_1 = 40 + 40 + 3                 # output-a, expert act, engram (pulls on the one-token path and at M = 2)
pulls_3 = 4 * 40 + 3                  # from M = 3 output-b and ffn rows are pulls too (slice >= OWN_XPULL_MIN 8192 B)
x = {1: tuple(pulls_1 * r / 1e3 for r in rt), 2: tuple(pulls_1 * r / 1e3 for r in rt)}
for m in (3, 4, 5, 6):
    x[m] = tuple(pulls_3 * r / 1e3 for r in rt)
show('1. pull exchanges in one round trip', x,
     'one round trip = %.1f-%.1f us (two = %.1f us = %.1f us after arrival - 2.2 launch - 1.5 bytes)'
     % (rt[0], rt[1], rt2, pull_after))

# ---- 3. the DSPLIT finishes ride o_b's and shared down's launches (M >= 4)
# tables/kernels_pace_m3_m4_m5.txt, RowsP<TokRows<HcFinishRows>> alone: M4 343.0 + 327.6, M4b 341.9 + 326.7,
# M5 325.3 + 327.6 us per check (40 launches each).
alone = {4: (343.0 + 327.6 + 341.9 + 326.7) / 2, 5: 325.3 + 327.6}
# rider cost per launch: the same finish riding q_b (kernels/sycl_v41.hpp WsTab<8, 1280>, bench SEQ us per launch):
# WS_DOTS (with the finish) - WS_PLAIN: 3: 28.4 - 27.2 = 1.2, 4: 32.0 - 28.4 = 3.6, 5: 31.9 - 31.8 = 0.1,
# 6: 34.2 - 33.8 = 0.4 (mean 1.3); range 0.1-3.6
rid_lo, rid_mid, rid_hi = 0.1, 1.3, 3.6
d = {}
for m in (4, 5, 6):
    a = alone[min(m, 5)]
    d[m] = ((a - 2 * LAYERS * rid_hi) / 1e3, (a - 2 * LAYERS * rid_lo) / 1e3)
show('3. DSPLIT finishes as riders (WS_DOTS forms for o_b and shared down)', d,
     'central (rider 1.3 us): M4 %.2f, M5 %.2f ms' % ((alone[4] - 80 * rid_mid) / 1e3, (alone[5] - 80 * rid_mid) / 1e3))

# ---- 2. q_b rows of the 16-head cards ride the light neighbours' own q_b launches, results pushed one way
# per check (pace q_b, light q_b) us: M1 tables/roles_pace_light_m1_m2.txt (958, 648); one-token
# tables/roles_pace_light_one_token_att_vs_default.txt (939, 638); M2-M5 tables/slope_by_m_attck.txt
qb = {1: (958, 648), 2: (1102, 721), 3: (1224, 781), 4: (1274, 734), 5: (1395, 813)}
# lead per layer at output-a (tables/segment_a_lead_pace_vs_light.txt; smallest of the timelines at each M)
lead = {1: 14.6, 2: 15.5, 3: 18.4, 4: 19.8, 5: 21.8}
# push: qb-off-1 measured 4.0 us for 4 heads x 512 values x 4 B (8 KB) on the one-token path (strategy note): ~2 GB/s
PUSH_GBS = 2.0
q = {}
detail = []
for m in (1, 2, 3, 4, 5):
    r = (qb[m][0] - qb[m][1]) / LAYERS / 4096  # us per row added to a launch (16-head minus 8-head launch, 4,096 rows)
    best = (0.0, 0)
    for k in (1, 2, 3, 4):                     # heads per helper (two helpers per 16-head card)
        s_h = 2 * k * 512 * r                  # the 16-head card's q_b gets shorter
        c_l = k * 512 * r + k * 512 * m * 4 / (PUSH_GBS * 1e3)  # the helper's rows + its push
        g = max(0.0, min(s_h, lead[m] - c_l))
        if g > best[0]:
            best = (g, k)
    detail.append('M=%d: %.2f ns per row, best k = %d heads per helper, %.1f us per layer' % (m, r * 1e3, best[1], best[0]))
    q[m] = (0.8 * best[0] * LAYERS / 1e3, best[0] * LAYERS / 1e3)
q[6] = q[5]
show('2. heavy cards\' q_b rows in the helpers\' own q_b launches', q, '; '.join(detail))
print('   (in separate helper launches, qb-off-1\'s form: ~3.8 ns per row + 5.3 us fixed + push per layer -> ~0)')

# ---- 4. the routed expert kernels on the one-token path (also every zero-guess check)
# tables/roles_pace_light_one_token_att_vs_default.txt: gate+up 1271 + down 861 us; floor 456 + 291
# (tables/expert_byte_floor_by_m.txt M=1). K2's packed-lane forms: 14-30 % fewer instructions per weight, issue-bound
# production (strategy note); applied to the measured time.
e = 1271 + 861
show('4. expert kernels, one-token path', {1: (0.14 * e / 1e3, 0.30 * e / 1e3)},
     'measured %d us against a byte floor of %d (%.2fx)' % (e, 456 + 291, e / (456 + 291)))

# ---- 5. WindowAppendM inside the check attention launch (M >= 2)
# tables/kernels_pace_m3_m4_m5.txt: 90.1 (M3), 92.6 (M4), 91.2 (M5) us per check, 40 launches of 2.25-2.31 us;
# M2 90 us (2.24 us x 40, tables/kernels_pace_m1_m2_tp96_tp95.txt). Folded: the launch goes, ~1/3 of it stays as work.
w = {m: (0.6 * 91 / 1e3, 0.95 * 91 / 1e3) for m in (2, 3, 4, 5, 6)}
show('5. window append folded into the check attention launch', w)

# ---- closed by arithmetic
print('== near neutral or closed by arithmetic')
# head split 12/12/12/12/8/8 for checks: halves the extra heads, so saves ~0.5 x lead per layer, and adds a pair
# exchange per layer. Its cost P: >= 7.3 us (e79: the one-token split lost, where it would save 0.5 x 14.6 us) and
# ~11.5 us (tune91 neutral at 2 tokens; the 2-token lead then ~22.9 us per layer, ck2tok/README.md, tp95 timeline).
for m in (2, 3, 4, 5):
    print('   head split at M=%d: 0.5 x %.1f - P(7.3 .. 11.5) = %+.1f .. %+.1f us per layer = %+.2f .. %+.2f ms per check'
          % (m, lead[m], 0.5 * lead[m] - 7.3, 0.5 * lead[m] - 11.5, (0.5 * lead[m] - 7.3) * LAYERS / 1e3,
             (0.5 * lead[m] - 11.5) * LAYERS / 1e3))
# with the defaults' leads (tl_ck3_d: 25.8 / 32.9 / 24.4 us per layer at M2 / M3 / M4) the same arithmetic gives
for m, ld in ((2, 25.8), (3, 32.9), (4, 24.4)):
    print('   (defaults M=%d: %+.1f .. %+.1f us per layer: tune91 / tg92 saw +1.2 %% from 3-4 tokens before ck-2)'
          % (m, 0.5 * ld - 7.3, 0.5 * ld - 11.5))
# o_a rows moved to a helper: its input (8 heads' attention output) exists only on the heavy card after attention;
# helper = pull (>= 5.5 us after arrival, output-b's) + launch (5.3 us fixed, qb-off-1) + 512 rows at 2x the
# big-launch rate; the heavy card saves 1/4 of its o_a (tl_one: 744 / 40 = 18.6 us per layer)
oa = 744 / LAYERS
print('   o_a quarter to a helper (one-token): heavy -%.1f us, helper after the heavy card\'s attention +%.1f us '
      '-> the helper is last; net %.1f us per layer' % (0.25 * oa, 5.5 + 5.3 + 2 * 0.25 * oa, oa - (5.5 + 5.3 + 2 * 0.25 * oa)))
