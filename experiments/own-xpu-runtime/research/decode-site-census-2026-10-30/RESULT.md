# Where decode time goes on one B70, per site and per row count (2026-10-30)

Diagnostic measurement for the plan in [IDEAS.md, "Toward 200 tok/s"](../../IDEAS.md). Device times are profiler
timestamps, not speed claims. Projections at the end are CPU arithmetic over these tables and are labelled as such.

## In plain words

- **A decode step is about half "big" work and half "small" work.** On one card, rank 0's step (layers 0–22) is
  10.1 ms of GPU time in 863 kernels; rank 1's (layers 23–47 plus the output head) is 11.8 ms in 938 kernels. The GPU
  is almost never idle inside a step (0.12 ms of gaps).
  - About 5–6 ms per rank is dense weight reads. The big ones (attention output, GDN qkv, the hyper-connection
    projections, the output head) run at 65–100% of what the memory can deliver (the head streams at 590 GB/s); the
    Q4_K/IQ4_XS projections run at 50–60%, the small shared-expert ones at 25–30%.
  - About 2.4–2.7 ms per rank is the routed experts (10 per layer). They run at only 26–42% of memory speed: they are
    limited by unpacking the 2–4-bit codes, not by memory.
  - About half of all GPU time (5.0 / 5.4 ms) is spent in kernels shorter than 20 µs: 84% of all launches. In the
    four-card layout most of this (3.8 / 4.2 ms per stage) is done again on both cards of a stage.
- **Checking more than one row at a time is expensive today, worse than the old "1.6×" note.** There is no multi-row
  decode path. Running rows one after another costs 2.0× for two rows. The engine's batched prompt-reading path costs
  2.7–3.0× for 2–4 rows, because its kernels are tuned for 256-row chunks (expert kernels alone cost 5× there).
  Choosing the already-existing exact small tiles per site (no new kernels, measured here) brings two rows down to
  about **1.55×** and four rows to about **2.2×**.
- **Experts do not get much cheaper with more rows, even in theory.** Consecutive real tokens share only about 4 of
  their 10 experts. Two rows touch 15.8–16.6 distinct experts, four rows 25–28. A perfect weight-stationary expert kernel
  still pays for every new expert.
