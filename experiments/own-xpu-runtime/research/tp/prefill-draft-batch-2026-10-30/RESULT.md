# Four-card prompt reading: the draft's prompt rows batched, exact (2026-10-30)

**Question.** After prefill-host-2026-10-30, rank 0 was still the critical path in four-card prompt reading: 446 ms of
prefill plus 57 ms of draft per 256-row chunk, against 465 ms on rank 1 (TTFT 239.3 s on the 121,854-token prompt). Its
draft chunk is device-bound: 256 rows × 15 single-row commands. Run those rows as one launch per site over the whole
chunk, exactly, toward about 221 s.

**Answer.** The four-card layout now reads the 121,854-token prompt in **222.50 / 222.47 s** (two fresh servers) against
**239.30 s** for tptsxqckh + HC on the same binary (−16.8 s, −7.0%).
- Decode after it is unchanged: 84.44 / 84.56 against 84.52 tok/s.
- All 512 outputs equal the 3+1 262K reference, the suite equals B19, and the 3,490-token prompt reads in 6.61 s
  instead of 7.09 s.
- **Draft chunk:** 56.8 → 13.8 ms per 256 rows (15 launches instead of 3,840). Rank 0 now needs 460 ms per chunk,
  rank 1 needs 466 ms, and **rank 1 bounds**: it is busy for the whole prompt (idle 0.02 s).
- **Exactness:** one new default-off flag; 15/15 rank-harness comparisons bitwise equal, including two-request cases at
  sp=600 and sp=64 and rank 1's exported draft-input rows; every server passed the startup gate 13/13.
- **The moe-ones finding** from the HC agent's harness is a check that was too strict, not an engine hazard (§3).

## 1. What was built (engine r1 `e6daa268a3a8` = HEAD `3d85cdb20` + one default-off flag)

`OWNRT_DRAFT_CHUNK_BATCH=1` requires `OWNRT_DRAFT_CHUNK_REPLAY=1` and `OWNRT_DRAFT_CHUNK_KV_ONLY=1`. It is in
[engine-draft-batch.patch](engine-draft-batch.patch): `mtp.hpp`, the new `draft_batch.hpp`, and `adapter.cpp`.

