# qkv-1: split the q_a + kv rows across the six cards (plan item D), 2026-11-13

## In plain words

Today every card reads the same 1,792 q_a + kv rows (1,280 + 512 rows x 5,120 columns) in every layer: six copies of
the same work. qkv-1 gives each card one sixth of those rows, then the cards swap their pieces (one small exchange per
layer) before the two norms. Each row is still computed by the same code on the same bytes, just on one card instead
of six, so the results are bit for bit the same.

- Switch: `OWN_QKV_SPLIT` (0 = off, today's engine; 1 = all three parts below). Opt-in, nothing changes when off.
- Expected: about 0.25-0.3 ms less per one-token step (about 2 % of the ~12.7 ms step), about 0.2-0.4 ms less per
  check of 2-6 tokens. Prompt reads in the production form (PX halves) are NOT covered (see "What is left").
- Result: see "Results" (traces and plain speed runs on six cards).

Patch: `/home/steve/dsv41-work/qkv/qkv-1.patch` (against lab HEAD 96ffc00a2, `git apply --check` clean; three files:
backend_sycl_v41.hpp, backend_sycl_v41_mt.inc, own_run_v41.cpp).

## 1. Ledger (what the replicated rows cost today)

Profile `runs/lp107/p3k_prof.log` (tp107, 3K prompt, one-token decode, 78.77 tok/s, wall 12.696 ms per step), the
q_a + kv launches per step:

| launch | per step | mean | total |
|---|---|---|---|
| Q8_0 pair, no rider (`RowsPair<NoRows, DenseRows<GemvQ8P<160>> x2>`) | 24 | 19.54 us | 0.469 ms |
| Q6_K pair, no rider (`... GemvQ6KP<20> ...`) | 13 | 17.35 us | 0.226 ms |
| Q8_0 pair with the attention mix's dot rows (`HcDotsRows<5120, 8>` rider) | 3 | 23.53 us | 0.071 ms |
| **total** | 40 | | **0.766 ms (6 % of the step)** |

(The brief's first estimate counted q_b's launch; q_b is already split by heads.)

One-card bench, card 3 (`src/bench_qkv.cpp`, logs `logs/out-t1.txt` M = 1..6, `logs/out-t2.txt` M = 1 again with a
400-launch warm-up + prompt blocks; kernel time, cold weights cycled over 8 copies, median of 5 rounds; work-groups
of 128 items for the shares). "full" = today's production launch for all 1,792 rows; "share" = the slowest of the six
cards' shares (rows split as the engine splits model rows: 16-row units, equal weights: 288 / 304 / 304 / 288 / 304 /
304 rows; card 4 holds q_a 1184-1280 + kv 0-208, card 5 kv 208-512).

| block | Q8_0 full | Q8_0 share | Q6_K full | Q6_K share |
|---|---|---|---|---|
| 1 token (t2) | 18.44 | 5.73 | 16.56 | 7.50 |
| 1 token, dot rows riding (t2) | 22.40 | 7.81 | 20.31 | 10.00 |
| 2 tokens (today: dot rows ride) | 22.29 | 5.73 (G1) | 23.65 | 7.50 (G1) |
| 3 tokens (today: dot rows ride) | 23.96 | 6.04 (G1) | 27.08 | 7.81 (G1) |
| 4 tokens | 20.94 | 6.25 (G1) | 24.38 | 8.23 (G1) |
| 5 tokens | 22.60 | 6.67 (G1) | 38.02 | 8.65 (G1) |
| 6 tokens | 22.40 | 7.71 (G1) | 38.02 | 10.21 (G1) |
| 64 tokens | 180.42 (X8R2L) | 48.96 (X8R2L) / 71.67 (G4) | 330.94 (G4R2) | 70.42 (G4R2) / 87.29 (G4) |
| 256 tokens | 837.92 (X4R4) | 178.12 (X4R4) / 343.54 (G4) | 1360.52 (G4R2) | 251.56 (G4R2) / 355.00 (G4) |

All in us. Bitwise: every share, every form, every token, every word equal to the full launch (t1: 240 comparisons,
t2: 18, 0 differ). Kernel journal clean for both runs (`logs/kj-t1.txt`, `logs/kj-t2.txt` empty).

