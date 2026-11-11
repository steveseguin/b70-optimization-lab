# DeepSeek V4.1 checks on six cards, tp96: where the time goes and what to change next

CPU-only analysis of the tp96 timelines in `/home/steve/dsv41-work/runs/tg96b/`. Nothing was run on the cards. Every
number comes from a table in `tables/` (made by the scripts in `tools/`), from a run log, or from the source or notes
named next to it.

## In plain words

- **A check of two words takes about 2.5 ms longer than an ordinary one-word step** (12.6 against 10.1 ms in the
  timeline; 13.05 against 10.41 ms in the speed runs). Almost all of that is real work for the second word: the
  expert part of the model (about 1.3 ms), the cards passing twice as much data to each other (0.56 ms), and the
  other matrices handling the second word (about 0.7 ms).
- **The two big wastes found last time are gone**: a matrix that fell into a slow form, and a matrix pair that ran
  as two launches. What is left of last time's list is small: extra push launches 0.2 ms, expert grouping 0.17 ms,
  riders up to 0.2 ms, one slow matrix form 0.09 ms. One new small item: a separate window-append launch, 0.09 ms.
- **Each further guessed word adds about 2.3 ms.** The expert kernels are 41 % of that and take about twice as
  long as reading their data would. The card-to-card exchanges are another fifth and take about three times what
  their data needs.
- **The new attention does each layer in one launch instead of four.** That saves about 0.15 ms per ordinary step
  (plain speed 98.7 to 101.3 words per second).
- **Two of the six cards do twice the attention work**, so the other four wait for them: about 0.6 ms per step,
  0.8-0.9 ms in checks of 4-5 words.
- **Best next steps, largest saving first:**
  1. Each card-to-card pull in one trip instead of two. Saves 0.2-0.3 ms per ordinary step and 0.4-0.7 ms per
     check of 3 or more words.
  2. The four lighter cards compute some of the busy cards' query rows inside launches they already run. Saves
     about 0.2-0.3 ms per step and per check, but only if done that way: as separate launches it was tried and
     gave nothing.
  3. In checks of 4-6 words, two small finishing launches per layer ride inside neighbouring matrices. Saves about
     0.55 ms per such check. This is the surest of the five.
  4. Faster expert kernels for ordinary steps. Saves 0.3-0.6 ms per step, but how is uncertain.
  5. The window append moved inside the check attention launch. Saves 0.05-0.09 ms per check.

## Inputs

| timeline | settings | steps used |
|---|---|---|
| `tl_ck.txt` | BEST + `OWN_ATT_T=1` + `OWN_MT_CK=1` | M1 10021/10025/10026; M2 10020/10022/10027; M4 10024; M5 10023 |
| `tl_ck3.txt` | same | M2 10044/10047; M3 10042/10045/10046/10048/10049; M4 10043 |
| `tl_ck3_d.txt` | BEST only | the same steps as tl_ck3 |
| `tl_one.txt` / `tl_one_d.txt` | ATT on / defaults, one-token steps | 20-27 |
| `../tg95b/tl_ck.txt` | tp95 (`OWN_QB_OFF=4`, before ck-2 / attn-a2) | M2 / M1 for comparison |

- **M** is the number of tokens in a check: guesses + 1. M1 checks run the one-token path.
- **Pace cards** are 2 and 5, with 16 heads each. **Light cards** are 0, 1, 3 and 4, with 8 heads each.
- All values are us per check (or per step), as a mean over the steps and cards named.
- Timelines are aligned causally (`dsv41_timeline.align_causal`).
- There is no M6 check in any timeline. M4 has 2 checks and M5 only 1, so treat those two columns as rough.

Round weights come from `tables/rounds_by_guesses_attck.txt` (ATT + CK runs `code_all_*`, `analysis_all_*`). These
are the number of rounds at 0..5 guesses:

| run | 0 | 1 | 2 | 3 | 4 | 5 | total |
|---|---|---|---|---|---|---|---|
| code | 63 | 64 | 41 | 21 | 14 | 20 | 223 |
| analysis | 27 | 40 | 32 | 24 | 21 | 36 | 180 |

## 1. A two-token check against a one-token check

### 1.1 Totals (tl_ck, ATT + CK)

