# barrier: what the stable mode costs per prompt piece, and what rebalancing can still win

2026-11-15. CPU-only model of one 512-token prompt piece under `OWN_PX_SERIAL=1`, built from the profiled px-512
timeline of tp109 (`runs/tlp109/tlp_px512.txt`, pieces 3-4 of the 3,323-token prompt, default power) and the
one-token timeline `runs/tg109/tl_one.txt`. Script `barrier_sim.py`, full output `barrier_sim.out.txt` (every
number below is copied from it). Run: `nice -n 19 python3 -I barrier_sim.py > barrier_sim.out.txt` (7 min, CPU).

## In plain words

- **The stable mode's cost is mostly the copies themselves, not card imbalance.** With every exchange a six-card
  barrier, a piece costs ~843 ms in the model against ~718 ms with overlap (model ratio 1.174; the measured
  tp115-stable / tp114-overlap 3K reads are 4.93 / 4.19 s = 1.177). Of the 124.84 ms extra, 122.36 ms per piece (14.5 %) is
  waiting for copies that used to run under compute (the expert-activation gather X3 alone 54.22 ms, output-a
  31.70, output-b and FFN rows 15.97 each, engram 4.16). The barriers
  add only ~15 ms of extra imbalance on top of what overlap mode already had.
- **Imbalance (sum of per-segment maxima minus sum of means) is ~50 ms per piece (~6 %).** About 40 ms of it is
  card-level: cards 1 and 2 (230 W, 12 heads) simply have the most work and set the pace in both modes.
  Half of the imbalance sits in the attention block (output-a, attention, q_b rows: head-bound), ~29 % in the
  FFN-in segment (routed gate/up), ~14 % in FFN-out (routed down), ~5 % in output-b. Card 2 is the slowest card in
  almost all of them, card 1 next.
- **(a) heads 4,2,2,4,2,2 is a loss.** The model says +3.4 % (linear head scaling) to +4.3 % (the measured
  8-vs-12-head exponent), because cards 0 and 3 then carry 16 heads and become the slowest in every attention block;
  dropping the pair swaps saves little since their waits were hidden inside the slow cards' time anyway. The real
  A/B on tp115 (st1, 16:52-16:55 today) measured **+18.1 %** (3K 4.93 -> 5.82 s; 10K 15.55 -> 18.44 s), 3.9-5.3 times the model's loss, so most of
  it is something this model does not contain: the 16-head prompt kernels must be
  much slower than linear (a profiled 3K timeline with these heads would show which). Either way: do not use it.
- **(b) row weights help a little and cost decode about as much.** Best prompt vector `OWN_TP_WEIGHTS=34,31,31,33,32,32`
  (more rows on fast cards 0 / 3, fewer on 1 / 2): -0.7 % per piece (-5.8 ms), but decode +0.9 % (+0.082 ms per
  step), since one-token steps are memory-bound and the cards are equal there (the decode optimum is equal rows).
  Break-even ~71 answer tokens per 512 prompt tokens. Net worth it only for long prompts with short answers; the
  rows' 16-row units limit it.
- **(c) no large same-bits lever is left in balance.** All 90 head layouts with 2-4 units per card: the current
  3,3,3,3,2,2 is within 0.03 % of the best. The prompt-only token weights (`OWN_PRT_W`, `OWN_MT_DSPLIT_WA/_WF`) are the
  right tools for the leftover imbalance (no decode cost); a rough emulation suggests <= ~0.7 % there. The big
  remaining lever is the copy time: Gen4 links cost 35.85 ms per piece in the model (copies at Gen5 speed: 807.41 vs
  843.26 ms, -4.3 %), and overlap itself is worth 14.8 % of the stable piece; both are stability decisions, not balance work.

## How the model works

- Each card replays its recorded kernel sequence with the recorded per-kernel times (non-exchange kernels only).
- Barrier boundaries: the pushes `bcs_fire` makes right after each producer (X1 output-a, X2 output-b, X3 expert
  act, X4 FFN rows; 8 per layer, 40 layers, 320 per piece), each followed by the serial wait (`bcs_wait`) in stable
  mode. The engram push (once per piece) has no serial wait; its reader (`px_eng`, layer 1) waits. The push
  sequence (site, layer, half) is identical on all six cards in both pieces (checked); the 321 consumer
  `XchgWaitB` per card map one-to-one onto px_layers' order.