Notes from the bench:
- At 2-3 tokens the dot-row rider costs a share more than the rows themselves (Q8 2 tokens: 5.7 -> 11.8 us; 3 tokens
  6.0 -> 16.6): its FP64 chains set the launch length once the rows are a sixth. So under the split the dot rows move
  to the pre-norm's launch (`OWN_MT_SKDOTS`'s SkDotsWM rows, which blocks of 4+ tokens already use).
- Q6_K one-token share: in t1 card 5 (kv rows only) was the slowest (7.40 vs 5.10-5.21), in t2 all six took
  7.40-7.50; not settled.
- Work-groups of 128 items beat 512 for a sixth of the rows (rider case 7.81 vs 10.31).

Exchange cost (xchg2's `xchg2/logs/xlat2-table.txt`, us, all six cards): flags alone ~4.2; the h exchange (3.4 KB
per sender per token) as XchgP 5.53 at 1 token; XchgQ (`snk4`) 7.59-7.94 at 1-2 tokens. The q_a + kv piece is 1.2
KB per sender per token (304 floats), so one token or a small check is at the flags floor: ~4.3-5.5 us as XchgP,
~7.7-8.1 us as XchgQ at 4-6 tokens.

## 2. Prediction

One-token step: 24 x (18.44 - 5.73) + 13 x (16.56 - 7.50) + 3 x (22.40 - 7.81) = 467 us of kernel time saved, minus
40 exchanges x 4.3-5.5 us = 172-220 us: **net 0.25-0.29 ms per step, 1.9-2.3 %** (78.8 -> ~80.4-80.6 tok/s).