| | M1 | M2 | difference |
|---|---|---|---|
| wall (span, first start to last end) | 10065 | 12580 | **+2515** |
| pace cards' busy time | 9845 | 12296 | +2451 |
| light cards' busy time | 9851 | 12298 | +2447 |
| pace cards' idle time (span minus busy) | 220 | 284 | +64 |

The speed-run medians are 10.41 and 13.05 ms (+2.64; code, `code_all_1`).

### 1.2 By family (ck2tok layout; `tables/roles_pace_light_m1_m2.txt`)

The tp95 M2 column is the same 2-token check in tg95b. Its last column is the change from tp95 to tp96 at M2, on
the pace cards.

| family | pace M1 | pace M2 | change | light M1 | light M2 | change | tp95 pace M2 | tp96 − tp95 |
|---|---|---|---|---|---|---|---|---|
| embed / broadcast | 4 | 6 | +2 | 4 | 6 | +2 | 6 | 0 |
| engram rows / gate | 114 | 134 | +21 | 114 | 134 | +20 | 134 | 0 |
| head (norm, GEMV, argmax) | 168 | 178 | +10 | 169 | 178 | +10 | 175 | +3 |
| check-only draft features | 83 | 87 | +4 | 83 | 87 | +3 | 88 | −1 |
| mix collapse | 105 | 143 | +37 | 102 | 136 | +34 | 144 | −1 |
| attn pre-norm (+dots at M1) | 263 | 129 | −134 | 260 | 128 | −132 | 129 | 0 |
| q_a + kv rows (+dots at M2) | 771 | 991 | +221 | 767 | 980 | +213 | 1120 | −129 |
| q_a / kv norms | 122 | 117 | −6 | 117 | 113 | −4 | 120 | −3 |
| q_b rows (+finish, rope) | 958 | 1097 | +139 | 648 | 719 | +71 | 1527 | **−430** |
| compressor + indexer | 129 | 158 | +28 | 128 | 159 | +31 | 158 | 0 |
| attention core | 455 | 546 | +91 | 461 | 536 | +75 | 770 | **−224** |
| o_a rows | 749 | 720 | −29 | 438 | 497 | +60 | 718 | +2 |
| o_b rows | 623 | 711 | +87 | 617 | 722 | +106 | 714 | −3 |
| ffn pre-norm (+dots at M1) | 278 | 139 | −138 | 269 | 135 | −134 | 139 | 0 |
| router rows (+dots at M2) | 360 | 624 | +265 | 358 | 619 | +260 | 628 | −4 |
| router pick + finish + shared gate/up | 446 | 447 | +1 | 449 | 447 | −2 | 511 | −64 |
| ExpertGroupM | 0 | 166 | +166 | 0 | 162 | +162 | 163 | +3 |
| experts gate + up | 1291 | 1915 | **+624** | 1279 | 1891 | +612 | 1910 | +5 |
| SwiGLU | 52 | 77 | +25 | 51 | 79 | +28 | 77 | 0 |
| experts down | 875 | 1312 | **+437** | 845 | 1306 | +461 | 1311 | +1 |
| shared down | 253 | 275 | +22 | 252 | 271 | +19 | 274 | +1 |
| MoE combine | 64 | 84 | +19 | 60 | 79 | +19 | 82 | +2 |
| xchg output-a (pull) | 478 | 481 | +3 | 1131 | 1132 | +1 | 500 | −19 |
| xchg output-b | 296 | 377 | +81 | 276 | 358 | +82 | 387 | −10 |
| xchg output-b, PushM | 0 | 102 | +102 | 0 | 90 | +90 | 98 | +4 |
| xchg expert act (pull) | 542 | 606 | +65 | 560 | 638 | +78 | 646 | −40 |
| xchg ffn rows | 309 | 481 | +172 | 351 | 512 | +161 | 475 | +6 |
| xchg ffn rows, PushM | 0 | 100 | +100 | 0 | 89 | +89 | 97 | +3 |
| xchg engram | 43 | 61 | +18 | 41 | 59 | +17 | 60 | +1 |
| xchg check (draft fc), incl. PushM | 15 | 33 | +18 | 18 | 34 | +16 | 45 | −12 |
| **total busy** | 9845 | 12296 | **+2451** | 9851 | 12298 | +2447 | 13202 | **−906** |

Grouped, the pace cards' +2451 us is:

- **Expert work +1271.** Gate + up, down, ExpertGroupM, SwiGLU and MoE combine. 10.48 distinct experts per layer
  instead of 6.
