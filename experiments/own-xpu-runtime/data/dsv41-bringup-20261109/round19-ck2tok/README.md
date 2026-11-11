# Why a 2-token check costs 3.2 ms more than a 1-token one (DeepSeek V4.1, six B70, tp95)

2026-11-11. CPU-only analysis of `runs/tg95b/tl_ck.txt`, a check timeline with all six cards. The run used tp95 with
BEST + `OWN_MT_CK=1 OWN_QB_OFF=4`, the code prompt, checks 20-27. In that window there are three 1-token checks
(10021, 10025, 10026; they run the plain one-token path, OWN_CK1), three 2-token checks (10020, 10022, 10027), one
of 4 tokens (10024) and one of 5 (10023). Nothing was run on a card and the repo was not edited.

## In plain words

- In this timeline a 1-token check takes 10.28 ms of wall time and a 2-token check 13.45 ms (+3.17 ms). The gate
  medians, which come from later checks with longer context, are 10.55 and 13.9 ms.
- About **1.7 ms of the +3.2 is real new work**. The second token's experts take 1.05 ms of that: on average 4.5
  experts are new, because 10.5 of the 12 picks are distinct. The rest is the second token's small kernels, its
  attention, and more bytes in the exchanges.
- About **1.5 ms is path overhead**. Four things cause most of it:
  1. **The two 16-head cards (2 and 5) set the pace, and in the block path they also run slow q_b forms.** In checks
     the light cards no longer take over part of q_b (OWN_QB_OFF works only on one-token steps). The mix finish
     rides on q_b's launch, so q_b drops to the GR R4 form, which decodes the weights once per token (36-37 us
     instead of ~25). The light cards wait 0.9 ms per check at the output-a exchange. The first half is **known**:
     the ck helper is fixing it in ck-2 (q_b WS_DOTS picks, ~0.45 ms at 2 tokens).
  2. **Push exchanges in two launches.** At 2 tokens, output-b and ffn-rows are pushes (6.9 KB is under
     OWN_XPULL_MIN = 8192). Each one is an `XchgPushM` launch (2.5 us) followed by an `XchgP`. That is 80 extra
     launches, ~0.2 ms on every card, and the time after arrival also grows.
  3. **`ExpertGroupM` is a launch of its own**: 4 us x 40 = 0.16 ms. The one-token path has nothing like it.
  4. **The stream-mix dot rows ride on the q_a+kv and router launches** instead of sitting in the norm's launch, as
     they do in the one-token path. The Q6_K layers also lose the q_a+kv pair, and some 2-token forms decode once
     per token (kv, o_b on Q6_K). Together that is ~0.25 ms.
- With ck-2 and the four fixes below, a 2-token check should come down to about **12.6 ms**, from 13.9 (gate frame).
  Reaching ~11.5-12 also needs cheaper experts at 12 slots. Their extra 1.05 ms per token is about twice the byte
  floor of ~0.55 ms. The o_a imbalance (0.22 ms) also stays.

## 1. One-token step vs 2-token check, per family (us per check, device time, launches)

The pace cards are 2 and 5: at 2 tokens they hold 16 heads and are the last to reach output-a in 98 % of the
layers. The light cards are 0, 1, 3 and 4. Values are means over the three checks of each size. In the "new" and
"overhead" columns, "new" means work that scales with the tokens, and "overhead" means the block path's extra cost
relative to the tuned one-token structure. Those two columns are estimates. The way each one is derived is in the
row's note. Raw tables: `tables/roles_pace_light_m1_m2.txt`, `tables/kernels_card2_m1_m2.txt` (card 2, per kernel).