- **What each idea can be worth (projection):** with the measured per-site times, a perfect multi-row kernel set (#1)
  makes two rows cost about 1.2× and four rows about 1.5× instead of 2× / 4×. Deeper speculation (#2) only pays once
  #1 exists; with today's kernels every deeper option is slower than today's one-guess pipeline. Glue fusion (#3) and
  faster experts (#4) each add 10–25%. Four cards (TP2 per stage) add 20–25% on top.
- **No single idea reaches 200 tok/s, and on these measurements no combination does under realistic costs.**
  Only the full stack (#1 + #2 + #3 + #4) on four cards passes 200, and only in an upper bound that assumes the two
  pipeline stages overlap perfectly and a rejected guess costs nothing (206–218 tok/s). Charging a rejected block its
  rank-0 redo, the best stack projects to about 145 tok/s; verifying in one batch with the ranks in series, about
  125; one stage over all four cards (#5, no miss cost) about 150, or 190 if its card-to-card exchanges were free.
  120 tok/s needs #1 + #3 on four cards; 150 needs everything at its best case. The rest of the way to 200 has to come
  from what the list does not cover: the draft (1.3 ms per chain step, 4 ms per cycle at depth 3), the stage-to-stage
  exchange cost (about 2 ms per stage on four cards) and acceptance (at 90% per position the same stack projects to
  about 195 with redo costs).
- **Recommended next build:** small-row (M ≤ 4) weight-stationary kernels for the dense projections that the existing
  tiles do not yet cover well: the Q6_K/Q4_K/IQ4_XS projections (gdn.qkv, gdn.z, qsa.qgate) and the shared expert.
  They hold the largest measured gap at two rows (2.2 ms per rank). With them a two-row verify costs about 1.33× a
  one-row pass instead of 1.55×, which is what makes a two-row verifier pay at 76% acceptance (it must stay under
  1.52×). Details at the end.


## What was measured, and how

- **Engine:** r7 sources (`b51c9e8d803e`) plus one diagnostic, `OWNRT_SITE_TRACE=1` (binary `b0b8d593d530`,
  [receipt](../../engine/receipts/b0b8d593d530.json)). With a profiling queue (`--timing launch`) every kernel event
  that `drain()` already times is also written to `rank<r>/site-trace.jsonl` with its phase (decode half, draft row,
  prefill chunk of ≤ 8 rows) and its full site label. No arithmetic, ordering, drain or wait changes.
- **Exactness of the diagnostic:** both ranks were run profiled and unprofiled (`--timing token`) on identical inputs.
  Full state dumps (rank 1: 1,079 buffers; rank 0: 1,029), every output row of every mode, rank 1's 144 decode tokens
  and rank 0's 144 draft guesses are identical ([rank 1](results/exactness-rank1-A1-vs-C1.json),
  [rank 0](results/exactness-rank0-B0-vs-C0.json)). Rank 1's tokens also equal the suite oracle (144/144).
- **Layout:** one card (23) per rank process, run one after the other with the lab's rank harness protocol
  ([census_driver.py](census_driver.py), a lab copy of the prefill-speed rank drivers; [run_census.sh](run_census.sh)).
  Context 65,536, F32 activations/state, the r7 launch environment, no TP flags.
- **Real tokens:** the suite prompt `code-review` (90 tokens) followed by the model's own 512-token greedy answer
  ([inputs](inputs/code-review-seq.json)). Each request reads positions 0–127 as one prompt chunk and then measures the
  window 128–271 (generated text) in one mode: decode (M = 1, rank 0 also runs the draft with its head), or batched
  chunks of exactly M = 1, 2, 3, 4 rows. Rank 1 is fed rank 0's real output rows; rank 0's draft is fed rank 1's real
  final rows (its guesses hit 108/144 = 75.0% in this window). Statistics skip the first 8 window positions.
- **Which kernel ran:** decode (M = 1) runs the prepared r7 one-row commands. The batched path
  (`prefill_engine.hpp`) runs: dense projections through the reuse2 token-row tiles (M ≥ 2; at M = 1 the one-row
  kernels, same times as decode), routed experts through the expert-grouped kernels (bucket pass + tile kernel, all M),
  multi-row native kernels for recurrence/conv/norm/mix/route/gather/combine/QSA select (one launch for M rows),
  QSA attention in groups of ≤ 4 rows, and per-row replays for the rest (e.g. `moe`: 46 → 92 → 138 → 184 launches).
  Two more runs cycle every compiled exact tile configuration per chunk (`OWNRT_PREFILL_REUSE2_CYCLE`,
  `OWNRT_PREFILL_EXPERTS_CYCLE`, existing diagnostics; [tiles.py](tiles.py)): reuse2 1x32, 4x8, 1x4, 1x1, 2x16 and the
  existing kernel; experts 2x4, 1x4 and the existing per-slot kernel. Every configuration's output rows equalled the
  decode rows bit for bit.
- **Routes:** two more runs with the existing `OWNRT_PREFILL_ROUTE_DUMP` give every chunk's expert ids per layer
  ([routes.py](routes.py)).
- **Roofline:** no separate copy test was needed: the target head (`output.weight`, 521 MB Q6_K) streams at
  **590 GB/s** in this trace and the PLE key projection (52 MB BF16) at 528 GB/s, matching the historical 540–590 GB/s.
  Weight bytes per site come from the loader placement; the engine's device weight bytes equal the stored GGUF bytes
  (rank 0: 24.653 GB both; rank 1: 30.06 GB), so no layout expansion is hidden in the GB/s figures.
- **Host overhead** (unprofiled wall minus device span): rank 0 0.43 ms per half, rank 1 0.38 ms, draft 0.12 ms.
  Profiling adds host time inside a half (rank 1: 7.8 ms of event reads at its mid-half export drain), not kernel time:
  unprofiled walls (10.55 / 12.29 ms) equal device spans plus those overheads.

| | rank 0 (layers 0–22) | rank 1 (layers 23–47 + head) | draft step (head on / off) |
| --- | ---: | ---: | ---: |
| device span per decode half | 10.12 ms | 11.92 ms (head 1.03 ms) | 1.205 / 0.77 ms |
| summed kernel time | 10.00 ms | 11.79 ms | 1.20 / 0.76 ms |
| gaps inside the half | 0.12 ms | 0.13 ms (+ the export drain) | 0.007 ms |
| launches | 863 | 938 | 50 / 45 |
| unprofiled wall per call | 10.55 ms | 12.29 ms | 1.32 / 0.89 ms |
| weight bytes read at M = 1 | 2.33 GB (floor at 590 GB/s: 3.9 ms) | 3.07 GB (floor 5.2 ms) | |
| batched path, M = 1 / 2 / 3 / 4 rows (span) | 18.98 / 27.83 / 28.81 / 30.73 ms | 20.49 / 29.44 / 29.82 / 31.95 ms (no head) | |
| best existing tiles, M = 2 / 3 / 4 (summed busy) | 15.50 / 18.16 / 21.81 ms | 16.73 / 19.72 / 23.61 ms | |
| ... as a multiple of the one-row pass | 1.55× / 1.82× / 2.18× | 1.55× / 1.83× / 2.19× | |

By class (rank 0 / rank 1, summed per half): bandwidth-bound (≥ 65% of 590 GB/s) 3.31 / 4.74 ms; instruction-bound
3.18 / 3.18 ms; state/latency-bound (no weights, ≥ 10 µs per launch) 0.88 / 0.93 ms; minimum-duration (median launch
under 10 µs; the shortest kernels take 2.0–2.5 µs) 2.63 ms in 575 launches / 2.93 ms in 630 launches.

## Per-site table (both ranks)

Times are device microseconds per pass, summed over the rank's layers (medians over 136 decode halves and 34–136
chunks). "Batched path" is today's prefill code with its default tiles; "four cards" is how the record layout
(`tptsxqc`) handles the site: split between the two cards of a stage, or replicated on both
(state-bundle/build/source-v4/rank.hpp:700–942). Fused partners have no launch of their own (gdn.b in gdn.a, qsa.ik in
qsa.iq, hc.*.inject and shared_gate in their neighbours).

**Rank 0** (layers 0-22 + draft): device us per decode half, summed over the rank's layers

| site | M=1 decode us (launches) | us/launch | weight MB | GB/s | class | prefill path M=1 / 2 / 3 / 4 us | t(M)/t_decode(1) M=2 / 3 / 4 | four cards |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| attention | 860 (23) | 37.2 | 384.4 | 447 | bandwidth-bound | 861 / 1263 / 1264 / 1281 | 1.47 / 1.47 / 1.49 | split |
| gdn.qkv | 817 (18) | 44.9 | 369.9 | 453 | bandwidth-bound | 826 / 1874 / 1879 / 1910 | 2.30 / 2.30 / 2.34 | split |
| expsgate | 812 (23) | 32.3 | 132.5 | 163 | instruction-bound | 4604 / 4487 / 4303 / 4654 | 5.52 / 5.30 / 5.73 | split |
| expsdown | 797 (23) | 37.2 | 179.7 | 226 | instruction-bound | 1432 / 2417 / 3053 / 3765 | 3.03 / 3.83 / 4.72 | split |
| expsup | 769 (23) | 30.6 | 132.5 | 172 | instruction-bound | 4578 / 4462 / 4284 / 4594 | 5.80 / 5.57 / 5.97 | split |
| gdn.recurrence | 569 (36) | 15.8 | 0.0 | 0 | state/latency-bound | 572 / 744 / 923 / 1118 | 1.31 / 1.62 / 1.96 | split |
| gdn.z | 505 (18) | 27.6 | 182.6 | 362 | instruction-bound | 504 / 1593 / 1597 / 1622 | 3.16 / 3.16 / 3.21 | split |
| hc.f.low | 392 (23) | 16.8 | 150.7 | 385 | bandwidth-bound | 383 / 702 / 769 / 853 | 1.79 / 1.97 / 2.18 | replicated |
| hc.f.gate | 379 (23) | 16.0 | 152.6 | 403 | bandwidth-bound | 379 / 700 / 708 / 712 | 1.85 / 1.87 / 1.88 | replicated |
| hc.a.low | 375 (23) | 16.1 | 150.7 | 402 | bandwidth-bound | 372 / 702 / 769 / 853 | 1.87 / 2.05 / 2.27 | replicated |
| hc.a.gate | 368 (23) | 16.0 | 152.6 | 415 | bandwidth-bound | 368 / 696 / 684 / 694 | 1.89 / 1.86 / 1.89 | replicated |
| qsa.qgate | 295 (5) | 62.0 | 89.5 | 304 | instruction-bound | 299 / 1054 / 1056 / 1065 | 3.58 / 3.58 / 3.61 | split |
| route | 279 (23) | 12.1 | 0.0 | 0 | state/latency-bound | 281 / 290 / 292 / 294 | 1.04 / 1.05 / 1.05 | replicated |
| shexpdown | 213 (23) | 9.3 | 40.0 | 188 | minimum-duration (tiny) | 214 / 771 / 771 / 795 | 3.61 / 3.61 / 3.73 | replicated |
| shexpgate | 177 (23) | 6.9 | 23.5 | 133 | minimum-duration (tiny) | 177 / 1051 / 1060 / 1074 | 5.92 / 5.97 / 6.05 | replicated |
| router | 176 (23) | 7.6 | 60.4 | 343 | minimum-duration (tiny) | 174 / 306 / 311 / 320 | 1.74 / 1.77 / 1.82 | replicated |
| shexpup | 171 (23) | 6.8 | 23.3 | 137 | minimum-duration (tiny) | 171 / 724 / 728 / 740 | 4.24 / 4.26 / 4.33 | replicated |
| hc.a.norm | 144 (46) | 3.1 | 0.0 | 0 | minimum-duration (tiny) | 144 / 140 / 147 / 147 | 0.97 / 1.02 / 1.02 | replicated |
| hc.f.norm | 141 (46) | 3.2 | 0.0 | 0 | minimum-duration (tiny) | 143 / 138 / 144 / 145 | 0.98 / 1.02 / 1.03 | replicated |
| qsa.attention | 118 (15) | 6.9 | 0.0 | 0 | minimum-duration (tiny) | 120 / 120 / 154 / 159 | 1.01 / 1.31 / 1.35 | split |
| attn.combine | 114 (23) | 4.9 | 0.0 | 0 | minimum-duration (tiny) | 120 / 136 / 139 / 149 | 1.20 / 1.22 / 1.30 | replicated |
| gdn.gated | 113 (18) | 6.2 | 0.0 | 0 | minimum-duration (tiny) | 112 / 115 / 117 / 119 | 1.02 / 1.04 / 1.06 | split |
| gdn.conv | 112 (18) | 6.2 | 0.0 | 0 | minimum-duration (tiny) | 113 / 140 / 166 / 195 | 1.25 / 1.49 / 1.74 | split |
| ffn.combine | 110 (23) | 4.8 | 0.0 | 0 | minimum-duration (tiny) | 113 / 125 / 130 / 133 | 1.14 / 1.18 / 1.21 | replicated |
| ple.key | 99 (1) | 99.4 | 52.4 | 528 | bandwidth-bound | 98 / 110 / 112 / 114 | 1.11 / 1.12 / 1.15 | replicated |
| gather | 95 (23) | 4.1 | 0.0 | 0 | minimum-duration (tiny) | 94 / 98 / 104 / 118 | 1.03 / 1.10 / 1.25 | replicated |
| qsa.select | 90 (10) | 8.9 | 0.0 | 0 | minimum-duration (tiny) | 90 / 90 / 92 / 92 | 1.00 / 1.02 / 1.02 | replicated |
| moe | 90 (46) | 2.0 | 0.0 | 0 | minimum-duration (tiny) | 92 / 176 / 259 / 337 | 1.96 / 2.88 / 3.75 | replicated |
| hc.f.act | 79 (23) | 3.4 | 0.0 | 0 | minimum-duration (tiny) | 80 / 80 / 80 / 80 | 1.01 / 1.01 / 1.01 | replicated |
| hc.a.mix | 78 (23) | 3.3 | 0.0 | 0 | minimum-duration (tiny) | 79 / 114 / 110 / 117 | 1.46 / 1.42 / 1.50 | replicated |
| hc.f.mix | 78 (23) | 3.3 | 0.0 | 0 | minimum-duration (tiny) | 79 / 114 / 111 / 117 | 1.47 / 1.43 / 1.51 | replicated |
| expsact | 73 (23) | 3.1 | 0.0 | 0 | minimum-duration (tiny) | 73 / 81 / 88 / 96 | 1.11 / 1.21 / 1.32 | split |
| gdn.a | 62 (18) | 3.4 | 8.8 | 142 | minimum-duration (tiny) | 56 / 84 / 87 / 87 | 1.36 / 1.40 / 1.40 | split |
| shexpact | 58 (23) | 2.5 | 0.0 | 0 | minimum-duration (tiny) | 58 / 71 / 73 / 75 | 1.23 / 1.26 / 1.30 | replicated |
| hc.a.act | 57 (23) | 2.4 | 0.0 | 0 | minimum-duration (tiny) | 58 / 64 / 62 / 62 | 1.11 / 1.08 / 1.08 | replicated |
| expsdown.check | 54 (23) | 2.3 | 0.0 | 0 | minimum-duration (tiny) | 55 / 60 / 63 / 78 | 1.11 / 1.16 / 1.44 | split |
| qsa.iq | 45 (5) | 9.0 | 16.4 | 366 | minimum-duration (tiny) | 39 / 65 / 66 / 69 | 1.45 / 1.48 / 1.54 | replicated |
| qsa.k | 44 (5) | 9.5 | 5.0 | 113 | minimum-duration (tiny) | 44 / 199 / 201 / 207 | 4.51 / 4.55 / 4.68 | split |
| qsa.v | 41 (5) | 9.1 | 5.0 | 122 | minimum-duration (tiny) | 41 / 166 / 168 / 171 | 4.04 / 4.07 / 4.16 | split |
| qsa.prepare | 31 (5) | 6.2 | 0.0 | 0 | minimum-duration (tiny) | 31 / 33 / 33 / 33 | 1.04 / 1.05 / 1.07 | replicated |
| ple.value | 25 (1) | 25.4 | 13.1 | 516 | bandwidth-bound | 25 / 33 / 33 / 32 | 1.29 / 1.28 / 1.25 | replicated |
| ple.gated | 18 (1) | 18.0 | 0.0 | 0 | state/latency-bound | 18 / 35 / 51 / 68 | 1.92 / 2.84 / 3.77 | replicated |
| qsa.pool | 16 (5) | 3.2 | 0.0 | 0 | minimum-duration (tiny) | 17 / 24 / 26 / 32 | 1.50 / 1.65 / 2.03 | replicated |

**Rank 1** (layers 23-47 + head): device us per decode half, summed over the rank's layers

| site | M=1 decode us (launches) | us/launch | weight MB | GB/s | class | prefill path M=1 / 2 / 3 / 4 us | t(M)/t_decode(1) M=2 / 3 / 4 | four cards |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| expsgate | 924 (25) | 35.9 | 158.2 | 171 | instruction-bound | 5109 / 4850 / 4470 / 4871 | 5.25 / 4.84 / 5.27 | split |
| expsdown | 913 (25) | 37.2 | 221.2 | 242 | instruction-bound | 1538 / 2451 / 3032 / 3631 | 2.68 / 3.32 / 3.98 | split |
| attention | 910 (25) | 36.2 | 417.8 | 459 | bandwidth-bound | 909 / 1369 / 1371 / 1380 | 1.50 / 1.51 / 1.52 | split |
| logits | 884 (1) | 884.4 | 521.5 | 590 | bandwidth-bound | 0 / 0 / 0 / 0 | 0.00 / 0.00 / 0.00 | split |
| expsup | 882 (25) | 34.6 | 158.2 | 179 | instruction-bound | 5078 / 4825 / 4450 / 4820 | 5.47 / 5.05 / 5.47 | split |
| gdn.qkv | 849 (18) | 47.0 | 340.8 | 402 | bandwidth-bound | 854 / 2285 / 2286 / 2314 | 2.69 / 2.69 / 2.73 | split |
| gdn.recurrence | 528 (36) | 14.6 | 0.0 | 0 | state/latency-bound | 529 / 714 / 892 / 1088 | 1.35 / 1.69 / 2.06 | split |
| gdn.z | 493 (18) | 27.7 | 196.6 | 398 | bandwidth-bound | 490 / 1403 / 1404 / 1425 | 2.84 / 2.85 / 2.89 | split |
| hc.f.low | 440 (25) | 17.4 | 163.8 | 372 | instruction-bound | 430 / 770 / 844 / 939 | 1.75 / 1.92 / 2.14 | replicated |
| hc.f.gate | 407 (25) | 15.8 | 165.9 | 407 | bandwidth-bound | 406 / 748 / 748 / 759 | 1.84 / 1.84 / 1.86 | replicated |
| hc.a.low | 405 (25) | 16.0 | 163.8 | 404 | bandwidth-bound | 401 / 762 / 835 / 923 | 1.88 / 2.06 / 2.28 | replicated |
| hc.a.gate | 399 (25) | 16.0 | 165.9 | 415 | bandwidth-bound | 396 / 735 / 734 / 741 | 1.84 / 1.84 / 1.86 | replicated |
| qsa.qgate | 380 (7) | 53.1 | 172.3 | 454 | bandwidth-bound | 379 / 830 / 831 / 841 | 2.19 / 2.19 / 2.22 | split |
| route | 302 (25) | 12.0 | 0.0 | 0 | state/latency-bound | 305 / 315 / 316 / 317 | 1.04 / 1.05 / 1.05 | replicated |
| shexpdown | 231 (25) | 9.3 | 43.5 | 188 | minimum-duration (tiny) | 232 / 835 / 845 / 845 | 3.61 / 3.65 / 3.65 | replicated |
| shexpgate | 195 (25) | 7.1 | 26.3 | 135 | minimum-duration (tiny) | 194 / 1139 / 1148 / 1164 | 5.84 / 5.89 / 5.97 | replicated |
| shexpup | 194 (25) | 7.0 | 27.4 | 141 | minimum-duration (tiny) | 193 / 846 / 847 / 863 | 4.36 / 4.37 / 4.45 | replicated |
| router | 191 (25) | 7.6 | 65.7 | 344 | minimum-duration (tiny) | 188 / 333 / 340 / 350 | 1.74 / 1.78 / 1.83 | replicated |
| qsa.attention | 162 (21) | 7.0 | 0.0 | 0 | minimum-duration (tiny) | 165 / 167 / 213 / 222 | 1.03 / 1.32 / 1.37 | split |
| hc.a.norm | 157 (50) | 3.4 | 0.0 | 0 | minimum-duration (tiny) | 153 / 145 / 152 / 155 | 0.92 / 0.97 / 0.98 | replicated |
| hc.f.norm | 154 (50) | 3.3 | 0.0 | 0 | minimum-duration (tiny) | 150 / 146 / 150 / 151 | 0.95 / 0.97 / 0.98 | replicated |
| attn.combine | 127 (25) | 5.0 | 0.0 | 0 | minimum-duration (tiny) | 125 / 142 / 146 / 162 | 1.12 / 1.16 / 1.28 | replicated |
| qsa.select | 127 (14) | 8.9 | 0.0 | 0 | minimum-duration (tiny) | 126 / 126 / 128 / 129 | 0.99 / 1.01 / 1.02 | replicated |
| ffn.combine | 121 (25) | 4.8 | 0.0 | 0 | minimum-duration (tiny) | 120 / 133 / 139 / 143 | 1.11 / 1.15 / 1.18 | replicated |
| gdn.gated | 111 (18) | 6.1 | 0.0 | 0 | minimum-duration (tiny) | 110 / 111 / 114 / 118 | 1.00 / 1.03 / 1.06 | split |
| gdn.conv | 103 (18) | 5.7 | 0.0 | 0 | minimum-duration (tiny) | 104 / 133 / 160 / 189 | 1.29 / 1.55 / 1.83 | split |
| argmax | 102 (1) | 102.0 | 0.0 | 0 | state/latency-bound | 0 / 0 / 0 / 0 | 0.00 / 0.00 / 0.00 | split |
| moe | 99 (50) | 2.0 | 0.0 | 0 | minimum-duration (tiny) | 109 / 202 / 289 / 376 | 2.03 / 2.91 / 3.78 | replicated |
| gather | 99 (25) | 4.0 | 0.0 | 0 | minimum-duration (tiny) | 99 / 103 / 107 / 114 | 1.04 / 1.07 / 1.14 | replicated |
| hc.f.act | 86 (25) | 3.4 | 0.0 | 0 | minimum-duration (tiny) | 86 / 87 / 88 / 88 | 1.00 / 1.02 / 1.02 | replicated |
| hc.a.mix | 84 (25) | 3.3 | 0.0 | 0 | minimum-duration (tiny) | 84 / 119 / 116 / 121 | 1.41 / 1.38 / 1.44 | replicated |
| hc.f.mix | 84 (25) | 3.3 | 0.0 | 0 | minimum-duration (tiny) | 83 / 119 / 116 / 121 | 1.41 / 1.38 / 1.44 | replicated |
| expsact | 80 (25) | 3.2 | 0.0 | 0 | minimum-duration (tiny) | 81 / 91 / 96 / 102 | 1.14 / 1.20 / 1.28 | split |
| qsa.k | 66 (7) | 9.4 | 7.5 | 114 | minimum-duration (tiny) | 66 / 304 / 306 / 313 | 4.59 / 4.61 / 4.73 | split |
| qsa.v | 64 (7) | 9.2 | 7.5 | 117 | minimum-duration (tiny) | 64 / 299 / 301 / 310 | 4.67 / 4.70 / 4.83 | split |
| shexpact | 64 (25) | 2.5 | 0.0 | 0 | minimum-duration (tiny) | 64 / 77 / 80 / 82 | 1.21 / 1.25 / 1.29 | replicated |
| hc.a.act | 61 (25) | 2.4 | 0.0 | 0 | minimum-duration (tiny) | 64 / 68 / 68 / 67 | 1.12 / 1.11 / 1.10 | replicated |
| gdn.a | 61 (18) | 3.3 | 8.8 | 145 | minimum-duration (tiny) | 53 / 83 / 84 / 84 | 1.36 / 1.38 / 1.39 | split |
| qsa.iq | 61 (7) | 8.5 | 22.9 | 379 | minimum-duration (tiny) | 52 / 90 / 92 / 96 | 1.49 / 1.52 / 1.58 | replicated |
| expsdown.check | 59 (25) | 2.3 | 0.0 | 0 | minimum-duration (tiny) | 64 / 71 / 77 / 95 | 1.21 / 1.30 / 1.61 | split |
| qsa.prepare | 46 (7) | 6.6 | 0.0 | 0 | minimum-duration (tiny) | 46 / 48 / 48 / 49 | 1.04 / 1.05 / 1.08 | replicated |
| qsa.pool | 23 (7) | 3.3 | 0.0 | 0 | minimum-duration (tiny) | 23 / 32 / 37 / 46 | 1.41 / 1.63 / 2.00 | replicated |
| final.low | 18 (1) | 17.8 | 6.6 | 369 | instruction-bound | 0 / 0 / 0 / 0 | 0.00 / 0.00 / 0.00 | replicated |
| final.gate | 16 (1) | 16.4 | 6.6 | 401 | bandwidth-bound | 0 / 0 / 0 / 0 | 0.00 / 0.00 / 0.00 | replicated |


### The best existing exact kernel per site at M = 2, 3, 4

The default batched path is 2.7–3.0× a one-row pass because its tiles are sized for 32–256-row chunks (the 1x32 tile
costs 6–8× at M = 2) and its expert kernels spend 160–190 µs per layer bucketing slots over all 512 experts in one
work-group. Choosing the best compiled configuration per site, with no new kernel, gives the table below (for sites
that use neither tile family the "tile" is irrelevant and the value is the minimum of six noisy medians, slightly
optimistic). BF16 and Q8_0 projections are already nearly weight-stationary at M = 2–4 (1.02–1.30×); the Q6_K, Q4_K and
IQ4_XS projections stay at 1.5–2.0×, the shared expert at 2.2–2.75×, and the routed experts at 1.7–4.7× (at M ≤ 3 the
best is the existing per-slot kernel, i.e. one decode per slot: no weight reuse at all).

**Rank 0**: best existing exact kernel per site (us per pass, all layers) and its ratio to the one-row decode time

| site | M=1 decode | M=2 best (tile) | M=3 best (tile) | M=4 best (tile) | ratio M=2 / 3 / 4 |
| --- | ---: | --- | --- | --- | ---: |
| attention | 860 | 897 (1x1 (GRF128)) | 1065 (1x1 (GRF128)) | 1121 (1x4 (GRF128)) | 1.04 / 1.24 / 1.30 |
| gdn.qkv | 817 | 1239 (1x4 (GRF128)) | 1251 (1x4 (GRF128)) | 1286 (1x4 (GRF128)) | 1.52 / 1.53 / 1.57 |
| expsgate | 812 | 1656 (existing per-slot kernel) | 2332 (existing per-slot kernel) | 2941 (existing per-slot kernel) | 2.04 / 2.87 / 3.62 |
| expsdown | 797 | 1385 (existing per-slot kernel) | 1993 (existing per-slot kernel) | 3723 (1x4) | 1.74 / 2.50 / 4.67 |
| expsup | 769 | 1611 (existing per-slot kernel) | 2301 (existing per-slot kernel) | 2966 (existing per-slot kernel) | 2.09 / 2.99 / 3.86 |
| gdn.recurrence | 569 | 744 (1x1 (GRF128)) | 920 (1x32) | 1099 (2x16 tile-major) | 1.31 / 1.62 / 1.93 |
| gdn.z | 505 | 960 (1x4 (GRF128)) | 966 (1x4 (GRF128)) | 970 (1x4 (GRF128)) | 1.90 / 1.91 / 1.92 |
| hc.f.low | 392 | 406 (1x1 (GRF128)) | 424 (1x1 (GRF128)) | 472 (1x1 (GRF128)) | 1.04 / 1.08 / 1.20 |
| hc.f.gate | 379 | 417 (1x4 (GRF128)) | 429 (1x4 (GRF128)) | 420 (1x4 (GRF128)) | 1.10 / 1.13 / 1.11 |
| hc.a.low | 375 | 384 (1x1 (GRF128)) | 398 (1x1 (GRF128)) | 449 (1x1 (GRF128)) | 1.02 / 1.06 / 1.20 |
| hc.a.gate | 368 | 441 (1x4 (GRF128)) | 403 (1x4 (GRF128)) | 424 (1x4 (GRF128)) | 1.20 / 1.10 / 1.15 |
| qsa.qgate | 295 | 595 (1x4 (GRF128)) | 595 (1x4 (GRF128)) | 596 (1x4 (GRF128)) | 2.02 / 2.02 / 2.02 |
| route | 279 | 286 (1x1 (GRF128)) | 287 (1x1 (GRF128)) | 286 (1x1 (GRF128)) | 1.02 / 1.03 / 1.03 |
| shexpdown | 213 | 464 (1x4 (GRF128)) | 464 (1x4 (GRF128)) | 467 (1x4 (GRF128)) | 2.18 / 2.18 / 2.19 |
| shexpgate | 177 | 424 (1x4 (GRF128)) | 458 (1x4 (GRF128)) | 489 (1x4 (GRF128)) | 2.39 / 2.58 / 2.75 |
| router | 176 | 172 (1x1 (GRF128)) | 180 (1x1 (GRF128)) | 183 (1x4 (GRF128)) | 0.98 / 1.02 / 1.04 |
| shexpup | 171 | 367 (1x4 (GRF128)) | 369 (1x4 (GRF128)) | 377 (1x4 (GRF128)) | 2.15 / 2.16 / 2.21 |
| hc.a.norm | 144 | 139 (1x32) | 146 (1x1 (GRF128)) | 144 (1x32) | 0.96 / 1.01 / 1.00 |
| hc.f.norm | 141 | 138 (1x32) | 144 (1x1 (GRF128)) | 144 (4x8) | 0.98 / 1.02 / 1.02 |
| qsa.attention | 118 | 116 (1x32) | 150 (1x32) | 155 (2x16 tile-major) | 0.98 / 1.28 / 1.31 |
| attn.combine | 114 | 123 (1x1 (GRF128)) | 127 (1x1 (GRF128)) | 129 (1x1 (GRF128)) | 1.08 / 1.12 / 1.13 |
| gdn.gated | 113 | 114 (1x1 (GRF128)) | 116 (1x1 (GRF128)) | 118 (1x1 (GRF128)) | 1.02 / 1.03 / 1.05 |
| gdn.conv | 112 | 136 (1x1 (GRF128)) | 162 (1x1 (GRF128)) | 188 (1x1 (GRF128)) | 1.21 / 1.45 / 1.68 |
| ffn.combine | 110 | 122 (1x4 (GRF128)) | 125 (4x8) | 126 (2x16 tile-major) | 1.11 / 1.14 / 1.15 |
| ple.key | 99 | 101 (1x4 (GRF128)) | 102 (1x4 (GRF128)) | 103 (1x4 (GRF128)) | 1.02 / 1.03 / 1.04 |
| gather | 95 | 98 (4x8) | 102 (4x8) | 111 (1x1 (GRF128)) | 1.03 / 1.08 / 1.18 |
| qsa.select | 90 | 90 (1x1 (GRF128)) | 91 (1x32) | 90 (1x1 (GRF128)) | 1.00 / 1.01 / 1.00 |
| moe | 90 | 176 (1x1 (GRF128)) | 256 (1x4 (GRF128)) | 335 (1x4 (GRF128)) | 1.96 / 2.85 / 3.72 |
| hc.f.act | 79 | 82 (existing kernel) | 84 (1x1 (GRF128)) | 80 (1x1 (GRF128)) | 1.03 / 1.06 / 1.01 |
| hc.a.mix | 78 | 84 (1x1 (GRF128)) | 92 (1x1 (GRF128)) | 100 (1x1 (GRF128)) | 1.08 / 1.18 / 1.29 |
| hc.f.mix | 78 | 85 (1x1 (GRF128)) | 93 (1x1 (GRF128)) | 102 (1x4 (GRF128)) | 1.09 / 1.20 / 1.31 |
| expsact | 73 | 80 (4x8) | 87 (4x8) | 91 (4x8) | 1.10 / 1.20 / 1.25 |
| gdn.a | 62 | 81 (1x1 (GRF128)) | 81 (1x1 (GRF128)) | 81 (1x1 (GRF128)) | 1.30 / 1.30 / 1.30 |
| shexpact | 58 | 60 (existing kernel) | 64 (existing kernel) | 67 (1x1 (GRF128)) | 1.04 / 1.11 / 1.15 |
| hc.a.act | 57 | 59 (1x1 (GRF128)) | 60 (1x1 (GRF128)) | 61 (1x1 (GRF128)) | 1.03 / 1.05 / 1.06 |
| expsdown.check | 54 | 57 (4x8) | 60 (4x8) | 73 (2x16 tile-major) | 1.06 / 1.10 / 1.35 |
| qsa.iq | 45 | 37 (1x1 (GRF128)) | 38 (1x1 (GRF128)) | 38 (1x4 (GRF128)) | 0.82 / 0.85 / 0.85 |
| qsa.k | 44 | 112 (1x4 (GRF128)) | 115 (1x4 (GRF128)) | 113 (1x4 (GRF128)) | 2.52 / 2.61 / 2.56 |
| qsa.v | 41 | 90 (1x4 (GRF128)) | 92 (1x4 (GRF128)) | 92 (1x4 (GRF128)) | 2.20 / 2.24 / 2.24 |

Sum of per-site best: M=2 15.50 ms, M=3 18.16 ms, M=4 21.81 ms of device busy time per pass.

**Rank 1**: best existing exact kernel per site (us per pass, all layers) and its ratio to the one-row decode time

| site | M=1 decode | M=2 best (tile) | M=3 best (tile) | M=4 best (tile) | ratio M=2 / 3 / 4 |
| --- | ---: | --- | --- | --- | ---: |
| expsgate | 924 | 1899 (existing per-slot kernel) | 2688 (existing per-slot kernel) | 3535 (1x4) | 2.05 / 2.91 / 3.83 |
| expsdown | 913 | 1619 (existing per-slot kernel) | 2302 (existing per-slot kernel) | 3895 (1x4) | 1.77 / 2.52 / 4.27 |
| attention | 910 | 959 (1x1 (GRF128)) | 1157 (1x1 (GRF128)) | 1215 (1x4 (GRF128)) | 1.05 / 1.27 / 1.34 |
| expsup | 882 | 1859 (existing per-slot kernel) | 2679 (existing per-slot kernel) | 3513 (1x4) | 2.11 / 3.04 / 3.98 |
| gdn.qkv | 849 | 1352 (1x4 (GRF128)) | 1362 (1x4 (GRF128)) | 1379 (1x4 (GRF128)) | 1.59 / 1.60 / 1.63 |
| gdn.recurrence | 528 | 719 (4x8) | 898 (1x32) | 1072 (1x1 (GRF128)) | 1.36 / 1.70 / 2.03 |
| gdn.z | 493 | 841 (1x4 (GRF128)) | 847 (1x4 (GRF128)) | 844 (1x4 (GRF128)) | 1.70 / 1.72 / 1.71 |
| hc.f.low | 440 | 454 (1x1 (GRF128)) | 468 (1x1 (GRF128)) | 520 (1x1 (GRF128)) | 1.03 / 1.06 / 1.18 |
| hc.f.gate | 407 | 466 (1x4 (GRF128)) | 445 (1x4 (GRF128)) | 454 (1x4 (GRF128)) | 1.14 / 1.09 / 1.11 |
| hc.a.low | 405 | 418 (1x1 (GRF128)) | 434 (1x1 (GRF128)) | 490 (1x1 (GRF128)) | 1.03 / 1.07 / 1.21 |
| hc.a.gate | 399 | 458 (1x4 (GRF128)) | 433 (1x4 (GRF128)) | 444 (1x4 (GRF128)) | 1.15 / 1.08 / 1.11 |
| qsa.qgate | 380 | 566 (1x4 (GRF128)) | 568 (1x4 (GRF128)) | 580 (1x4 (GRF128)) | 1.49 / 1.50 / 1.53 |
| route | 302 | 309 (1x1 (GRF128)) | 313 (1x1 (GRF128)) | 308 (1x1 (GRF128)) | 1.02 / 1.04 / 1.02 |
| shexpdown | 231 | 512 (1x4 (GRF128)) | 507 (1x4 (GRF128)) | 509 (1x4 (GRF128)) | 2.21 / 2.19 / 2.20 |
| shexpgate | 195 | 468 (1x4 (GRF128)) | 491 (1x4 (GRF128)) | 535 (1x4 (GRF128)) | 2.40 / 2.52 / 2.75 |
| shexpup | 194 | 439 (1x4 (GRF128)) | 436 (1x4 (GRF128)) | 442 (1x4 (GRF128)) | 2.26 / 2.25 / 2.28 |
| router | 191 | 185 (1x1 (GRF128)) | 194 (1x1 (GRF128)) | 197 (1x4 (GRF128)) | 0.97 / 1.02 / 1.03 |
| qsa.attention | 162 | 167 (1x32) | 214 (4x8) | 223 (2x16 tile-major) | 1.03 / 1.32 / 1.38 |
| hc.a.norm | 157 | 144 (1x32) | 152 (1x32) | 150 (1x1 (GRF128)) | 0.92 / 0.96 / 0.95 |
| hc.f.norm | 154 | 147 (4x8) | 151 (4x8) | 152 (2x16 tile-major) | 0.95 / 0.98 / 0.99 |
| attn.combine | 127 | 135 (1x1 (GRF128)) | 139 (1x1 (GRF128)) | 142 (1x1 (GRF128)) | 1.07 / 1.10 / 1.12 |
| qsa.select | 127 | 126 (1x1 (GRF128)) | 128 (4x8) | 127 (1x1 (GRF128)) | 1.00 / 1.01 / 1.00 |
| ffn.combine | 121 | 133 (4x8) | 141 (4x8) | 141 (1x1 (GRF128)) | 1.11 / 1.17 / 1.17 |
| gdn.gated | 111 | 114 (1x1 (GRF128)) | 116 (1x1 (GRF128)) | 116 (1x1 (GRF128)) | 1.02 / 1.05 / 1.05 |
| gdn.conv | 103 | 132 (1x1 (GRF128)) | 160 (1x1 (GRF128)) | 185 (1x1 (GRF128)) | 1.28 / 1.55 / 1.79 |
| moe | 99 | 204 (1x1 (GRF128)) | 289 (1x4 (GRF128)) | 373 (1x1 (GRF128)) | 2.05 / 2.91 / 3.76 |
| gather | 99 | 104 (4x8) | 107 (1x32) | 112 (4x8) | 1.04 / 1.08 / 1.13 |
| hc.f.act | 86 | 85 (1x1 (GRF128)) | 88 (1x1 (GRF128)) | 85 (1x1 (GRF128)) | 0.98 / 1.01 / 0.99 |
| hc.a.mix | 84 | 92 (1x1 (GRF128)) | 98 (1x1 (GRF128)) | 105 (1x1 (GRF128)) | 1.09 / 1.16 / 1.25 |
| hc.f.mix | 84 | 90 (1x1 (GRF128)) | 98 (1x1 (GRF128)) | 105 (1x1 (GRF128)) | 1.07 / 1.17 / 1.25 |
| expsact | 80 | 91 (existing kernel) | 96 (4x8) | 100 (4x8) | 1.14 / 1.20 / 1.25 |
| qsa.k | 66 | 173 (existing kernel) | 173 (1x4 (GRF128)) | 173 (1x4 (GRF128)) | 2.61 / 2.61 / 2.61 |
| qsa.v | 64 | 149 (existing kernel) | 194 (existing kernel) | 202 (1x4 (GRF128)) | 2.33 / 3.03 / 3.15 |
| shexpact | 64 | 67 (existing kernel) | 73 (1x1 (GRF128)) | 72 (1x1 (GRF128)) | 1.05 / 1.14 / 1.14 |
| hc.a.act | 61 | 64 (1x1 (GRF128)) | 64 (1x1 (GRF128)) | 64 (1x1 (GRF128)) | 1.04 / 1.04 / 1.05 |
| gdn.a | 61 | 77 (1x1 (GRF128)) | 78 (1x1 (GRF128)) | 77 (1x1 (GRF128)) | 1.27 / 1.28 / 1.27 |
| qsa.iq | 61 | 51 (1x1 (GRF128)) | 54 (1x1 (GRF128)) | 54 (1x4 (GRF128)) | 0.84 / 0.89 / 0.89 |
| expsdown.check | 59 | 68 (existing kernel) | 73 (1x4 (GRF128)) | 90 (1x4 (GRF128)) | 1.15 / 1.23 / 1.52 |
| qsa.prepare | 46 | 47 (1x1 (GRF128)) | 48 (1x4 (GRF128)) | 48 (1x1 (GRF128)) | 1.02 / 1.04 / 1.05 |

Sum of per-site best: M=2 16.73 ms, M=3 19.72 ms, M=4 23.61 ms of device busy time per pass.


Where the remaining gap to an ideal multi-row kernel set sits (best existing minus ideal; ideal = one-row time for
dense and glue sites, distinct-expert scaling for experts, measured native ratio for recurrence/attention):

| | rank 0, M = 2 | rank 0, M = 4 | rank 1, M = 2 | rank 1, M = 4 |
| --- | ---: | ---: | ---: | ---: |
| dense weight sites (Q6_K/Q4_K/IQ4_XS projections, shared expert) | 2.17 ms | 2.67 ms | 2.22 ms | 2.77 ms |
| routed experts | 0.70 ms | 2.94 ms | 1.07 ms | 4.07 ms |
| glue and per-row replays | 0.85 ms | 1.22 ms | 0.87 ms | 1.15 ms |
| recurrence, conv, QSA (already native multi-row) | 0 | 0 | 0 | 0 |

## Experts

- **Decode kernels are instruction-bound, confirmed:** 155–250 GB/s (26–42% of the measured 590 GB/s), about 3.5 µs per
  expert-row slot per site, 105 µs per layer for gate+up+down. By format: IQ3_XXS gate/up 155–165 GB/s, IQ2_S 165–173,
  IQ3_S 197–204, IQ4_XS 171–175, IQ4_NL down 226–248. Experts are 2.38 ms (24%) of rank 0's half and 2.72 ms (23%) of
  rank 1's.
- **Distinct experts on real consecutive tokens** (route dumps, 25 or 23 layers × every window chunk):

| rows M | slots | rank 0 distinct (min–max) | rank 1 distinct (min–max) | shared slots |
| ---: | ---: | --- | --- | ---: |
| 1 | 10 | 10 | 10 | 0 |
| 2 | 20 | 16.6 (10–20) | 15.8 (10–20) | 17–21% |
| 3 | 30 | 22.9 (12–30) | 21.1 (11–30) | 24–30% |
| 4 | 40 | 28.1 (13–40) | 25.3 (13–39) | 30–37% |

  Two consecutive tokens share about 3.4–4.2 of their 10 experts. So even a perfect weight-stationary kernel pays
  1.6× / 2.1–2.3× / 2.5–2.8× the one-row expert cost at M = 2 / 3 / 4.
- **Same expert, extra row vs extra expert** (per chunk and layer, expert-grouped kernel time against that chunk's
  distinct experts, [census.json](results/census.json) `experts`): within each M, every additional distinct expert adds
  13–20 µs per layer (gate+up+down), on top of a fixed 160–190 µs per layer; at a fixed number of distinct experts,
  extra rows add nothing measurable (the joint fit's row coefficient is negative, −41 / −52 µs). For comparison the
  decode kernel pays about 10.5 µs per expert-row slot. The cost of a verify row in the experts is the new experts it
  brings, not the row.

## Glue census (idea #3)

| | rank 0 half | rank 1 half | draft step |
| --- | ---: | ---: | ---: |
| all kernels | 863 launches, 10.00 ms | 938 launches, 11.79 ms | 50, 1.20 ms |
| kernels under 20 µs | 728 launches, 5.02 ms (50%) | 792 launches, 5.44 ms (46%) | 37, 0.29 ms |
| of which weightless (norms, act, mix, combine, moe, gather, checks, route, conv, gated, recurrence, QSA small ops) | 511, 2.58 ms | 552, 2.70 ms | |
| of which small weight GEMVs (hc.* BF16 at 16 µs, shared expert, router, QSA k/v/indexer, gdn.a) | 217, 2.44 ms | 240, 2.73 ms | |
| under 20 µs and replicated on both cards in the four-card layout | 567, 3.83 ms | 617, 4.20 ms | card 0 only |
| all replicated work in the four-card layout (any size) | 569 launches, 3.96 ms (40%) | 618 launches, 4.21 ms (36%) | |
| work split across the two cards | 6.04 ms | 7.57 ms | |

The "~37% replicated glue" figure is confirmed (40% / 36%). The replicated set is every hc.* site, both combines, the
router and route/gather, the shared expert, `moe`, the QSA indexer and select, PLE and the final hc of the head; the
split set is the GDN sites, attention output, QSA q/k/v/attention, routed experts, logits and argmax. With TP2 the
ideal split stage would be 6.98 ms (rank 0) / 8.00 ms (rank 1); the record's 10.82 ms hit cycle therefore carries
about 1.96 ms per stage of exchange, wait and snapshot cost (calibrated below). Fusing the minimum-duration class into a
few kernels per layer is worth at most 2.6 / 2.9 ms per half before the fused kernels' own time; the projections use
"glue halved" (1.3–1.5 ms per half).

## Projection (CPU arithmetic, not a measurement)

Inputs: the per-site device times above, the unprofiled host overheads, the measured distinct-expert counts, and
acceptance from lab records. a1 = 0.761 (12-prompt suite, [miss-stall analysis](../tp/miss-stall-2026-10-29/ANALYSIS.md));
conditional a2 = 0.718 given an accepted first guess (packet66 depth-2 probe as used by
[packet71c](../../stage2/packet71c-depth2-engine/DESIGN.md); older UD-IQ3_XXS lane, a1 = 0.787 there); **no record of
a third-position acceptance exists**, so a3 = a2 is assumed and the sweep below shows the dependence; top-2 at the
first position rescues 28 of 58 misses ([packet96](../../stage2/packet96-dual-guess-model/DECISION.md), packet31 CPU
reference), giving 0.876.

Model: a verify block of M rows (the confirmed token plus the guesses) runs through rank 0, then rank 1 (+ head);
d draft steps (1.32 ms each, on rank 0) propose the next block. Three cycle assumptions bracket any design:
**serial** = rank 0 + rank 1 + drafts (no stage overlap); **with redo** = stages overlap like today's pipeline, rank 0
working on the next block on the guessed continuation, which survives only if every guess is accepted and the next
block's first guess matches (one more acceptance factor), otherwise rank 0 redoes it with its drafts; **upper bound** =
perfect overlap, rejections free. Today's one-guess pipeline under the same inputs: 66.9 tok/s, against 66.42
measured on two cards. Four cards (PP2 × TP2): split sites halve, replicated sites do not, plus the calibrated
1.96 ms per stage. "Ideal multi-row" (#1): dense and glue sites at their one-row time, experts × distinct/10,
recurrence/conv/QSA at their measured native ratio, the head once plus one argmax per extra row. "#4 experts 2× / at
roofline": expert time halved / ×0.3. Every row is in [census.json](results/census.json) `projection`.

**two cards (PP2)**: tok/s as serial verify / pipelined with rank-0 redo on any reject / upper bound (perfect overlap, no miss cost)

| kernels and levers | one guess (chain depth 1) (M=2) | chain depth 2 (M=3) | chain depth 3 (M=4) | top-2 tree at the first position (M=3) | top-2 tree + depth 2 on the top-1 branch (M=4) |
| --- | ---: | ---: | ---: | ---: | ---: |
| today kernels (M serial one-row passes) | 37 / 51 / 72 | 32 / 40 / 63 | 28 / 33 / 55 | 27 / 38 / 51 | 26 / 32 / 49 |
| existing exact multi-row kernels, best tile per site | 48 / 65 / 91 | 52 / 64 / 99 | 49 / 57 / 96 | 43 / 61 / 80 | 45 / 56 / 86 |
| #1 ideal multi-row kernels | 63 / 86 / 124 | 71 / 86 / 138 | 73 / 80 / 138 | 60 / 86 / 117 | 68 / 83 / 133 |
| #1 + #3 glue halved | 70 / 96 / 138 | 77 / 93 / 150 | 79 / 87 / 149 | 66 / 95 / 130 | 74 / 90 / 144 |
| #1 + #3 + #4 experts 2x faster | 84 / 115 / 167 | 95 / 114 / 183 | 99 / 106 / 182 | 82 / 119 / 162 | 93 / 112 / 180 |
| #1 + #3 + #4 experts at roofline (3.3x) | 91 / 125 / 182 | 105 / 124 / 200 | 110 / 117 / 201 | 91 / 132 / 179 | 104 / 124 / 200 |

**four cards (PP2 x TP2)**: tok/s as serial verify / pipelined with rank-0 redo on any reject / upper bound (perfect overlap, no miss cost)

| kernels and levers | one guess (chain depth 1) (M=2) | chain depth 2 (M=3) | chain depth 3 (M=4) | top-2 tree at the first position (M=3) | top-2 tree + depth 2 on the top-1 branch (M=4) |
| --- | ---: | ---: | ---: | ---: | ---: |
| today kernels (M serial one-row passes) | 43 / 58 / 84 | 37 / 46 / 73 | 32 / 37 / 64 | 31 / 44 / 60 | 29 / 36 / 58 |
| existing exact multi-row kernels, best tile per site | 60 / 82 / 119 | 68 / 84 / 134 | 67 / 77 / 132 | 57 / 82 / 111 | 63 / 78 / 124 |
| #1 ideal multi-row kernels | 76 / 103 / 150 | 88 / 103 / 166 | 93 / 98 / 169 | 75 / 109 / 149 | 87 / 103 / 165 |
| #1 + #3 glue halved | 85 / 115 / 167 | 97 / 113 / 181 | 102 / 106 / 183 | 84 / 120 / 165 | 96 / 112 / 180 |
| #1 + #3 + #4 experts 2x faster | 95 / 127 / 184 | 110 / 126 / 203 | 117 / 120 / 206 | 96 / 136 / 187 | 111 / 128 / 206 |
| #1 + #3 + #4 experts at roofline (3.3x) | 99 / 132 / 192 | 116 / 133 / 213 | 124 / 126 / 217 | 102 / 144 / 198 | 119 / 136 / 218 |

**four cards as one stage (TP4, idea #5)**: serial tok/s (no pipeline, so no miss cost), exchanges at 2x the calibrated TP2 cost / free

| kernels and levers | no speculation (target only) | one guess (chain depth 1) | chain depth 2 | chain depth 3 | top-2 tree at the first position | top-2 tree + depth 2 on the top-1 branch |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| today kernels (M serial one-row passes) | 62 / 82 | 52 / 68 | 45 / 59 | 39 / 51 | 38 / 49 | 36 / 47 |
| #1 ideal multi-row kernels | 62 / 82 | 95 / 121 | 112 / 138 | 119 / 143 | 97 / 122 | 113 / 139 |
| #1 + #3 glue halved | 72 / 100 | 109 / 144 | 126 / 160 | 132 / 164 | 110 / 143 | 127 / 160 |
| #1 + #3 + #4 experts 2x faster | 75 / 107 | 117 / 157 | 136 / 177 | 144 / 183 | 120 / 161 | 139 / 180 |
| #1 + #3 + #4 experts at roofline (3.3x) | 77 / 110 | 120 / 163 | 141 / 185 | 150 / 191 | 125 / 169 | 145 / 190 |

**Acceptance sweep** (every chain position accepted with probability a; #1 + #3 + #4 2x; serial / with-redo / upper bound)

| layout | depth | a = 0.7 | a = 0.761 | a = 0.8 | a = 0.85 | a = 0.9 | a = 0.95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| two cards (PP2) | 1 | 81 / 107 / 161 | 84 / 118 / 167 | 86 / 126 / 170 | 88 / 138 / 175 | 91 / 152 / 180 | 93 / 169 / 185 |
| two cards (PP2) | 2 | 90 / 105 / 173 | 97 / 119 / 185 | 101 / 130 / 193 | 106 / 147 / 204 | 112 / 169 / 215 | 118 / 198 / 226 |
| two cards (PP2) | 3 | 93 / 97 / 171 | 102 / 113 / 188 | 108 / 125 / 200 | 117 / 146 / 215 | 126 / 173 / 232 | 136 / 212 / 251 |
| four cards (PP2 x TP2) | 1 | 91 / 118 / 178 | 95 / 130 / 184 | 97 / 139 / 188 | 99 / 152 / 194 | 102 / 167 / 199 | 105 / 186 / 204 |
| four cards (PP2 x TP2) | 2 | 105 / 116 / 193 | 112 / 132 / 206 | 117 / 144 / 215 | 123 / 163 / 226 | 129 / 188 / 239 | 136 / 220 / 251 |
| four cards (PP2 x TP2) | 3 | 110 / 110 / 193 | 120 / 127 / 212 | 128 / 142 / 225 | 138 / 165 / 243 | 149 / 195 / 262 | 160 / 239 / 283 |

**Which stacks reach a target** (best speculation scenario per stack; upper bound / with-redo estimate / serial)

| layout | kernels and levers | best upper bound | best with-redo | best serial | reaches 120 / 150 / 200 (redo estimate) | reaches 200 (upper bound) |
| --- | --- | ---: | ---: | ---: | --- | --- |
| two cards (PP2) | today kernels (M serial one-row passes) | 72 (one guess (chain depth 1)) | 51 (one guess (chain depth 1)) | 37 | no / no / no | no |
| two cards (PP2) | existing exact multi-row kernels, best tile per site | 99 (chain depth 2) | 65 (one guess (chain depth 1)) | 52 | no / no / no | no |
| two cards (PP2) | #1 ideal multi-row kernels | 138 (chain depth 3) | 86 (top-2 tree at the first position) | 73 | no / no / no | no |
| two cards (PP2) | #1 + #3 glue halved | 150 (chain depth 2) | 96 (one guess (chain depth 1)) | 79 | no / no / no | no |
| two cards (PP2) | #1 + #3 + #4 experts 2x faster | 183 (chain depth 2) | 119 (top-2 tree at the first position) | 99 | no / no / no | no |
| two cards (PP2) | #1 + #3 + #4 experts at roofline (3.3x) | 201 (chain depth 3) | 132 (top-2 tree at the first position) | 110 | yes / no / no | yes |
| four cards (PP2 x TP2) | today kernels (M serial one-row passes) | 84 (one guess (chain depth 1)) | 58 (one guess (chain depth 1)) | 43 | no / no / no | no |
| four cards (PP2 x TP2) | existing exact multi-row kernels, best tile per site | 134 (chain depth 2) | 84 (chain depth 2) | 68 | no / no / no | no |
| four cards (PP2 x TP2) | #1 ideal multi-row kernels | 169 (chain depth 3) | 109 (top-2 tree at the first position) | 93 | no / no / no | no |
| four cards (PP2 x TP2) | #1 + #3 glue halved | 183 (chain depth 3) | 120 (top-2 tree at the first position) | 102 | yes / no / no | no |
| four cards (PP2 x TP2) | #1 + #3 + #4 experts 2x faster | 206 (chain depth 3) | 136 (top-2 tree at the first position) | 117 | yes / no / no | yes |
| four cards (PP2 x TP2) | #1 + #3 + #4 experts at roofline (3.3x) | 218 (top-2 tree + depth 2 on the top-1 branch) | 144 (top-2 tree at the first position) | 124 | yes / no / no | yes |


What the tables say:

- **Deeper speculation does not pay with today's kernels.** Every block scheme with today's one-row kernels is below
  today's 66.9 tok/s pipeline (51 at best). Even with the best existing tiles chosen per site, two cards reach 65 and
  four cards 84 under realistic costs: about today's 66.9 / 78.3, so a multi-row verifier on today's kernels would not pay.
- **Idea #1 (multi-row kernels) is the enabler** but not enough on its own: 86 (two cards) / 109 (four cards) realistic,
  138 / 169 upper bound.
- **Idea #2 (more tokens per cycle)** gains little beyond depth 1–2 at 76% acceptance once rejected blocks cost a redo;
  depth 3 helps only in the serial and upper-bound columns. The top-2 tree is the best realistic shape (its block
  survives more often). Acceptance moves the picture more than depth: at a = 0.9 per position the full stack on four
  cards projects 167–195 with redo.
- **Idea #3 (glue)** adds 10–12%, **idea #4 (experts)** 10–25% on top; both matter more as M grows because experts and
  replicated glue are what still scale.
- **Idea #5 (TP4, one stage)** has no miss cost, so its serial numbers are its real numbers: 119 with #1, 150 with
  everything, 191 if its exchanges were free. Replicated work (8.2 ms per token over both halves, every card) is its
  floor; it needs #3 first.
- **200 tok/s** appears only in the upper-bound column with #1 + #3 + #4 on four cards (206–218), or two cards with
  roofline experts (200–201). No realistic column reaches it.

## Recommended next build

**M ≤ 4 weight-stationary kernels for the dense K-quant/IQ4_XS projections and the shared expert** (gdn.qkv Q6_K,
gdn.z Q4_K, qsa.qgate IQ4_XS, shexp gate/up/down), as new small-row tiles in the existing exact token-row family,
gated bitwise per row against the one-row kernels.

- Measured upside: these sites are the largest gap at two rows, 2.17 ms (rank 0) / 2.22 ms (rank 1) between the best
  existing tile and the one-row time. Closing it takes a two-row pass from 1.55× to about 1.33× a one-row pass
  (rank 0: 15.5 → ~13.3 ms busy).
- Why that is the threshold that matters: by the [width-2 falsifier](../pp4-review-2026-10-28/verifier-width2-cost-screen.txt)
  a two-row block must cost less than 2p = 1.52× one row (p = 0.761) before any start/resolve cost. Best existing
  tiles (1.55×) fail it; with these kernels there is about 0.19× of a row left for the verifier's own costs; the ideal
  set (1.17×) leaves 0.35×.
- Immediately available without a build (measured here, exact): for chunks of M ≤ 4 the 1x4 / 1x1 reuse2 tiles and the
  existing per-slot expert kernel cost 1.55× instead of the default batched path's 2.75×. Today no decode path uses
  M ≤ 4 chunks, so this is a configuration fact for the verifier, not a speed change.
- Next after it: an M ≤ 4 expert kernel without the bucketing pass (gap 0.7–1.1 ms at M = 2, 2.9–4.1 ms at M = 4),
  then the multi-row verifier transaction itself (per-row recurrent checkpoints,
  [verifier screen](../pp4-review-2026-10-28/verifier-batch-screen.txt)).

## Incidents

None on the device: every kernel-log check before and after the 12 arms (3 smoke arms, 7 census arms, 2 tile arms) was
clean (`logs/kernel-log-*.txt`), no fault, reset or coredump; MemAvailable stayed ≥ 63 GB during a load and ≥ 96 GB
between arms. One harness bug in the first smoke: the driver sent RESET without the `reset-<sequence>.txt` metadata
file the engine requires; the rank refused it with `failure.txt: reset metadata` and exited cleanly; fixed, smoke rerun.

## Files

- Scripts: [census_driver.py](census_driver.py), [run_census.sh](run_census.sh), [analyze.py](analyze.py),
  [routes.py](routes.py), [tiles.py](tiles.py), [wall.py](wall.py), [weights.py](weights.py), [census.py](census.py)
  (`python3 -B census.py` rebuilds `results/census.json`; `--markdown` prints the tables above).
- Results: `results/rank{0,1}-sites.json` (per site, per mode), `rank{0,1}-tiles.json`, `rank{0,1}-routes.json`,
  `token-wall.json`, `exactness-*.json`, `census.json` (tables, glue, experts, projection).
- Raw runs (traces, dumps, rows, routes; 12.2 GB, sha256 lists beside them):
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/decode-site-census-runs` (arms A0 A1 C1 B0 C0 R1 R0 and the
  smokes) and `.../decode-site-census-tiles-runs` (T1 T0). Logs: `logs/`.