- Card c's copy starts when its producer ends and takes `-11.4 us + 178.7 us x MiB per peer` (fit to the six-card
  push bench in `bcs/README.md`, Gen5) times 1.4. The factor 1.4 makes the model's stable / overlap ratio
  (1.174) match the measured 1.177; at 1.0 / 1.2 the ratio would be 1.124 / 1.149. Card c is released at the latest
  of its peers' (producer end + copy), plus the wait launch floor (1.04 us, p25 of 3,852 waits).
- Pair swaps (cards 0-1, 2-3, the split head groups): publish after attention, whole-group output-a rows, then
  wait for the partner and pull (86.2 us floor, p10 of 640 pulls).
- Check against the profile (overlap mode, Gen5 copies): piece 717.3 / 719.6 ms vs profiled span 723.8-726.8 ms;
  per-card waits reproduce the profile's (e.g. card 4 76.2 vs 78.2 ms, card 0 72.8 vs 81.1 incl. its pair pulls).
- Decode: every one-token exchange is a synchronous pull, so a barrier; cost per barrier = the exchange kernel's
  time on the last card to arrive. Model 8.745 ms per step vs profiled span 8.948 ms.

## Tables (ms per 512-token piece; piece 20003 / 20004)

Stable mode, copies x1.4:

| piece | model | sum of segment maxima | barriers (copy + wait) | sum of segment means | slowest card total busy (card 2) | mean card busy | imbalance (max - mean) |
|---|---|---|---|---|---|---|---|
| 20003 | 842.29 | 722.36 | 122.36 | 672.39 | 707.34 | 667.64 | 49.97 (5.9 %) |
| 20004 | 844.23 | 724.00 | 122.36 | 673.44 | 709.47 | 668.69 | 50.56 (6.0 %) |

Imbalance split: segment-level (sum max - slowest card total) 15.02 / 14.53 ms, card-total (slowest - mean)
39.70 / 40.78 ms. Copy per push at the current split, us (x1.4): X1 396 (12-head cards) / 271 (8-head), X2 and X4
196-200, X3 678, engram 4,147-4,162.

Compute busy per card (piece 20003; experts / dense rows / attention+index / norms+mix / total):
card 0 328.88 / 216.73 / 57.04 / 32.29 / 637.01; card 1 363.23 / 239.73 / 64.58 / 33.83 / 703.62;
card 2 364.34 / 241.64 / 65.09 / 33.96 / 707.34; card 3 341.63 / 224.96 / 60.02 / 33.52 / 662.26;
card 4 349.82 / 200.66 / 45.55 / 42.51 / 640.71; card 5 358.25 / 204.94 / 46.55 / 42.92 / 654.88.
(Profile waits: cards 0 / 3 spend 58.03 / 45.85 ms in pair swaps waiting on partners 1 / 2; cards 4 / 5 78.16 /
64.19 ms in XchgWaitB.)

Where the imbalance sits (both pieces summed):

| segment (ends at) | n | sum max | sum mean | max - mean | share | slowest card (excess ms) | main families of the excess |
|---|---|---|---|---|---|---|---|
| X1 attention block (post, q_a/kv, q_b, attention, output-a) | 160 | 503.04 | 450.82 | 52.22 | 51.9 % | c2 37.8, c1 14.4 | out_a +16.20, attn +15.89, q_b +14.57, pair +4.75, qakv +4.25 |
| X3 FFN in (router, shared + routed gate/up, SwiGLU) | 160 | 528.37 | 499.50 | 28.87 | 28.7 % | c2 11.2, c1 8.8, c5 4.1, c3 2.1, c4 1.7, c0 0.9 | exp_up +26.48 |
| X4 FFN out (routed + shared down) | 160 | 300.69 | 286.61 | 14.08 | 14.0 % | c2 10.0, c1 2.9, c5 1.0 | exp_down +12.75, sh_down +1.22 |
| X2 output-b rows | 160 | 97.52 | 92.92 | 4.60 | 4.6 % | c2 2.8, c1 1.1, c5 0.6 | out_b +4.51 |
| engram rows (once) | 2 | 16.39 | 15.65 | 0.75 | 0.7 % | c2 0.7 | engram +0.72 |

(a) prompt heads (mean of both pieces, stable model 843.26 ms at the current heads):