| family (one layer phase) | pace M1 | pace M2 | Δ pace | light M1 | light M2 | Δ light | new | overhead | why |
|---|---|---|---|---|---|---|---|---|---|
| q_b rows (+finish, rope) [attn in] | 689 (80) | 1530 (84) | **+841** | 1158 (200) | 950 (84) | -208 | ~80 | **~760** | 16 heads instead of 8 (QB_OFF is one-token only): ~320. Finish rider -> WS_DOTS lookup -> no entry -> GR R4: 36.2 / 37.5 us (Q8 / Q6_K) vs ~25 WS: ~440 (**known, ck-2**). Rope now a launch of its own (1.2 us; it rode q_b / QbWaitRope at M1) |
| q_a+kv rows (+dots) + attn pre-norm | 1031 (80) | 1249 (93) | +218 | 1023 (80) | 1232 (93) | +208 | ~110 | ~110 | M1: SkNormDotsW 6.85 (norm + 25 SkDotsFF rows) + pair 19.5 (Q8) / 17.2 (Q6_K). M2: SkNormWM 3.2 + pair with HcDotsRows riders 26.6 (Q8). On Q6_K the pair is lost: q_a WS+dots 21.1 + kv `DenseRowsG<GemvQ6KP<20>,1>` 9.0 (13 extra launches, kv decoded once per token) |
| router (+dots) + ffn pre-norm | 633 (80) | 767 (80) | +134 | 630 (80) | 753 (80) | +123 | ~90 | ~45 | M1: SkNormDotsW 6.9 + router 8.8. M2: SkNormWM 3.4 + router with HcDotsRows riders 15.4 |
| router pick + finish + shared gate/up | 447 (40) | 511 (40) | +63 | 444 (40) | 512 (40) | +69 | ~45 | ~20 | Q8 11.0 -> 13.5 us. The WS_SHARED check pick at 2 tokens is C1R1 (T = 1, per token) |
| ExpertGroupM | 0 | 163 (40) | **+163** | 0 | 161 (40) | +161 | 0 | **163** | an extra launch, 4.0 us per layer |
| routed experts gate+up | 1294 (40) | 1910 (40) | +615 | 1279 | 1899 | +619 | 615 | 0 | 10.5 distinct experts of 12 picks (u84 table): 1.75x the bytes for 1.48x the time |
| routed experts down | 873 (40) | 1311 (40) | +438 | 844 | 1294 | +451 | 438 | 0 | as above. Byte floor for the 4.5 new experts, both: ~0.55 ms at 550 GB/s |
| SwiGLU, MoE combine, shared down | 369 (120) | 433 (120) | +64 | 362 | 435 | +73 | ~55 | ~10 | per-token small forms (SwiGLU 1.28 -> 1.9 us, combine 1.6 -> 2.0) |
| attention core | 732 (160) | 770 (160) | +37 | 724 | 744 | +20 | 37 | 0 | M-forms do both tokens in one launch |
| o_a rows [attn out] | 749 (40) | 718 (40) | -31 | 439 | 497 | +58 | 0 | -31 | the 2-token WS forms beat the one-token GEMV (Q6_K 19.8 -> 16.5 us). **o_a is 16 heads on the pace cards (17.9 vs 12.4 us per layer) and cannot move** |
| o_b rows | 625 (40) | 714 (40) | +89 | 613 | 730 | +117 | ~35 | ~55 | Q6_K o_b has no 2-token WS pick: `DenseRowsG<GemvQ6KP<32>,1>` 19.3 vs 14.9 us |
| mix collapse, compressor, engram, head, embed, check tail | 602 (150) | 702 (147) | +100 | 597 | 696 | +99 | ~70 | ~30 | HcPostPrePMG 1.69 vs HcPostPreP 1.24 us x 78, etc. |
| exchanges (all kinds) | 1880 (165) | 2308 (245) | +428 | 1804 (165) | 3185 (245) | **+1381** | ~150 | ~280 | pace: +198 for the XchgPushM launches, +221 after arrival (2x bytes, slow peer stores), wait +13. Light: +844 waiting at output-a for the pace cards |
| **total busy** | **10042 (1075)** | **13202 (1209)** | **+3160** | 10032 (1195) | 13203 (1209) | +3170 | **~1.73 ms** | **~1.46 ms** | |

