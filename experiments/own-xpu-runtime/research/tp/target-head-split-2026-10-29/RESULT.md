# Rank 1's target head split across its two cards (2026-10-29)

**Question.** In the four-card TP2×PP2 layout, rank 1's half sets the pace in hit cycles: about 11.1 ms in the service
against rank 0's draft plus speculative half of about 10.7 ms
([draft-split-2026-10-29](../draft-split-2026-10-29/RESULT.md), section 5). Under TP both of rank 1's cards compute
the whole target head (248,320 F32 logits and their argmax, about 1 ms). Can each card score half the vocabulary,
exactly?

**Answer.** Yes, and with both head splits the service gets faster.
- With `OWNRT_TARGET_HEAD_SPLIT=1`, rank 1's decode half drops from 10.88–10.92 to 10.40–10.42 ms (−0.48 ms, −4.4%) on
  both card pairs tried. It is bitwise equal to one card (1079/1079 buffers, all tokens).
- Each card also stores only half the head, so rank 1 plans 31.46 instead of 31.72 GB per card at 64K.
- **Suite at 65536, same binary, one server per arm** (outputs equal B19 in every arm):

| Arm | Median tok/s |
|---|---:|
| Two cards | 66.42 |
| TP | 72.99 |
| TP + target head split | 73.73 |
| **TP + both head splits** | **74.66** |

- With the target head split rank 0 sets the pace again, so the draft head split now pays off. Against TP alone, both
  splits are faster on every prompt (1.004–1.033×, median 1.023×). Against the target split alone they are
  1.007–1.027× (median 1.012×). Both splits give 1.124× two cards.
- One server per arm is not a speed verdict: back-to-back drift here is up to about 3%. Every per-prompt ratio of the
  combined arm is above 1, but a repeat on fresh servers should confirm it.

Binary `b7786ad42675…` (build r3, [receipt](../../../engine/receipts/b7786ad42675.json)), built from `engine/src` into
`/dev/shm/engine-build-target-head-split-20261029-r3`. Context 65536, B19 flags ([arm_env.py](arm_env.py)), F32 target.
Builds r1 and r2 never ran on a card: their CPU plan probes refused the split plan, first on a too-strict wiring check,
then because the scratch writer set did not list the two new operations (both write no scratch).

## 1. Every place the target head runs