- **The sites.** The 17 KV-only draft sites become 15 launches per chunk plus two copies (the staged hidden and
  embedding rows). The row path issues n × 15 commands. Every kernel computes each output with the single-row
  kernel's unchanged arithmetic; only the mapping from work-item to (row, token) changes:

  | Site | Row path kernel | Batched kernel (`draft_batch.hpp`) |
  |---|---|---|
  | merge embedding / hidden norm, hc.a.norm | `p59::Norm` | `NormTokens`: one 256-item group per normalised row, gain row r of its token |
  | merge.embedding_projected, merge.projected (+ fused merge add), qsa.k, qsa.v, qsa.ik | `p59::Dense<2560,..,1,1>` / `DenseBatch4` | `DenseTokens<2560,4>`: `p59::lane()` per output, same 32-lane tree, `p59::tail()`'s expressions; merge add with the token's own embedding row |
  | hc.a.low (+ fused silu/4) | `p59::Dense<10240,..,1,4>` | `DenseSplitTokens<10240,4>`: `Dense::chain` per part, the same subgroup and part trees |
  | hc.a.gate | `mtp36` Dense (BF16 production) | `GateTokens<320>`: its 32 lane sums `p28::dense_lane` and the same adjacent tree, one work-item per output |
  | hc.a.mix | `mtp36` Elements mix | `MixTokens`, with the same active / sticky-error guard |
  | qsa.prepare, qsa.pool | generic kernels, one row | the same generic kernels with `Spec.tokens = n` (rows at position + r; pool reads earlier rows from raw and the chunk's own rows from its input), as the target's batched prefill runs them |
  | begin.0, commit.final | adapter glue, one row | the glue's token rows on per-row positions (P0 + r); the draft's position then becomes P0 + n |

- **What carries beyond the chunk.** Row-major values live in 21 n-row buffers (51 MB at 256 rows). Only the persistent
  writes carry beyond the chunk (keys, values, raw, pooled, position), as with the KV-only rows. The single-row
  intermediates keep their previous values instead of the last row's. They are dead: the next step writes them before
  reading them.
- **Refusals.** At the first chunk the engine refuses unless the KV-only derivation keeps exactly these 17 sites, each
  with the kernel choice it is batched for (`check_chunk_batch`). The CPU-only check
  [check_schedule.py](check_schedule.py) ran before any build or device run:
  [results/schedule-check.json](results/schedule-check.json). It covers the kept set, the kernel choices, the dataflow
  and the buffer sizes.

## 2. Gates (rank harnesses at 131,072; A = tptsxqckh + `OWNRT_HC_KERNELS=1`, B = A + `OWNRT_DRAFT_CHUNK_BATCH=1`)

15/15 comparisons are bitwise equal ([results/gates.json](results/gates.json), [gates_summary.py](gates_summary.py)),
with 0 kernel-log fault lines. Every arm ran under all four card locks, and every phase was archived to the RAID
(sha256) before the next one.

| Gate | Rank 0 | Rank 1 |
|---|---|---|
| smallest smoke (40 rows, 16-row chunks), B = A | s1: 1029 + 71 draft, draft tokens equal | — |
| B = A, 1,100 rows (hmcn) | g1 | g1, with `db` set (the service passes it to both ranks): 1079 |
| batched = token by token | g1 `tbt` | — |
| = one card at 65,536 (prefix + zeros) | `hmcn` and `m`: 1009 + 20 / 67 + 4 | 1058 + 21 |
| A on the new binary = prefill-host's tptsxqckh run (`c8e173bf4e7d`) | g1 | g1 |
| two requests, sp=600: B = A, = one card; inventories 286/286; ones | t1a | — |
| two requests, sp=64 (short second request): B = A; inventories; exact ones (k = 64) | t1b | t1c (inventories 61/61) |
| rank 1's exported draft-input rows (HC export check) | — | g1: 1,116 rows equal; t1c: 1,116 + 80 |

- The rank-1 driver is research/hc-kernels-2026-10-30's (its export check), with this folder's exact ones check. It
  compares exports when both runs recorded them.
- The rank-0 harness feeds seeded rows as rank 1's exports, so the draft's arithmetic is checked on the same input
  rows in A and B. The services read the real rows from rank 1.

## 3. The `prefill:moe-ones` inventory failure in the HC agent's harness: harmless, check made exact

**The finding (HC agent, x1 runs: one card, rank 1, the ten tptsxqckh prefill flags, 128 rows then sp=64).** The
check that "every `prefill:moe-ones` holds only 1.0 at every reset" failed in the second request's inventory, with HC on
and off alike.

- **Flag combination.** `OWNRT_PREFILL_MOE_NATIVE=1` plus a request after a reset whose batched chunks are all shorter
  than the buffer. The buffer holds prefill_rows = 256 floats. HC plays no part.
- **Harmless.**
  - The buffer is filled with 1.0 at allocation, and a request reset zeroes it.
  - Since prefill-speed r7, every batched chunk of M rows rewrites floats [0, M) before its sites.
  - The native `moe_combine` reads exactly those: the site's shape[0] is 1, so with `Spec.tokens` = M it reads
    `ones[r]` for r < M.
  - Floats from M on are never read, and token-by-token prompts never read the buffer.
  - Measured ([results/ones-check.json](results/ones-check.json)): at the reset after the 64-row second request the
    buffer is exactly 64 ones then 192 zeros, in the HC runs and in this folder's TP runs t64-r0-b and t64-r1-b.
- **Why my sp=600 gates passed.** The row count. A 600-row second request starts with a full 256-row chunk, which
  rewrites all 256 floats; a 64-row second request rewrites 64. The harness and the extras were not the cause.
- **Fix (harness only).** [inventory_check.py](inventory_check.py) `ones()` now checks the exact pattern:
  - the first request of the process: all C ones;
  - a request after a reset, read batched: min(C, rows per chunk, prompt rows) ones, then zeros;
  - a request after a reset, read token by token: all zeros.

  It passes the HC x1 runs and every r7, prefill-host and draft-batch run. It still fails the r6 expect-fail runs
  (k = 0 where 256 is required), so the reset proof of prefill-speed stands. On device here, sp=64 passes with k = 64 on
  both ranks.

## 4. Harness timing (rank alone, 131,072, 1,100 rows; mean of the full chunks after the first)

[results/harness-timing.json](results/harness-timing.json); host clocks only (`OWNRT_PREFILL_HOST_TRACE=1`).

| Per 256-row chunk | A | B |
|---|---:|---:|
| rank 0 prefill wall | 414.2 ms | 412.7 ms |
| rank 0 draft chunk | 56.3 ms (3,840 commands) | **12.6 ms** (15 launches; host staging 2.0 ms on 4 threads, about 10 ms device) |
| rank 0 critical | 470.5 ms | **425.3 ms (−45.2)** |
| rank 1 prefill wall, two cards (TP) | 462.8 ms (host blocked on the cards 415.3, host active 44.2, 150 exchange sites) | — |
| rank 1 prefill wall, one card at 65,536 (same flags that apply to one card) | 682.7 ms (device-bound: issued in 17.5 ms, then waited 660.7) | — |

## 5. Fresh servers at 131,072, A/B/B (binary `e6daa268a3a8`)

Each server was a fresh lab service. All four card locks were held by one holder unit, which waits (bounded) for cards
another agent holds. Each server had to pass its startup gate (13/13, batched reading on) before timing, then served the
12-prompt suite, the 3,490-token probe and the 121,854-token / 512-output long request. Kernel log: 15 checks, 0 fault
lines. [results/suite/](results/suite/), [results/suite/summary.json](results/suite/summary.json), long-request
timelines [results/long-trace-*.json](results/). Work directories are archived (sha256) at
`.../2026-10-30/prefill-draft-batch-suite-20261030`.

| Server | A `tptsxqckhc` | B1 `tptsxqckhcb` | B2 `tptsxqckhcb` |
|---|---:|---:|---:|
| startup gate | 13/13 | 13/13 | 13/13 |
| **TTFT, 121,854-token prompt** | **239.30 s** | **222.50 s** | **222.47 s** |
| decode after it (all 511) | 84.52 tok/s | 84.44 | 84.56 |
| 512 outputs = 3+1 262K reference (`bf1f0867d1bd`) | yes | yes | yes |
| MTP on the long request (hits / guesses) | 418 / 511 | 418 / 511 | 418 / 511 |
| 3,490-token prompt TTFT | 7.09 s | 6.61 s | 6.60 s |
| 12-prompt suite median (ids, sha, MTP = B19) | 87.64 tok/s (yes) | 87.49 (yes) | 87.46 (yes) |
| rank 0 prefill per chunk (median) | 446.0 ms | 446.2 | 446.0 |
| rank 0 draft chunk (median) | 56.8 ms | **13.8** | **13.8** |
| rank 0 critical per chunk | 502.7 ms | 459.8 | 460.0 |
| rank 1 busy per chunk / idle in the prompt | 465.0 ms / 17.4 s | **466.4 ms / 0.02 s** | **466.3 ms / 0.02 s** |

- The harness measured 56.3 → 12.6 ms for the draft chunk; the long request measured 56.8 → 13.8 ms.
- TTFT fell by the 43 ms of the draft chunk until rank 1's 466 ms took over: 476 × 466 ms + the first and last
  chunks ≈ 222.5 s.

## 6. What bounds both ranks now, and the next lever

Measured in the long request (B1) and the harness:

| | Rank 0 (cards 23+27) | Rank 1 (cards 43+47) |
|---|---:|---:|
| per chunk in the long request | 446.2 prefill + 13.8 draft = **460 ms** | **466 ms (busy all the time: idle 0.02 s per prompt)** |
| harness: share of the chunk the host waits on the cards | 90% (369 of 413 ms) | 90% (415 of 463 ms) |
| exchange sites per chunk (each drains both cards) | 138 | 150 (6 per layer over 25 layers) |
| two cards against one card (harness) | — | 682.7 → 462.8 ms: 74% of a perfect split; **121 ms per chunk (4.9 ms per layer)** over it |
| card balance (exchange poll counts × 0.18 µs per poll under TP) | — | card 0 waits for card 1 about 10 ms per chunk; card 1 waits about 0.3 ms |

- **Both ranks are now within 1.5% of each other, and rank 1 bounds.** TTFT = 476 chunks × 466 ms, about 222 s.
- Both prefills are device-bound.
- The four-card overhead is rank 1's 121 ms per chunk over a perfect split. It is made of:
  - replicated work (norms, HC glue, routing, combine and status checks run at full M on both cards);
  - split kernels that do not halve (each keeps a fixed part);
  - the 75 exchange pairs (drain, peer stores, flags);
  - about 10 ms of imbalance between rank 1's cards.
  The share of each is not measured here: that needs per-card device time, which is not allowed under `--tp-replicate`.

**Next lever (not built): measure, then cut rank 1's 121 ms.**
- **Measurement first.** The four-card shape probe (`OWNRT_TP_SHAPE_PROBE=0|1`, research/tp/stage-overhead-2026-10-30)
  runs exactly one card's split kernels on one card with no exchanges. Run with batched prefill and the host trace, it
  gives each card's own work W0 and W1 for a 256-row chunk. Then:
  - TP wall − max(W0, W1) = exchanges + synchronisation;
  - W1 − W0 = imbalance;
  - each W − 682.7/2 = replicated work + split fixed parts.
  Batched prefill under the probe is a new path, so it needs the smallest smoke first.
- **Sizing.** Every 10 ms per chunk removed from rank 1 is worth 4.8 s of TTFT, until rank 0's 460 ms takes over. So
  rank 1 alone is worth at most about 3 s, and both ranks together are worth about 20 s for 40 ms each.
  - The cheapest candidate is balancing rank 1's two cards: about 10 ms, about 3 s.
  - Larger gains need both ranks' replicated work split or fused (rank 0 has the same structure).

## Files

- Engine: [engine-draft-batch.patch](engine-draft-batch.patch) (against `3d85cdb20`).
  - Files: `engine/src/stage2/packet194-expert-diet-engine/draft_batch.hpp` (new), `adapter.cpp` (begin/commit glue
    rows admitted under the flag), `gsq-rco-iq3s/integration/.../native-src/mtp.hpp`.
  - Receipt `engine/receipts/e6daa268a3a8.json`. The build is at `/dev/shm/engine-build-prefill-draft-batch-20261030-r1`
    and archived at `.../2026-10-30/engine-builds/prefill-draft-batch-20261030-r1.copy` (sha256).
  - The private copy was written on `225c05aeb` and moved onto `c1c3012e9` and `3d85cdb20` as the HC commits landed.
    Nothing was built until the HC end gate finished.
- Harness, copied from prefill-host-2026-10-30:
  - extras `db` (both ranks) and `hc`;
  - the rank-1 driver of research/hc-kernels-2026-10-30 (export check; exports compared when both runs recorded them);
  - the exact `inventory_check.ones()`;
  - [check_schedule.py](check_schedule.py) (CPU only);
  - arms `tptsxqckhc` / `tptsxqckhcb` in [arm_env.py](arm_env.py);
  - [suite.sh](suite.sh) waits (bounded) for MemAvailable to clear the start floor before each server.
- Raw runs: `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/prefill-draft-batch-runs-{s1g1,t1a,t1b,t1c}`, sha256
  verified, `/dev/shm` copies removed after each phase. Compact evidence is in `evidence/`. Evidence for s1 is under
  `evidence/g1/`: the two phases shared one run directory.