Each card is busy for ~98 % of the check's span (idle 0.22-0.28 ms in both paths), so busy time on the pace cards
is the critical path. A light card's extra time goes to waiting. Launches per layer: 25 at one token (pace) and
28 at two tokens (the two push launches, ExpertGroupM, and kv separate on Q6_K, while QbWaitRope becomes a rope
launch). So the launch count is not the main cost.

### The same check by layer phase: wall time between exchange completions (`tables/segments_m1_m2_m4_m5.txt`)

| segment (per check, 40 layers) | M1 wall | M2 wall | Δ | last to arrive (M2) | what grew |
|---|---|---|---|---|---|
| A attention input -> attention -> o_a -> **output-a** | 4292 | 5252 | **+960** | cards 5 / 2 (65 / 33 %), 0.85 ms ahead of the light cards' work | q_b +841, q_a/kv/dots +218, attention +37 (pace card) |
| B o_b -> **output-b** | 912 | 1193 | +281 | spread | PushM +98, o_b +89, after arrival +56 |
| C FFN input, router, gate+up, SwiGLU -> **expert act** | 3077 | 4183 | **+1106** | spread | gate+up +615, ExpertGroupM +163, router/dots +134, shared/finish +63, after +50 |
| D down, shared down, combine -> **ffn rows** | 1536 | 2272 | +736 | spread | down +438, PushM +97, after +115 |
| engram (layers 1, 14) + head + check tail | 458 | 549 | +91 | | |
| **total** | **10276** | **13449** | **+3173** | | |

At 1 token, segment A ends with the light cards (the QB_OFF helpers) arriving last by 0.1-0.2 ms. At 2 tokens it
ends with the 16-head cards arriving last by 0.85 ms, and that 0.85 ms is the largest single piece of overhead.
Segments C and D are balanced at both sizes (the cards' work agrees within ~0.1 ms), so a cut there reaches the
wall clock directly.

## 2. Exchanges (`tables/exchange_waits_m1_m2_m4_m5.txt`)

Each check has 164 exchanges: 4 per layer, plus 3 engram and 1 for the draft fc. "Arrival" is the start of the
kernel that raises the card's flags. "Wait" is the last card's arrival minus this card's arrival. "After" is the
time from the last arrival to this card's end, which covers flags, fences and the pull or push itself. The clocks
are aligned causally: 2-7 of 2,952 ends fall before the last arrival (alignment error).

| | 1-token (CK1 plain path) | 2-token block path |
|---|---|---|
| exchange launches per check | 165 (83 XchgPull + 81 XchgP + 1 PushM) | 245 (83 XchgPull + 81 XchgP + **81 XchgPushM**) |
| pace cards: wait / after / push launches (ms) | 0.44 / 1.44 / 0.00 | 0.45 / 1.66 / 0.20 |
| light cards: wait / after / push launches (ms) | 0.31 / 1.49 / 0.00 | **1.27** / 1.73 / 0.19 |
| light cards' wait at output-a, per layer | 2.1 us | **22.9 us** |
| after arrival per exchange (card 2): output-a pull | 11.4 us | 10.8 |
| expert-act pull | 11.4 | 12.8 |
| output-b | 6.1 (XchgP pushes) | 7.6 + 2.5 PushM |
| ffn rows | 6.9 | 10.0 + 2.5 PushM |

At 3+ tokens these two exchanges become pulls (10.4 KB >= 8192), so XchgPushM appears only at 2 tokens. From 2
tokens on, the pull exchanges' after-arrival time grows ~3.5 us per extra token per exchange. Measured at 4 and 5
tokens: 2.8-3.0 ms after arrival, against 1.7 ms at 2 tokens. That is ~0.5 ms of every further token on the pace
card, far above the bytes. It matters for M = 3-6, not for the 1->2 step.

## 3. Ranked fixes (ms per 2-token check on the critical path; then M = 3-6)

0. **(Known, ck-2 in progress) q_b in weight-stationary forms under the finish rider** (WS_DOTS picks for
   1280-column Q8_0 / Q6_K q_b). Saves -0.45 ms at M=2 (36-37 -> ~25 us x 40 on the pace cards). The ck helper
   puts M=3 at 46 -> 30 us, so ~-0.6 ms there. Nothing at M >= 4, where DSPLIT already moves the finish off q_b. Bits:
   the rider runs the same finish code in any launch, as FIN_QB already showed, and WS rows match the one-token
   rows by the WS proof.
1. **q_b offload for checks: the light cards compute 2-3 of each heavy card's heads for the block and the heavy
   card waits in its rope launch.** This is OWN_QB_OFF carried to tpm_layer. After ck-2 the pace cards still lead
   at output-a by ~16 us per layer: q_b 25 vs ~16-17, o_a 17.9 vs 12.4, attention +0.7. With k = 3 the heavy card
   saves ~6.5 us and each helper carries ~+9.5 us (3 heads x 2 tokens, a launch, the push), which roughly
   balances: **-0.2 to -0.26 ms at M=2**. At M=3-6 the lead is 20-26 us per layer today (4 tokens: 0.81 ms,
   5 tokens: 1.03 ms), worth **-0.3 to -0.4 ms**. From 3 tokens on, let the heavy card pull the helpers' rows
   (loads run at 25-37 GB/s, against ~1 GB/s per card for peer stores). Bits: every row of q_b is the same row
   code whatever dense form or card runs it (all forms are bit-identical to the one-token rows), the rope kernel
   is the same, and the transfer is a pure copy. qb-off-1's gates already proved the pattern (traces identical,
   k = 2/3/4). Effort: medium (block strides, M-token push or pull, a k per M). Risk: the light cards' slack, which
   is 22.9 us per layer today and ~16 after ck-2. Lesson from qb-off-1: size k from a six-card timeline, not from
   a one-card bench.