The target head is three plan sites on rank 1: `final.*` (norm, low, gate, mix: the head input), `logits` (the
248,320-row raw Q6_K GEMV into F32) and `argmax` (ArgmaxFast, the `specialised` class of the SC117 dispatch).
- **Decode halves** (`HALF` with fixture > 0) run all three. This is the only place the head runs.
- **Prompt rows read token by token** (fixture 0) skip `final.*`, `logits` and `argmax` by label (`prefill_skip`).
- **Batched prefill** (`prefill_engine.hpp`) excludes the same labels (`prefill_runs`). The first decode token after a
  prompt is an ordinary decode half (the controller's seam).
- **No multi-row verify on rank 1.** In this pipeline rank 1 checks one position per half; `--max-new` is the request
  cap, not a row count. The M = 2–4 verifier rows belong to other lanes.
- **Other head paths** are refused or off in this configuration: the p105 split head and the packet188 kernel-io
  token read are refused with F32 activations, and the head transpose is not selected.

So the flag changes only the decode half's `logits` and `argmax` launches. All new launches keep the labels `logits`
and `argmax`, so the prompt-row and prefill skips apply to them unchanged.

## 2. What was built: `OWNRT_TARGET_HEAD_SPLIT=1` (opt-in, TP ranks)

- **Plan** (`rank.hpp`, the TP transform; needs `OWNRT_TP_EXCHANGE=direct` and F32):
  - `logits` becomes one launch per card with `row_begin`/`row_count`: card 0 rows [0, 124,160), card 1 rows
    [124,160, 248,320). Each card loads only its rows of `output.weight` (the existing TP row-slice loader) and runs
    the unchanged raw row kernel into the start of its own `logits` buffer. A row's arithmetic does not depend on the
    row count (the Stage 1 row splits rely on the same property).
  - `argmax` becomes, per card: `tp_head_shard` (ArgmaxFast's scan on this card's rows, a Best record into slot c of
    the 8-word buffer `argmax.pair#tp`), one direct exchange (`tp_xgather`, own slot to the peer's same slot), and
    `tp_head_merge` into `next_token` on both cards.
  - `OWNRT_TARGET_HEAD_SPLIT_ROWS` moves the boundary (a multiple of 128). A TP rank without a target head (rank 0)
    leaves the flag inert and writes `target-head-split.json` with `applied: false`.
- **Kernels:** the draft head split's kernels ([draft_head_split.hpp](../../../engine/src/stage2/packet194-expert-diet-engine/draft_head_split.hpp)),
  now templated on the logit type (BF16 draft, F32 target) and on where the records start. The merge rule is
  unchanged: card 1's index wins only if its value is strictly greater, so equal values go to the lowest global index
  (+0 and −0 are equal). Any non-finite logit sets that card's sticky error and an error record, and both merges then
  fail exactly where ArgmaxFast fails; the half then stops with the sticky rank error, as before. On that failure path
  `next_token` keeps its old value where ArgmaxFast writes a fallback index; nothing reads it there.
- **Engine** (`main.cpp`): the two new operations; `strict_snapshot.hpp` lists them as writing no scratch.
- **Dump:** `logits` is registered in `head_split_layout` (card 0's rows at 0, card 1's rows at 124,160), so the state
  dump reassembles the one-card logits and the bitwise compare against one card is unchanged. `argmax.pair#tp` is a
  TP-internal buffer (not model state). Card-1-equals-card-0 now compares 784 buffers (`logits` differs by design).
- Exchanges per rank-1 half: 69 (68 + 1).

## 3. Gates

**CPU unit test** ([head_unit_test.cpp](head_unit_test.cpp), [output](head_unit_test.out)): the engine's own shard and
merge kernels (on the OpenCL CPU device; no GPU opened) and their host twins, against a plain sequential argmax and a
verbatim copy of ArgmaxFast's kernel; the merge is run on both simulated cards.
- **382 cases, 0 failures.**
  - Target, F32, 248,320 rows, six split points (128 … 248,192): 241 cases. They cover random logits, equal maxima
    across the split, at the boundary, in two lanes and inside card 1; the maximum only on card 1; all-equal rows;
    FLT_MAX on both cards; all −FLT_MAX but one; equal and unequal denormal maxima; a one-ulp-larger value on card 1;
    +0/−0 in all four orders; NaN, −NaN, +inf and −inf on either or both cards; a sticky error already set on either
    card.
  - Draft, BF16, 91,392 rows (regression of the generalised kernels): 141 cases.
- 72 cases have the maximum on both cards (48 target). A negative control (card 1 wins ties) differs from ArgmaxFast in
  all 72. Device records equal the host twins bit for bit; card 1's merge equals card 0's.

**Device gates** (rank-1 harness [tp_rank1_driver.py](../service-ready-2026-10-29/tp_rank1_driver.py) unchanged,
context 65536, 1,100 prompt rows (256-row chunks, the 512-row raw ring wraps twice), then 16 decode halves; cards
23 + 47; phases `q1-smoke`, `q2-gate`; [logs/q2-gate-compare.txt](logs/q2-gate-compare.txt)):

| Comparison (full dump, bitwise) | Buffers | Tokens |
|---|---|---|
| one card, **new binary vs previous binary** `0702b5a9cd78` (r1-one-b) | **1079/1079** | 16/16 equal |
| TP, flag off, vs one card / vs the previous binary's TP (r1-tp-b) | 1079/1079 | equal |
| **TP + target head split vs one card**, batched prompt | **1079/1079** | equal |
| TP + split vs one card, prompt read token by token (the fixture-0 head skip) | **1079/1079** | equal |
| TP + split with card 0 at 131,072 rows vs one card | **1079/1079** | equal |

- The first device run was the smallest smoke (`s-tpt`: 16 prompt rows, 4 halves): rc 0, 0 timeouts.
- The reassembled `logits` (all 248,320 rows of the last half) and `next_token` are among the 1079 buffers. Of the 16
  tokens, 2 come from card 1's rows (218,223 and 248,044).
- Exchanges: 0 timeouts and 0 aborts in every TP run. Card 1 equals card 0 on all 784 (split) or 785 (flag off)
  buffers both hold in full. The kernel log was clean before every phase (24 h) and after every arm.

## 4. Speed: rank 1

Rank-1 harness, 1,100 prompt rows batched, then 48 decode halves; median of halves 3–48; A/B/A/B on cards 23 + 47,
then A/B on 43 + 47 (rank 1's service cards) ([results-timing.json](results-timing.json)):

| Cards | TP (flag off) | TP + target head split | Change |
|---|---:|---:|---:|
| 23 + 47, run 1 / 2 | 10.921 / 10.882 | **10.423 / 10.406** | −0.48 ms |
| 43 + 47 | 10.886 | **10.401** | −0.49 ms |

- One card: 12.41 ms. TP alone is 1.14× one card; TP with the split is **1.19×**.
- All six timing runs produced the same 48 tokens, with 0 exchange timeouts.
- Expected effect in the service: rank 1's in-service half is about 11.1 ms, so with the split about 10.6 ms. Rank 0's
  draft plus speculative half (about 10.7 ms in the service) then becomes the slower stage in hit cycles, so the period
  should drop by about 0.4 ms, not the full 0.48. This is a projection; the suite measures it.

Raw runs (sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/target-head-split-runs-q1-q3/`.

## 5. Suite at 65536: 66.42 / 72.99 / 73.73 / 74.66 tok/s, outputs identical

Run as service-ready-2026-10-29 step 4 ([run_arm.sh](run_arm.sh), copied with fresh names): the lab service on
127.0.0.1:18171, one fresh transient unit per arm (`sc117-tp-svc-th-arm-{two,tp,tpt,tpts}-20261029`, `Restart=no`,
`KillMode=process`, no SIGKILL, `LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19), all four card locks held by
`sc117-tp-svc-th-locks-20261029`.
- Arm order: two, tp, tpt in [suite_chain.sh](suite_chain.sh). The fourth arm, tpts, was launched once afterwards
  ([suite_extra.sh](suite_extra.sh), with a fresh lock holder); it is a new arm, not a retry.
- Each arm: one cold request per frozen prompt (512 cap, greedy), then one cold 3,490-token prompt (64-token cap).
- Same binary `b7786ad42675` everywhere, B19 flags at 65536 ([arm_env.py](arm_env.py)). The arms differ only in
  `OWNRT_TARGET_HEAD_SPLIT=1` (tpt, tpts) and `OWNRT_DRAFT_HEAD_SPLIT=1` (tpts).
- The lab service is service-ready's; the adapter passes the split keys to TP ranks. `sc117-lan` was not touched.

| Arm | Cards (rank 0 / rank 1) | Median tok/s | Mean | Range | MTP acceptance | TTFT, 3,490-token prompt | Its decode tok/s | Outputs |
|---|---|---:|---:|---:|---:|---:|---:|---|
| two: control | 23 / 47 | **66.42** | 66.64 | 64.30–70.02 | 4533/5954 = 0.7613 | 12,517 ms | 60.20 | = B19, all 12 |
| tp | 23+27 / 43+47 | **72.99** | 73.37 | 70.57–77.41 | 0.7613 | 10,367 ms | 66.47 | = B19, all 12 |
| tpt: tp + target head split | 23+27 / 43+47 | **73.73** | 73.89 | 71.28–77.76 | 0.7613 | 10,355 ms | 67.80 | = B19, all 12 |
| **tpts: tp + both head splits** | 23+27 / 43+47 | **74.66** | 74.95 | 72.05–78.94 | 0.7613 | 10,370 ms | **68.58** | = B19, all 12 |

**Paired, per prompt** ([results/summary.json](results/summary.json)):

| Pair | Per-prompt ratio (median, range) | Medians |
|---|---|---:|
| tpt / tp | 1.008 (0.996–1.015) | 1.010 |
| tpts / tpt | 1.012 (1.007–1.027) | 1.013 |
| **tpts / tp** | **1.023 (1.004–1.033)** | 1.023 |
| tpts / two | 1.124 (1.116–1.134) | 1.124 |

**Outputs:** all 5,965 ids, hashes and per-prompt MTP guesses and hits equal B19 in all four arms. The 64 long-prompt ids
are equal across the arms. `cached_tokens=0` everywhere.

**Gates:**
- The startup gates passed in every arm: the F32 self-tests, the pinned 4096 and 65536 state oracles (with the split
  logits reassembled), and 13/13 batched-prefill cases.
- In tpt and tpts, rank 1's `target-head-split.json` shows the split applied (124,160 / 124,160 rows). Rank 0's shows
  `applied: false`, as designed. Rank 0 wrote `draft-head-split.json` in tpts only.
- Teardown clean in every arm (`terminal.json` passed). The kernel log was clean before, after ready, after the suite
  and after each arm. The only lines in the window were AppArmor audits of a snap.

**Who sets the pace** (controller trace of the 3,490-token request, positions 3,490–3,553;
[results/long-prompt-trace.json](results/long-prompt-trace.json); medians, ms):

| Arm | Rank 0 speculative half (p10–p90) | Rank 1 half | Draft | Rank 0's half ends after rank 1's by | Decode wall |
|---|---:|---:|---:|---:|---:|
| tp | 9.431 (9.40–10.51) | 11.117 | 1.284 | −0.04 | 948 ms |
| tpt | 9.401 (9.38–9.49) | **10.632** | 1.285 | **+0.38** | 929 ms |
| tpts | 9.372 (9.36–9.42) | 10.678 | **1.118** | **+0.15** | 919 ms |

- With the target head split, rank 1's in-service half is 0.49 ms shorter, so rank 0's draft plus speculative half
  becomes the later of the two: rank 0 now sets the pace in hit cycles.
- That is why the draft head split pays off now (tpts / tpt 1.012×) when it did not before
  ([draft-split-2026-10-29](../draft-split-2026-10-29/RESULT.md): 0.996–1.009×).
- The slow speculative halves seen once in that suite's split arm (10.12 ms median) did not recur here (9.37 ms). This
  suite's plain TP arm also had slow ones (p90 10.51 ms). So that earlier slowdown was most likely server-instance
  variance, not the draft split.

Files: per arm `results/arm-*/`. Raw run directories (912 files, 335,278,304 B, sha256-verified):
`/mnt/raid-models/ownrt-experiment-archives/2026-10-29/target-head-split-suite-20261029/`.

## Next

1. **Confirm on fresh servers:** repeat tp against tpts, for example tp, tpts, tp, tpts. After that, put both flags in the
   lab service's TP arm. The `sc117-lan` switch is the owner's call; sessions and continuation are still refused under TP.
2. **Rank 0 now sets the pace, by about 0.15 ms.** Next on rank 0, from the draft profile
   ([draft-split-2026-10-29](../draft-split-2026-10-29/RESULT.md), section 1): the draft's large GEMVs (qsa.qgate
   122 µs, attention output 83, experts 72 + 50, merges 52 + 36). Splitting them by rows across rank 0's two cards
   would take about 0.15 ms off. The fixed costs of rank 0's half (speculative snapshot) are the other lever.
3. **Misses:** rank 1 still waits the whole 9.4 ms redo of rank 0 on each miss (24% of positions). That is the largest
   remaining structural cost.

## Files

- Engine: `rank.hpp` (TP transform), `main.cpp` (operations), `strict_snapshot.hpp` (scratch writer set),
  `draft_head_split.hpp`, `mtp_kernels.{hpp,cpp}` (F32 shard, record base).
- Lab: [run_phase.sh](run_phase.sh) (mode `tpt`), [analyze_rank1.py](analyze_rank1.py), [collect_evidence.py](collect_evidence.py),
  [archive_runs.sh](archive_runs.sh), [arm_env.py](arm_env.py) (arm `tpt`), [make_launch.py](make_launch.py),
  [plan_probe.py](plan_probe.py), [lab/](lab/) (the adapter passes the split keys to TP ranks), launch JSONs
  `rank{0,1}-launch-c65536-b7786ad42675.json`.
- Suite: [run_arm.sh](run_arm.sh), [suite_chain.sh](suite_chain.sh), [suite_extra.sh](suite_extra.sh),
  [compare.py](compare.py) (ratios for every split arm), [trace_summary.py](trace_summary.py), [lab/](lab/).
- Evidence: [evidence/](evidence/) (per run: summary, target state hashes for the gate runs, split, exchange and
  card-compare statistics; CPU plan probes), [results-gate.json](results-gate.json), [results-timing.json](results-timing.json),
  [results/](results/) (suite), [logs/](logs/) (phase logs, kernel-log checks, archive receipts).