- **Exchanges +559.** Of that, 202 is the two PushM launches.
- **Dense rows +706.** q_a + kv, q_b, o_a, o_b, router, router pick and shared down. These include the stream-mix
  dots, which leave the pre-norms at M2 (−272).
- **Attention +91.** The WindowAppendM launch.
- **The rest +96.**

Per kernel: `tables/kernels_pace_m1_m2_tp96_tp95.txt` and `tables/kernels_light_m1_m2_tp96_tp95.txt`.

### 1.3 Wall time by segment (`tables/segments_tlck_m1_m2_m4_m5.txt`)

Each segment ends at an exchange.

| segment | M1 | M2 | change |
|---|---|---|---|
| A: attention in, attention, o_a, then output-a | 4081 | 4486 | +405 |
| B: o_b, then output-b | 904 | 1188 | +284 |
| C: ffn in, router, gate + up, then expert act | 3086 | 4084 | **+998** |
| D: down + shared, then ffn rows | 1524 | 2278 | **+754** |
| E: engram | 143 | 175 | +32 |
| Z: head + check, then fc | 268 | 314 | +46 |

### 1.4 The ck2tok overhead items now

| ck2tok item (tp95) | tp96 | size now (pace cards, per M2 check) |
|---|---|---|
| q_b in the GR R4 form under the finish rider (~0.44 ms) | **gone** (ck-2 WS_DOTS picks). Per launch: Q8 36.31 → 26.71 us, Q6 38.00 → 23.91 us. q_b role 1527 → 1097. | 0 |
| Q6_K q_a + kv pair as two launches | **gone**. One pair launch of 25.87 us, against 21.16 + 9.11 before. | 0 |
| XchgPushM (each 2-token push is two launches) | **remains**. Only at M2; from M3 output-b and ffn rows are pulls. | 202 us (102 + 100) |
| ExpertGroupM | **remains** (4.15 us × 40). eg-fold-1 closed it as a fold. | 166 us. At M3 / M4 / M5: 206 / 225 / 269. |
| Dots riders | **remain, small**. See below. | ≤ ~210 us, including the rows' own growth at M2 |
| o_b Q6_K form | **remains**. Q6 `DenseRowsG<GemvQ6KP<32u>,1u>` 18.79 us at M2 against 15.05 at M1 (×13 layers). Q8 WS 17.27 against 15.84 (×27 layers). | ~49 + 39 us |
| new: WindowAppendM | its own launch at M ≥ 2 (2.24 us × 40). The one-token SparseOutF appends inside its launch. | 90 us |

How the dots riders break down. The dots leave the pre-norm launches at M2:

- Pre-norm: 6.83 → 3.23 us (attention), 6.94 → 3.48 us (FFN).
- They ride the q_a + kv pair and the router instead. Each pair of launches together:
  - Q8 layers: 26.7 → 27.5 us (+22 us per check).
  - Q6 layers: 24.1 → 29.1 us (+65).
  - Router: 15.9 → 19.1 us (+126).

In the speed runs, `OWN_MT_SKDOTS_MIN=2` (the dots as their own launches) took 13.25 ms at M2, against 13.31-13.37
for ck. The 3-token version took 15.60, against 15.71-15.77. Analysis was neutral (`tables/runtime_arms_check_ms.txt`).
The rider overhead is therefore at most about 0.1 ms.

The push arms did not help:

| arm | M2 check (ms) |
|---|---|
| ck alone | 13.31-13.37 |
| `OWN_MT_XPUSH=0` | 13.36 |
| `OWN_MT_XPUSH=2` | 15.65 |
| `OWN_XPULL_MIN=6912` (pulls at M2) | 13.68 |

### 1.5 The pace cards' lead at output-a

From `tables/segment_a_lead_pace_vs_light.txt`. The lead is the pace cards' arrival minus the light cards' mean
arrival.

| case | lead per step | per layer |
|---|---|---|
| one-token step, ATT (defaults) | 584 us (577) | 14.6 us (14.4) |
| M1 check | 618 | 15.4 |
| M2 check | 622 / 642 | 15.5 / 16.1 |
| M3 check | 735 | 18.4 |
| M4 check | 794 / 811 | 19.8 / 20.3 |
| M5 check | 872 | 21.8 |
| defaults (tl_ck3_d) M2 / M3 / M4 | 1032 / 1314 / 978 | 25.8 / 32.9 / 24.4 |