2. **The 2-token push exchange in one launch.** Today it is XchgPushM, 2.5 us, then XchgP with nslot 0. Running
   XchgP's own one-group push for both slots, as at 1 token, saves 80 launches. Expected **-0.15 to -0.3 ms at
   M=2** (0.2 ms of launches, plus part of the after-arrival growth: 6.1 -> 7.6 and 6.9 -> 10.0 us). Nothing at
   M >= 3, where these are pulls. No build needed: `OWN_MT_XPUSH=0` (or `=2`, one group per peer), or turn them
   into pulls with `OWN_XPULL_MIN=6912`. Bits: pure copies of the same bytes. Risk: the draft's block exchanges may
   take the same branch, so watch the draft ms column.
3. **ExpertGroupM folded into the expert gate+up launch.** Each work-group computes the groups of the block's
   6M ids in local memory (36 ids at most for checks; O(n^2) scans as ExpertGroupM does), and work-group 0 writes
   the table for the down launch. Saves **-0.14 ms at M=2**, -0.2 to -0.22 at M=4-6 (ExpertGroupM grows to 5.5-6.6
   us). Segment C is balanced, so the cut reaches the wall clock. Bits: the same table from the same ids by the same
   code, and a slot's sums do not depend on its group (the OWN_MT_EU rule). Effort: small to medium (RoutedU*
   prologue). Risk: local memory and registers in RoutedU3, so check that it stays at 128 registers in the machine
   code.
4. **Dot rows in the norm's launch at 2-3 tokens (the one-token placement): `OWN_MT_SKDOTS_MIN=2`.** This turns
   the pre-norms into SkNormDotsWM and leaves the q_a+kv pair and the router without riders. tune92 saw SKDOTS from
   2 lose, but that was before skn-1's fused SkNormDotsWM (norm + dots 10.0 -> 4.6 us). The numbers have changed,
   so it is worth one arm. Expected **-0.1 to -0.2 ms** (uncertain). Bits: SkDotsWM is the one-token SkDotsFF row
   code, gated at 2 tokens in tg92. No build needed.