Checks (per check of M tokens; 27 Q8_0 + 13 Q6_K layers; moved dot rows estimated at the rider's cost in the full
launch, 3.6 / 4.3 us at 2 / 3 tokens; at 4-6 tokens ~2.5 us of extra card skew from OWN_MT_DSPLIT's dot split):

| M | kernel saved | added (exchange + moved dots + skew) | net |
|---|---|---|---|
| 2 | 657 us | 346 us | ~0.31 ms |
| 3 | 734 us | 391 us | ~0.34 ms |
| 4 | 607 us | 408 us | ~0.20 ms |
| 5 | 812 us | 416 us | ~0.40 ms |
| 6 | 758 us | 424 us | ~0.33 ms |

Both above the brief's stop line (0.15 ms per step).

Prompt blocks without PX halves (bit 8): with the slowest share form (G4, what the engine's general rules pick for
a share's row count), 64 tokens save ~6.1 ms of kernel time per block against 1.0-1.4 ms of pulls (est.), 256 tokens
~26 ms against 3.2-4.8 ms. But production reads prompts as PX halves (`OWN_PROMPT_BLOCK=512 OWN_PX=1
OWN_PX_BIG=1`), where qkv-1 stays off; only odd-sized remainder blocks and non-PX block sizes take it.

## 3. Design

- `OWN_QKV_SPLIT` bits: 2 one-token steps, 4 blocks of 2-6 tokens (checks, small prompt blocks), 8 larger blocks
  (prompt blocks without PX halves, up to the arena's slots); `=1` means all (14). Tuning knobs: `OWN_QKV_XQ` (XchgQ
  from this many tokens, default 5; below it XchgP), `OWN_QKV_WG` (128 default / 512), `OWN_QKV_FORM` (1 default:
  DenseRowsG<1> pairs; 2: DenseRowsG<2>).
- Shares: tp_setup splits the 1,792 concatenated rows in 16-row units with equal weights (`qkr0/qkr1`), the same
  split helper as the model rows. Exchange part `XP_QKV` (xbounds = the shares).
- Arena: a new region `xqk` after everything else (8 slots of 1,792 floats; with bit 8 one slot per token of the
  largest block, mtba_n = 264 slots, 1.9 MB per card). Token t's rows at `xqk + t * 1792` (q_a rows, then kv rows).
- One-token step (tp_phase case 0, the fused path): `qkv_share1` launches the card's q_a rows and kv rows (plus the
  dot-row rider when the norm did not already compute them) in gemv_pair_ex's launch type over the share's row
  ranges, writing into the arena slot; then `xchg(XP_QKV, 1 slot)` (XchgP under OWN_XPUSH2); both norms
  (SkNormPairW, or the NormRows pair) read the gathered rows from the arena instead of s.qa / s.kv.
- Blocks of 2-6 tokens (tpm_layer): `qsp` = split on. The attention mix's dot rows leave q_a's launch for the
  pre-norm's (skdA: the SkNormDotsWM / SkDotsWM rows that blocks of 4+ tokens already use); `qkv_share_m` launches the
  share as one RowsPair of DenseRowsG<G> rows (strided output into the arena), then `xchg(XP_QKV, M slots)` (XchgP
  below OWN_QKV_XQ tokens, XchgQ from there); both norms read the arena slots (per-token stride 1,792; SkNormPairWM
  and TokRows<NormRows> take the strides).
- Larger blocks (bit 8): `qkv_share_big` = the production gemv_m call with its row-range arguments (q_a rows, kv
  rows; the card holding both launches twice), output stride 1,792; the exchange is the pull (use_pull).
- Off conditions (printed at start-up as "OWN_QKV_SPLIT: off (...)"): model shape (q_a 1,280 + kv 512, h 5,120),
  OWN_K7, OWN_XTAIL, OWN_XLL, OWN_DEV_INDEX=0 (a serial step's host top-k would wait on a card queue that waits on
  the gather of cards not yet submitted). Per step: not in OWN_PX halves (px_run), not in the draft's block steps
  (dr_step), not without OWN_MT_SMALL / OWN_MT_SKDOTS, only packed Q8_0 / Q6_K pairs of the same type.
- Exchange safety (reuse rule): every card reads the gathered rows (both norms) before its next exchange (output-a),
  so a peer's next push into that region (next layer) comes only after this card raised that exchange's flag.
  With OWN_MT_DSPLIT the attention partials' `ds_arm` comes after this exchange, so it never carries the second
  region. Serial trace steps queue every card's phase before any host wait, so the gather in the middle of phase 0
  cannot deadlock (the one host wait there, OWN_DEV_INDEX=0's top-k, switches the split off).

## 4. Why the bits are the same

- Rows: each q_a / kv output row (and token) is computed by the same per-row function (`GemvQ8P<160>::row` /
  `GemvQ6KP<20>::row` at one token, `rowg<G>` in blocks, the WS forms in gemv_m's prompt picks) over the same packed
  row bytes and the same activations as today; only the card, the launch's row offset and the output address change.
  The engine already relies on every dense form giving the same sum per (row, token) (one-token vs block traces are
  identical); per-row code has no cross-row or work-group dependence (-fp-model=precise, -ffp-contract=off). The bench
  checks it directly: all six shares in every form against the full launch, 0 words differ.
- Exchange: XchgP / XchgQ / XchgPull are plain 16-byte copies of the rows into every card's arena region.
- Norms: the same SkNormPairW / NormRows code over the same values; only the input pointer and per-token stride
  change.
- Dot rows at 2-3 tokens: moved from the HcDotsRows rider to SkDotsWM (OWN_MT_SKDOTS's form). SkDotsWM's partials
  differ but its finish outputs are the production ones by construction (pcd-1's C0 argument: it checks float(T)
  against the production float sum and the same rsqrt per row, and writes the production partials where that check
  fails); blocks of 4+ tokens and the one-token path already run it.
- Off (`OWN_QKV_SPLIT=0`, the default): qkv_on is false, the arena does not grow, every launch and exchange is the old
  one (the only code that runs differently is a flag test).

## 5. Results

(filled in below as the runs finish)

## 6. What is left

- Prompt reads in PX halves (production's `OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1`): the split there needs its
  exchange on the PX exchange queue between segments; not done.
- Q6_K one-token shares: 7.4-7.5 us in t2 against 5.1-5.2 for five of six in t1; worth a look (uneven shares or
  another share form).
- The 3 one-token layers whose dot rows still ride the share (7.81 vs 5.73 us).
- OWN_QKV_XQ = 4 vs 5 (XchgP and XchgQ tie near 4 tokens).