Where the lead comes from:

- **At M2:** q_b (pace 1097, light 719: +378) and o_a (720 against 497: +223). Attention adds about 10.
- **At one token:** q_b +301, o_a +307, attention equal (460 on both).

The light cards spend that wait inside the output-a exchange: 0.61-0.65 ms per light card on the one-token path
(`tables/one_token_segments_xwait_att_vs_default.txt`).

The new forms halved this imbalance. Same steps, defaults against ATT + CK, on the pace cards
(`tables/roles_same_checks_default_vs_attck_m2_m3_m4.txt`, `tables/segments_tlck3*.txt`):

- Wall: M2 13825 → 12974, M3 15906 → 14925, M4 17782 → 17228.
- At M3 the gain is q_b −656, attention −262, q_a + kv −178, o_a −65.

## 2. Each token past two: the slope

Pooled tl_ck + tl_ck3, ATT + CK (`tables/slope_by_m_attck.txt`): M2 5 checks, M3 5, M4 2, M5 1.

- **Span:** 12738 / 14925 / 17219 / 19860 us. That is **2366 us per token** (steps +2188, +2294, +2641).
- **Speed-run medians:** 13.05 / 15.45 / 17.59 / 20.28 / 22.66 ms (steps +2.40, +2.14, +2.69, +2.38).
- **Pace busy:** 12459 / 14616 / 16874 / 19320 us, **2284 us per token**.

| family (pace cards) | M2 | M3 | M4 | M5 | slope per token | floor per token | measured / floor |
|---|---|---|---|---|---|---|---|
| **experts gate + up** | 1997 | 2506 | 3105 | 3671 | **562** | 269 (bytes) | 2.09 |
| **experts down** | 1367 | 1727 | 2158 | 2477 | **376** | 171 (bytes) | 2.20 |
| **exchanges, total** | 2209 | 2516 | 3133 | 3616 | **484** | ~167 (bytes at 25 GB/s) | ~2.9 |
| o_b rows | 716 | 860 | 877 | 1032 | 96 | dense rows together ~100 (FMA floor, K5 note) | ~4 |
| q_b rows | 1102 | 1224 | 1274 | 1395 | 93 | (same) | |
| attention core | 558 | 580 | 649 | 752 | 65 | | |
| o_a rows | 722 | 745 | 790 | 919 | 64 | (same) | |
| q_a + kv rows | 995 | 1112 | 1056 | 1199 | 56 | (same) | |
| router pick + shared gate/up | 451 | 571 | 534 | 637 | 52 | (same) | |
| shared down | 278 | 329 | 354 | 412 | 43 | (same) | |
| ExpertGroupM | 166 | 206 | 225 | 269 | 33 | | |
| head | 178 | 228 | 228 | 265 | 26 | | |
| engram rows | 135 | 144 | 176 | 207 | 25 | | |
| DSPLIT finishes alone (2 kinds) | 0 | 0 | 669 | 653 | (a step at M4) | | |
| router rows (+dots) | 630 | 866 | 468 | 508 | (dots leave at M4) | | |

Here is how the exchange slope splits:

| kind | us per token |
|---|---|
| expert act | 199 |
| output-a | 119 |
| ffn rows | 103 |
| output-b | 100 |
| engram | 18 |
| check | 7 |

The PushM launches drop out at M3 (−62).

The floor per token is the bytes a card pulls per token and layer, times 40 layers, at 25 GB/s. Per token and layer
a pace card pulls:

| exchange | KB |
|---|---|
| output-a | 24.6 |
| output-b | 17 |
| expert act | 46 |
| ffn rows | 17 |

That is about 4.2 MB per token, or about 167 us at 25 GB/s.

- **Which family dominates the slope: the routed experts.** They take 938 us per token, 41 % of the pace cards'
  2284 us. Next come the exchanges (~484, 21 %), then the dense rows (~404, 18 %).