5. **Q6_K layers at 2 tokens: q_a+kv as one WS pair, and a 2-token WS pick for Q6_K o_b.** Today they cost
   9.0 us for kv's own launch and +4.3 us for o_b over 13 layers. Expected ~-0.1 ms. These are table entries plus a
   one-card bench (the ck helper's tables). Bits: WS proof.

Sum after ck-2: ~-0.6 to -0.9 ms, so ~12.6 ms per 2-token check in the gate frame (13.9 today, 13.45 in this
timeline). What is left above ~11.5-12:

- the experts' extra 1.05 ms per token, against a ~0.55 ms byte floor (RoutedU3 at 12 slots runs ~300 GB/s on the
  new bytes);
- the o_a 16-head imbalance, 0.22 ms;
- the second token's small kernels and attention, ~0.3 ms.

Not worth it at 2 tokens: splitting q_a+kv rows across the cards (H3 for blocks: at best -0.1 ms, plus a new sync
point), the head split from 2 tokens (closed, tune91), slot-major experts at small M (closed, tg90) and OWN_HEAD_CQ
(closed).

## 4. What to measure next on six cards

A. **Runtime arms on tp95, no build.** Use BEST + `OWN_MT_CK=1 OWN_QB_OFF=4`, the code and analysis prompts, two
   rounds each. Compare the OWN_SPEC_LOG check ms by M against the CQ default (13.92-13.96 / 16.85 / 18.0 / 20.6 /
   22.7) and keep the usual gates (traces 2-6 identical, SAME AS plain, GLOG_SAME):
   - a1 `OWN_MT_XPUSH=0`
   - a2 `OWN_MT_XPUSH=2`
   - a3 `OWN_XPULL_MIN=6912`
   - a4 `OWN_MT_SKDOTS_MIN=2`
   - a5 `OWN_MT_SKDOTS_MIN=3`
   - a6 `OWN_MT_FIN_QB=0` (shows ck-2's direction early: q_b goes WS, and the finish goes back beside the norms, ~+4
     us per layer)
   - a7 the best of a1-a3 plus a4

   Expected: a1/a3 -0.15 to -0.3 ms at M=2 only, a4 -0.1 to -0.2 at M=2-3, a6 ~-0.25 at M=2-3.
B. **A check timeline of the best arm, and of ck-2 once it is built.** Use `OWN_TIMELINE_CHECKS=20-60`: on this
   prompt that is 12 / 15 / 9 / 4 / 2 checks of 1 / 2 / 3 / 4 / 5 tokens, ~33 MB. Then run `tools/segs.py`
   (wall per segment, who arrives last), `tools/xwait.py` (wait / after / push) and `tools/merged.py` (edit its
   step lists). This gives the light cards' slack at output-a per M after ck-2, which sets fix 1's k per M.
C. **A one-card bench of RoutedU3 with the grouping prologue** at M = 2-6 (bitwise against ExpertGroupM + RoutedU3,
   time against the two launches) before fix 3 goes into a build.

## Notes on the tools

- `/home/steve/dsv41-work/tools/ck_by_m.py`'s step-to-row mapping is right for this file. Check k (step 10000 + k)
  is spec row k-1, so the first index is 19. Its empty "one vs check" table comes from `dsv41_kbusy.py`, which runs
  its comparison when it is imported (no main guard), on `argv[1]` and `argv[2]` = the spec file. On top of that,
  its per-family slope mixes the 1-token checks' one-token kernels with the block kernels, so its slope column is
  not usable on CK1 timelines.
- `tools/` here (CPU only, standard library plus the repo's `dsv41_timeline.py`):
  - `roles.py` groups the kernels of both paths into the same roles (name plus position).
  - `merged.py` builds the pace/light table.
  - `segs.py` gives wall time between exchange completions.
  - `xwait.py` gives exchange wait / after / push.
  - `fams.py` gives per-kernel totals.
  - `seq.py` dumps one step's launch sequence.

  Run them with `python3 -I`.