| layout | model | change |
|---|---|---|
| 4,2,2,4,2,2, head kernels x linear | 872.15 | +3.4 % |
| 4,2,2,4,2,2, head kernels x ratio^1.14 | 879.71 | +4.3 % |
| rough tp115 emulation (`OWN_PRT=3` token weights 3,2,2,3,3,3): current 811.16 -> 4,2,2,4,2,2 | 848.43 | +4.6 % |
| measured 3K read, tp115 stable (st1 c1_p3k_def / c1_p3k_h1) | 4.93 -> 5.82 s | +18.1 % |
| overlap mode (reference) | 718.42 -> 716.42 | -0.3 % |

Measured loss / model loss: 5.3 (linear, tp109 structure), 3.9 (rough tp115 emulation).

Head-scaled kernel time per card and piece (q_b + attention + output-a): c0 133.5, c1 149.8, c2 151.3, c3 140.4,
c4 94.4, c5 97.5 ms (8-head / 12-head on equal-power cards: 0.637, exponent 1.11).

(b) row weights (prompt: stable model; decode: one-token model 8.745 ms per step):

| OWN_TP_WEIGHTS | piece | decode step | note |
|---|---|---|---|
| equal (32 x 6) | 843.26 | 8.745 | today |
| 34,31,31,33,32,32 | 837.46 (-0.7 %) | 8.827 (+0.9 %) | prompt optimum; break-even 71 answer steps per piece |
| 34,32,31,33,32,32 | 837.49 (-5.77 ms) | 8.803 (+0.0584 ms) | joint optimum at 20 answer steps per piece |
| 33,32,32,33,32,32 | 840.73 (-2.53 ms) | 8.756 (+0.0117 ms) | joint optimum at 80 answer steps per piece |
| equal | 843.26 | 8.745 | decode optimum |

Rows at the prompt optimum: output-b / down (td) 896, 816, 832, 864, 848, 864; expert act (tm) 400, 368, 368, 400,
384, 384; engram 4,496, 4,112, 4,112, 4,384, 4,240, 4,256. With heads 4,2,2,4,2,2 the same vector is best (-0.7 %).

(c) head layouts (90 with 2-4 units per card): best 3,3,2,3,3,2 843.05 ms (-0.0 %), current 3,3,3,3,2,2 rank 2,
4,2,2,4,2,2 rank 42. `OWN_PRT_W` scan under the rough emulation (1,506 vectors): 3,3,3,3,2,2 805.22 ms vs today's
3,2,2,3,3,3 811.16 (-0.7 %). This is indicative only: the emulation treats the token-share gathers as tight barriers
and puts them in the same segment as the dot rows that `OWN_MT_DSPLIT_WA` already loads onto cards 4 / 5. Tune
those two knobs together.

## Caveats

- Older engine: tp109 has no `OWN_PRT` token split of q_a + kv / router rows (tp115 default 3,2,2,3,3,3), no skip39,
  no idx_dsplit; the rough PRT emulation moves the piece from 843 to 811 ms, so tp115's balance differs somewhat.
- Profiled timing: per-kernel times only; card speed differences (275 W cards 0 / 3) are baked into each card's
  recorded times, as of 2026-11-13 at default power.
- Copy speed in the stable mode (Gen4) is calibrated, not measured: x1.4 the Gen5 bench, from builds that differ
  (tp114 vs tp115). The imbalance numbers do not depend on it; the copy share does.
- Head scaling is linear (or ^1.14) in heads per card. The measured H1 loss is 3.9-5.3x the model's, so the
  16-head prompt kernels do not scale linearly. Weight scaling is linear in rows per card, at the engine's 16-row units.

## Follow-up: heads split per 2 or per 1 (hypothetical; `barrier_heads.py`, output `barrier_heads.out.txt`)

Same stable-mode model, layouts of 64 heads with 8-16 heads per card (so a group of 8 touches at most two cards).
Split groups get a pair swap (publish after attention, pull the partner's heads of that group at the profile's
pull floor / 4 per head, output-a rows 128 per head). Run: `nice -n 19 python3 -I barrier_heads.py > barrier_heads.out.txt` (1 min).

### In plain words