- **The experts are 2.13× their byte floor per token** (938 against 440 at 550 GB/s). The floor comes from the
  distinct experts per block in the u84 p3k id dump (`tables/expert_byte_floor_by_m.txt`):

  | M | distinct experts | floor (us per check) | floor step | measured experts (pace) | measured / floor |
  |---|---|---|---|---|---|
  | 1 | 6.00 | 746 | | 2166 | 2.90 |
  | 2 | 10.48 | 1308 | +561 | 3364 | 2.57 |
  | 3 | 14.34 | 1791 | +483 | 4233 | 2.36 |
  | 4 | 17.80 | 2223 | +432 | 5263 | 2.37 |
  | 5 | 21.05 | 2628 | +405 | 6148 | 2.34 |
  | 6 | 24.03 | 3000 | +372 | (no timeline) | |

- **The per-token cost is set by the slot count, not the bytes** (`tables/experts_vs_floor_by_format.txt`). Every
  format adds almost the same time per token whatever its block size, while the floors differ by almost 2×:

  | format | measured per token | floor per token |
  |---|---|---|
  | gate + up | 14.0-15.4 us per layer | 4.9-9.0 |
  | down | 9.7-10.0 us per layer (Q2_K, 1 layer: 16.1) | 3.2-5.8 |

  That fits the cost being the per-slot x loads and FMA chains, which are redone for every row (pp92 / rux notes),
  rather than weight reads. IQ1_S gate + up is the furthest from its floor, at 3.4-4.3× at every M.
- **At M4, DSPLIT switches on** (`mt_dsplit_min=4`). It adds the two mix finishes as lone launches
  (`RowsP<TokRows<HcFinishRows>>`, 8.1-8.6 us × 80, 669 us per check), adds the dot rows of each card's own tokens to
  the FFN pre-norm (+143), and removes the router's dots rider (−397). The finishes run alone because
  `mt_dsplit_fin=2` resolves to 0 under `OWN_MT_WS`: output-b and shared down have no WS_DOTS entries
  (`backend_sycl_v41_mt.inc` `fride`). This is lever 3 below.

## 3. The one-token step

### 3.1 What the new attention changed (tl_one_d against tl_one, steps 20-27)

From `tables/one_token_attention_per_layer_pace.txt`:

| layers | defaults: launches per layer, us per layer | `OWN_ATT_T=1`: launches per layer, us per layer | per step |
|---|---|---|---|
| 38 layers, window + compressed rows | 4, 15.42 | 1 (`SparseOutF`, window append inside), 11.54 | −147 us |
| 2 layers, window only | 4, 13.79 | 1, 10.45 | −7 us |

- **Attention:** pace −154 us per step, light −158 (`tables/roles_pace_light_one_token_att_vs_default.txt`).
- **Busy:** −124 us. **Span:** 9903 → 9774 us (−129). **Launches:** 1053 → 933 per step.
- **Plain 128-token runs:** 99.49 / 97.87 tok/s (`d96_*`) against 101.22 / 101.44 (`att_*`). That is −0.17 to
  −0.36 ms per token.

### 3.2 The pace card's budget (tl_one, ATT)

From `tables/one_token_timeline_report_att.txt` and `tables/one_token_segments_xwait_att_vs_default.txt`.

| | ms per step |
|---|---|
| span | 9.769 |
| busy | 9.588 (98 %) |
| — work outside exchanges | 7.914 |
| — exchange kernels | 1.674: waiting for a peer 0.307, after the last arrival 1.367 |
| idle | 0.182: device gaps 0.146, host late 0.036 (step 23 has a ~0.2 ms host-late outlier) |

The light cards spend 2.22-2.32 ms in exchanges, 0.79-0.90 of it waiting (0.61-0.65 at output-a).

Top 10 families on the pace cards (us per step), against the byte floors:

| # | family | us | floor | measured / floor |
|---|---|---|---|---|
| 1 | experts gate + up | 1271 | 456 | **2.79** |
| 2 | q_b rows (16 heads) | 939 | 754 | 1.25 |
| 3 | experts down | 861 | 291 | **2.96** |
| 4 | q_a + kv rows | 761 | 659 | 1.15 |
| 5 | o_a rows (2 groups) | 744 | 604 | 1.23 |
| 6 | o_b rows | 615 | 509 | 1.21 |
| 7 | xchg expert act | 566 | | |
| 8 | attention core | 460 | | |
| 9 | xchg output-a | 452 | | |
| 10 | router pick + finish + shared gate/up | 434 | 271 | 1.60 |

Where the floors come from:

- Dense floors: the per-layer byte floors in the step-budget note (Q8 27 layers, Q6 13 layers).
- Expert floors: `tables/expert_byte_floor_by_m.txt` at M=1.

Next in size come router rows 353 (floor 302), xchg ffn rows 304, xchg output-b 294, the two pre-norms (with dots)
269 + 254, and shared down 245 (floor 137). The head is 167 against 165.

Grouped, the pace card's 9.59 ms busy is:

| group | ms | floor (ms) |
|---|---|---|
| weight-reading kernels | 6.50 | 4.15 |
| exchanges | 1.65 | 0.61 (step-budget note) |
| norms with dots | 0.64 | |
| attention | 0.46 | |
| other small ops | 0.34 | |

Above their floors:

- **Experts: 1.39 ms.** The largest single gap.
- **Exchanges: about 1.0 ms**, of which 0.76 is after the last arrival.
- **Dense rows: 0.86 ms** in total. Each is about 1.15-1.25× its floor; router pick + shared is 1.6× and shared
  down 1.8×.

## 4. The next five structural levers, ranked

The arithmetic is in `tools/levers96.py`, with its output in `tables/lever_estimates.txt`. Savings are per check of
M tokens (M1 = the one-token path, which also covers plain decoding and every zero-guess check). The per-round
figure is the mean over the round weights above.

| # | lever | saving per one-token step / M1 check | per check, M2 / M3-6 | per round (code / analysis) | change | confidence |
|---|---|---|---|---|---|---|
| 1 | Pull exchanges in one round trip (data and flag together) | 0.22-0.34 ms | 0.22-0.34 / 0.44-0.67 ms | 0.32-0.49 / 0.36-0.55 | kernel (XchgPull + the producers' writes) | medium-low |
| 2 | The 16-head cards' q_b rows ride the light neighbours' own q_b launches (pushed from inside that launch) | 0.21-0.27 | 0.19-0.23 / 0.18-0.29 | 0.20-0.25 / 0.21-0.26 | kernel + scheduling | medium-low |
| 3 | DSPLIT finishes ride o_b's and shared down's launches at M4-6 | 0 | 0 / 0.36-0.66 at M4-6 (central 0.55) | 0.09-0.16 / 0.17-0.29 | kernel table (WS_DOTS entries) | **high** |
| 4 | Routed expert kernels on the one-token path | 0.30-0.64 | not estimated | 0.08-0.18 / 0.05-0.10 | kernel | low |
| 5 | WindowAppendM inside the check attention launch | 0 | 0.05-0.09 at every M ≥ 2 | 0.04-0.06 / 0.05-0.07 | kernel | high |

**1. One round trip per pull.**

- Why: the step-budget note found a pull costs ~12.2 us, the same as an idle bench where all cards arrive together
  (e81b, 11.9 us). The cost is two PCIe round trips (read the flags, then read the data), not waiting. tp96 agrees:
  after the last arrival, one-token output-a takes 10.6 us and expert act 11.2 us on the pace card (11.1-11.8 on
  the light cards).
- Derivation:
  - Take away the launch (≥ 2.2 us) and the bytes (27-46 KB at 25 GB/s, ~1.5 us). That leaves ~7.2 us for two
    round trips, so one round trip is 2.7-4.1 us.
  - The one-token path and M2 have 83 pulls (output-a, expert act, engram). From M3 there are 163, because
    output-b and ffn rows become pulls once a slice is ≥ 8192 B.
- Form: each 16-byte vector (or each 64-byte line) carries the exchange's sequence word. The reader polls the data
  itself and re-reads stale vectors.
- Bitwise: the same values move.
- Risks:
  - The tag costs payload (4 bytes of 16, or 4 of 64).
  - It assumes a vector store lands whole.
  - K7-1's stale-L1 failure says to run a six-card stale-read pre-check, like xov1, before the engine patch.

**2. q_b rows riding the helpers' own launches.**

- This is the in-flight qb-off-2 idea, with the condition that decides it.
- Inputs:
  - Each card's q_b per check.
  - The lead per layer from section 1.5.
  - qb-off-1's measured push rate: 4.0 us per 8 KB, about 2 GB/s.
- Derivation:
  - Marginal cost per row = (pace q_b − light q_b) / 40 / 4096. That is 1.89 ns at M1 (qb-off-1 measured 1.9),
    2.33 at M2, 2.70 at M3, 3.30 at M4, 3.55 at M5.
  - For k heads per helper, the gain per layer = min(the heavy card's saving 2k × 512 rows × rate, lead − the
    helper's cost k × 512 × rate − push time).
  - Best: k = 4 at M1 (6.6 us per layer), k = 3 at M2 (5.8), k = 2 at M3-M5 (5.5-7.3).
- Two conditions:
  - **The moved rows must ride the helper's existing q_b launch.** qb-off-1 put them in their own launch, which
    costs ~3.8 ns per row + 5.3 us fixed per layer, and that is why it gave nothing.
  - **They must come first in that launch and be stored into the heavy card from inside it** (XchgP-style rows).
    The heavy card waits for the flags in its rope launch. If the push only starts after the helper's launch
    ends, it lands after the heavy card's own shortened q_b, and the gain disappears.
- This puts qb-off-2 at 0.18-0.29 ms per check, below its 0.29-0.57 ms estimate.
- Weights: the helpers need the moved rows. Cards 1 and 4 already hold them; cards 0 and 3 need ~103 MB more
  (qb-off-1 note).

**3. DSPLIT finishes as riders** (M4-6).

- Today: the two lone `HcFinishRows` launches cost 669-671 us per M4 check and 653 per M5 check
  (`tables/kernels_pace_m3_m4_m5.txt`).
- Riding cost: the same finish riding q_b costs 0.1-3.6 us per launch, mean 1.3 (`WsTab<8,1280>`, WS_DOTS minus
  WS_PLAIN bench: 3 tokens 1.2, 4 3.6, 5 0.1, 6 0.4).
- Saving: 0.36-0.66 ms per M4-6 check, central 0.57 at M4 and 0.55 at M5.
- The change: WsTab WS_DOTS entries for output-b (8,192 columns, Q8_0 / Q6_K) and shared down (2,304 columns,
  Q8_0 / Q5_K) at 4-6 tokens, as ck-2 added for q_b. Then `fride()` can keep the riders under `OWN_MT_WS`.
- A free test first: `OWN_MT_DSPLIT_FIN=1`, a runtime switch never run at checks. The bench's dense-vs-WS penalty
  for these launches is small (o_b Q8 4 tokens 17.9 against 16.2 us, 5 tokens 21.0 against 19.7; shared down Q8 8.2
  against 6.8 and 10.3 against 7.5; Q5 9.1 against 7.4 and 10.4 against 8.5), about 0.11-0.14 ms per check, so it
  could save ~0.4 ms. But q_b's history (G R4 + finish 46.7 against WS + finish 32.0 at 4 tokens) shows a rider
  can push a matrix into a far slower form. Read which form its trace picks.

**4. Expert kernels, one-token path.**

- The gap: 2132 us against a 747 us byte floor (2.85×). Every format is at 2.4-4.3× its floor at M1.
- Known limits:
  - Production is issue-bound (pcs1: busy 48 %, ALU 22 %, send 17 %).
  - The float operations per weight are fixed by the bitwise order.
  - K2's packed-lane forms cut 14-30 % of the instructions per weight but lost to per-lane x loads. The note's
    condition for a retry: x permuted by its producer, so one block read hands each item its own values.
- Estimate: 14-30 % of the measured time, 0.30-0.64 ms per step and per zero-guess check (+3-7 % plain speed).
- The change: the expert kernels plus their x producers (the FFN pre-norm for gate + up, SwiGLU for down).
- Checks of 2+ tokens use the expert-major RoutedU kernels. There the per-slot x loads and FMA chains dominate, not
  the decode. Not estimated here.

**5. WindowAppendM folded into the check attention launch** (M ≥ 2).

- Today: 2.24-2.31 us × 40 = 90-93 us per check, at every M. One-token SparseOutF already appends inside its launch.
- Estimate: 60-95 % of that is saved.

**Near neutral: a free runtime re-test, not a lever.**

- **Head split for checks** (`OWN_TP_HEADS_MIN=3` or `4`). It saves about half the lead per layer and adds a pair
  exchange of P us per layer. P is at least 7.3 us, because e79's one-token split lost where it would have saved
  0.5 × 14.6. P is about 11.5 us if tune91's neutral result at 2 tokens went with the ~22.9 us lead of the tp95
  timeline.
- With today's leads that gives +0.02 to −0.15 ms at M2 and −0.02 to −0.10 ms at M4-M5 (a minus sign is a gain).
  It won +1.2 % in tune91 from 3-4 tokens, before ck-2. With the defaults' leads (25.8-32.9 us per layer in
  tl_ck3_d), the same arithmetic gives the 1.4-9.1 us per layer that would explain that win. ck-2 halved the lead,
  and the gain went with it.

**Closed by arithmetic, or measured.** Do not spend card time on these.

- **o_a rows to a helper.** Its input exists only on the heavy card after attention. The helper pays a pull, a
  launch and the rows (+20.1 us) against a 4.7 us saving. Net −1.5 us per layer.
- **ExpertGroupM folded into gate + up.** eg-fold-1 was slower at 2-6 tokens. The launch itself is 166-269 us per
  check at M2-M5, which is the most any fold could save.
- **Push arms** xp0 / xp2 / xpl, **SKDOTS_MIN** 2 / 3, **FIN_QB=0**: see section 1.4 and
  `tables/runtime_arms_check_ms.txt`.
- **RUX row tiles at checks**: 0-17 % slower (rux README).
- **XL2 prefetch during exchanges**: plain 97.9-99.3 tok/s (tg90 `d90_*`, `a89_*`) → 84.5-84.7 (`xq_*`).

**Already in flight.** k7-2 (stream-mix dot partials ride the exchanges; 0.15-0.3 ms per plain step in the
strategy note) and qb-off-2 (lever 2 above). The persistent layer kernel (S1 in the step-budget note) is the
long-range answer to the exchanges, gaps and small launches together. It is a rewrite, not a next step.

**Suggested order:**

1. `OWN_MT_DSPLIT_FIN=1` and `OWN_TP_HEADS_MIN=4` with ATT + CK in the next gate, which are free.
2. Lever 3's table entries, which are sure.
3. The stale-read pre-check bench for lever 1, which decides the largest item.
4. Lever 2 built as riders, with a six-card timeline before the full patch (the qb-off-1 lesson).
5. Lever 4 only with a new idea for the x layout.

## Tools (`tools/`, run with `python3 -I`)

| tool | does |
|---|---|
| `roles96.py` | Role classifier for tp96 launch names. Roles come from the matrix format and column blocks plus position: the router is the H16 160 launch before a Route*; rope after q_b counts as q_b; a lone HcFinishRows is the attention finish before o_b, else the FFN one; pre-norms take the next launch's side; an exchange takes its producer's kind. `classify(t, step, card)` returns (role, launch, layer). Fixes ck2tok's router / compressor mix-up at M ≥ 4. |
| `merged96.py` | Pace against light per role, for any number of groups (`LABEL=TIMELINE@s1,s2`) |
| `fams96.py` | Per-kernel us, launches and us per launch by role (`CARDS LABEL=TIMELINE@...`) |
| `segs96.py`, `xwait96.py` | ck2tok's segment and exchange-wait readers on roles96 |
| `slope96.py` | Per-role us by M, pooled; span; least-squares slope; step increments |
| `floor_experts.py`, `experts_vs_floor.py` | Expert byte floor per M from an id dump plus a timeline's formats; per-format measured against floor |
| `attn_layers.py` | Attention per layer, two one-token timelines |
| `lead96.py` | The pace cards' lead at output-a, from segs96 output |
| `levers96.py` | The lever arithmetic in section 4 |

Tables (`tables/`):

- Section 1: `roles_pace_light_m1_m2.txt`, `kernels_*_m1_m2_tp96_tp95.txt`, `segments_tlck_m1_m2_m4_m5.txt`,
  `exchange_waits_tlck_m1_m2_m4_m5.txt`, `segment_a_lead_pace_vs_light.txt`,
  `roles_same_checks_default_vs_attck_m2_m3_m4.txt`, `segments_tlck3*_m2_m3_m4.txt`, `runtime_arms_check_ms.txt`.
- Section 2: `slope_by_m_attck.txt`, `expert_byte_floor_by_m.txt`, `experts_vs_floor_by_format.txt`,
  `kernels_pace_m3_m4_m5.txt`.
- Section 3: `roles_pace_light_one_token_att_vs_default.txt`, `one_token_attention_per_layer_pace.txt`,
  `one_token_segments_xwait_att_vs_default.txt`, `one_token_timeline_report_att.txt`.
- Section 4: `lever_estimates.txt`, `rounds_by_guesses_attck.txt`.