- **Finer splits would win ~2 % per prompt piece, at 2-head granularity; 1-head adds nothing more.** Best layout
  `12,10,10,12,10,10` (the fast cards 0 / 3 keep 12, the slow cards 1 / 2 drop to 10, the light cards 4 / 5 rise to
  10): 843.26 -> 825.74 ms (-2.1 %) linear, 826.43 (-2.0 %) with the super-linear 16-head curve. One-head moves
  from the best 2-head layouts find nothing better. `11,11,11,11,10,10`: -0.7 / -0.8 %. Units of 4: today's layout
  is already the best (within 0.03 %).
- **Giving cards 0 / 3 more than 12 heads never helps**, even linearly (`14,10,10,10,10,10` -1.2 % linear, +5.2 %
  with the fitted curve).
- **Decode:** unchanged (8.745 ms per step), because one-token steps keep whole groups (`OWN_TP_HEADS_MIN`). If the
  same layout were also used for one-token steps: `12,10,10,12,10,10` 8.731 ms (-0.2 %), `11,11,11,11,10,10`
  8.675 (-0.8 %). Head imbalance savings there are eaten by one pair wait per layer (6.77 us stand-in).
- **The 16-head cost implied by st1 is 2.1-2.3x the 12-head cost (linear would be 1.33x).** That number is only
  loosely determined. It comes from one measured layout and assumes all of st1's loss sits in the two 16-head cards'
  head kernels. The shape between 12 and 16 heads is unknown (piecewise linear assumed). A jump that big for 1.33x
  the work looks like a cliff, not a curve. Between 8 and 12 heads the profile is well determined and linear:
  0.637 raw, 0.652 after the cards' 2.3 % speed difference (linear 0.667). The best layouts stay at <= 12 heads,
  so their numbers hardly depend on the fit.

### Which kernels scale with heads (prompt profile, 8-head cards 4+5 / 12-head cards 1+2, same 230 W)

attention (ScoreM / SoftmaxM / OutM) 0.629, output-a rows 0.632, q_b rows 0.651. Every other family is the same
work on every card (0.97-1.01: routed / shared experts, output-b, q_a + kv, router, indexer 0.969, compressor 0.918,
kv ring 0.951); the dot rows (norms) are 1.259 because `OWN_MT_DSPLIT_WA` puts more tokens on cards 4 / 5. Decode:
q_b +37.14 and output-a +38.81 us per head per step; decode attention (`SparseOutF`) does not grow with heads
(390.2 us at 8 heads, 377.3 at 16).

### Does anything need 4-head units?

Nothing in the data: the indexer and compressor are not split by heads, output-a rows (128 per head) and q_b rows
(512 per head) stay on 16-row / 64-byte lines, and the pair swap already handles two partners per card. What does
assume 4: the prompt score kernel `SparseScoreHG<512, 4>` (76 of 80 attention launches per piece run heads in
groups of 4: a 10-head card needs a 2-head form or tail), the pair-swap head ranges (`pb0 / pb1` in 4-head units)
and the engine's checks (`OWN_TP_HEADS` in units of 4, heads per card % 4).

| layout | prompt L | prompt S | decode if used there too |
|---|---|---|---|
| 12,12,12,12,8,8 (today) | 843.26 | 843.26 | 8.746 (+0.0 %) |
| 16,8,8,16,8,8 (H1, measured +18.1 %) | 872.15 (+3.4 %) | 1004.95 (+19.2 %) | 8.742 |
| 12,10,10,12,10,10 (best at 2 and 1) | 825.74 (-2.1 %) | 826.43 (-2.0 %) | 8.731 (-0.2 %) |
| 12,12,10,10,10,10 | 833.19 (-1.2 %) | 833.87 (-1.1 %) | 8.730 (-0.2 %) |
| 11,11,10,11,11,10 | 830.29 (-1.5 %) | 831.56 (-1.4 %) | 8.673 (-0.8 %) |
| 11,11,11,11,10,10 | 837.15 (-0.7 %) | 836.74 (-0.8 %) | 8.675 (-0.8 %) |
| 14,10,10,10,10,10 | 833.46 (-1.2 %) | 887.45 (+5.2 %) | 8.857 (+1.3 %) |

(ms per 512-token piece, stable mode, copies x1.4; L = head kernels linear in heads, S = f(8) 0.652, f(12) 1,
f(16) 2.30 fitted to st1's 3K read without its first step; decode today 8.745 ms per step.)
