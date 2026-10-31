# Four-card HC GEMV row split across each card pair (2026-10-30)

**Question.** On four cards, every card of a pipeline stage still computes the hyper-connection (HC) GEMVs of its stage
in full: per layer the low (320 x 10240 BF16, fused with the 4-row inject) and the gate (10240 x 320) of the attention
and FFN blocks, about 1.45 ms per card per half. Does an exact contiguous-row split (card c computes rows
[c*R/2, (c+1)*R/2), one direct exchange assembles the output on both cards) take time off both ranks, and does the
same split speed up four-card prompt reading?

**Answer.** **Yes, exactly. Fresh four-card lab servers at 65536, A/B/A/B on one binary: 92.77 / 92.53 -> 94.04 / 94.31 tok/s
(mean of medians 92.65 -> 94.18, +1.65%), every output equal to B19, hit cycle 8.84 -> 8.68 ms.** B is faster on 12/12
prompts in all four cross-pairs (1.012-1.022).
- The 121,854-token / 512-output request at 131072 reads its prompt 5.6 s faster (221.3 -> 215.7 s, -2.5%) and decodes
  at 88.56 -> 89.82 tok/s.
- Its output equals the 3+1 262K reference (same ids, MTP 418/511) in both arms.
- The flag is `OWNRT_TP_HC_SPLIT=low,gate,final,prefill`, default off, on build r1 `40388fc92c43` (the m2 tree plus
  [engine-hc-split.patch](engine-hc-split.patch); not applied to `engine/src`).

## In plain words

- **The split itself works as estimated.** Each card now reads half of every HC weight. On one card (shape probe
  traces) a half low takes 9.5 us instead of 15.4 us and a half gate 8.2 us instead of 14.2 us; per half, a card's busy
  time drops by 0.71 ms on rank 1 and 0.61 ms on rank 0.
- **The exchanges give most of it back.** Every split GEMV needs one more exchange before its consumer: 102 more per
  half on rank 1 (76 -> 178), 92 more on rank 0 (69 -> 161). Each costs about 4.5 us in the four-card half (1.1-1.6 us of
  its own stores, fences and flag, 1-2 us waiting for the peer, about 1 us of launch). Net: **-0.14 ms per half on
  rank 1 (8.675 -> 8.533 ms) and -0.175 ms on rank 0 (7.858 -> 7.683 ms)** in the rank harness.
- **Prompt reading also gets faster** when the split is on in batched prefill (the `prefill` token): -46 to -47 ms per
  1,024 prompt rows on both ranks (rank 1 -1.6%, rank 0 -2.7%), about 11.5 ms per 256-row chunk. The estimate was larger
  (about 35 ms per chunk); each split site there also adds one prefill exchange with its drain.
- **Every output is bit-identical** to the one-card engine and to the flag off: full state, tokens, draft buffers and
  tokens, rank 1's exported draft-input rows, both requests of the two-request case, at 128-row and 1,024-row prompts.

## The engine change ([engine-hc-split.patch](engine-hc-split.patch), default off)

Against the lab build m2 tree (`979462f7c` + [engine-fixed-cost-2.patch](../fixed-cost-2-2026-10-30/engine-fixed-cost-2.patch)),
8 files, private tree `/dev/shm/hcsplit-2026-10-30/tree` (the shared `engine/src` was not touched). Build r1
`40388fc92c43` ([build receipt](results/build-r1-build-receipt.json), [engine receipt](results/engine-receipt-40388fc92c43.json));
[verify_receipt.py](verify_receipt.py) confirms that 979462f7c + both patches reproduces all 269 compiled sources.

`OWNRT_TP_HC_SPLIT` (comma tokens; `1` = `low,gate,final`), four-card TP only (`OWNRT_TP_EXCHANGE=direct`, F32):
- `low`: `blk.*.hc.a.low`, `blk.*.hc.f.low`. The low+inject sibling fusion stays: the launch carries the card's 160 low
  rows plus the whole 4-row inject (replicated).
- `gate`: `blk.*.hc.a.gate`, `blk.*.hc.f.gate` (5,120 rows per card, still the `hcgate` two-rows-per-subgroup kernel).
- `final`: rank 1's `final.low` / `final.gate` (decode halves only).
- `prefill`: batched prefill runs the split sites too, and each card then stores only its rows of each split weight
  (-334 MB per card on rank 1, -301 MB on rank 0). Without it, the split launches read their rows from the whole,
  replicated weight at a row offset, and batched prefill runs those sites' full rows with no exchange, exactly as before.

How each blocker in the round-3 notes was handled:
- **`split_site` admitted only the p33 paths.** A separate HC branch in the TP transform (`rank.hpp`). Card c's launch
  gets `row_begin = c*R/2`, `row_count = R/2` and output `y#tp`, and one `tp_xgather` pair per site writes y on both
  cards. The HC exchanges take flag slots after every other exchange site, so the existing sites keep their m2 slots.
- **The HC low is fused with its inject.** Nothing to change: the fusion pairs the per-card launches, and `kopt::fused_gemv`
  partitions subgroups by matrix, so the half low and the whole inject share one launch with unchanged rows.
- **The gate's paired-rows kernel needs the row-range descriptor.** In whole-weight mode `kopt::Matrix::row0` moves the
  bound weight pointer by row0 rows on the host (`Multiply::run`, before any kernel is built; never captured by a kernel).
  `bf16_multi_static<2,4>` (gate), `<1,10>` (low) and the generic path then read exactly the bytes those rows read in
  the full launch. With `prefill`, the weights are row-sliced instead (`tp_runs`), which needs no offset. Either way the
  admission (`small_k` for the gate, `lowsel` for the low) selects the same kernel at half the rows.
- **The dump layout.** y itself is the one-card buffer (both halves exchanged in place). `y#tp` is skipped by the dump as
  every TP half buffer is, so the bitwise gate against one card reads the one-card layout unchanged.

Supporting changes:
- `exchange_layout::slots` 256 -> 512 (each control block 64 KiB): 178 decode slots on rank 1.
- The prefill flag slot base is `max(128, decode slots)` instead of 128, so prefill never zeroes a decode slot. With the
  flag off it is still 128.
- The HC gate+mix fusion (`OWNRT_FUSE_MIX`, closed and off) skips split gates.
- Host readbacks: no controller read touches an HC low/gate output, and no write moves. `final.mix` (the head input)
  is still written by its own site after the gate exchange, and `streams` is not touched.

## Gates

### Gate 1 (CPU plan check, smallest device smoke)

- [cpu_plan_check.py](cpu_plan_check.py) ([results](results/cpu-plan-check-r1.json)), `OWNRT_PLAN_ONLY=1` with the
  four-card transform, both ranks, flag off / `1` / `low,gate,final,prefill` / `low`:
  - 102 split sites on rank 1 (50 low, 50 gate, 2 final), 92 on rank 0;
  - card c rows [c*R/2, (c+1)*R/2), one exchange pair per site whose halves tile [0, R) exactly once;
  - HC slots 76..177 (rank 1) and 69..160 (rank 0), with the other sites' slots equal to flag off;
  - weights per card equal to flag off in whole-weight mode, and -334,233,600 / -301,465,600 bytes with `prefill`;
  - prefill slots at most 355 < 512.
- Smoke ([logs/s1.log](logs/s1.log)): rank 1, four cards, 16 prompt rows, 8 halves. rc 0, card 1 == card 0 (728
  buffers), 0 exchange timeouts, kernel log clean.

### Gate 2 (four-card rank harness; m2 flags `ep,rd,hk=1,tf=1` + `df=1` on rank 0)

Rank 1 on 23+47 and rank 0 on 23+27; one-card references on 43:00.0. 128 prompt rows, then 64 halves.
Compares: [logs/g2-compare.txt](logs/g2-compare.txt), [logs/g2x-compare.txt](logs/g2x-compare.txt),
[logs/t2-compare.txt](logs/t2-compare.txt).

| check | result |
| --- | --- |
| rank 1, token by token, flag on vs off (2 pairs) and vs one card | 1079/1079 buffers, 64 tokens, 192 exported draft-input rows equal |
| rank 1, batched + second request (`sp=64`), `1` and `low,gate,final,prefill`, vs off and vs one card | both requests 1079/1079, tokens, exports 192 + 128 equal, ones checker OK |
| rank 1, 1,024-row prompt (4 x 256-row chunks) + 1,024-row second request, both modes vs off | 1079/1079 twice, exports 1028 + 1028 equal |
| rank 0, `h`, `hmcn`, `m`, flag on vs off and vs one card | 1029/1029 + 71/71 draft buffers, draft tokens equal |
| rank 0, batched + `sp=64` and 1,024 + 1,024 rows, both modes | both requests 1029/1029 + 71/71, draft tokens, ones OK |
| card 1 vs card 0, every TP run | equal (728 / 670 buffers); 0 exchange timeouts |

The reset inventories (every standalone allocation hashed at the reset) differ only in scratch whose layout follows the
plan's buffer set:
- rank 0's `speculative-private-image` / `speculative-copy-table` also capture the new `y#tp` outputs; they are equal
  between the two flag-on modes;
- rank 1's prefill shadow packing, which has 4 more roles (`blk.*.hc.*#tp`) with `prefill`;
- the new `prefill:blk.*.hc.*#tp` shadows.

Batched TP against one card shows the same prefill-scratch differences with the flag off (control in g2x).

**Half wall times** (medians over halves 3..64; [results/t1-halves.json](results/t1-halves.json),
[results/g2-halves.json](results/g2-halves.json)), A/B order, quiet host (phase t1):

| rank | off | `1` (low, gate, final) | gate (+final) only | low only |
| --- | --- | --- | --- | --- |
| 1 | 8.732 / 8.677 / 8.674 | 8.549 / 8.526 / 8.525 | 8.626 / 8.603 | 8.634 / 8.627 |
| 0 (half, `h`) | 7.861 / 7.855 | 7.684 / 7.682 | 7.746 / 7.761 | 7.780 / 7.793 |

- Rank 1 -0.14 ms (-1.6%), rank 0 -0.175 ms (-2.2%); rank 0's draft step is unchanged (0.98-0.99 ms).
- Both parts pay, and they add up. The gate saves more, because its exchange waits less after the long kernel.
- Phase g2 (busier host, an archive job running) gave the same direction: rank 0 -0.165 ms in every pattern, rank 1
  -0.05 to -0.16 ms.

**Where the time goes** (diagnostics; [results/t1-exchange-stats.txt](results/t1-exchange-stats.txt), probe traces
[results/p1-r1-probe0-hs-half-sites.json](results/p1-r1-probe0-hs-half-sites.json),
[results/p1-r0-probe0-hs-half-sites.json](results/p1-r0-probe0-hs-half-sites.json)):
- One-card shape probe (`OWNRT_TP_SHAPE_PROBE`, site trace, never under TP), card 0's launches of the four-card plan:
  - busy time per half 8,068 -> 7,359 us on rank 1 (HC GEMVs -605 us, the HC act/mix after them -75 us) and
    6,983 -> 6,374 us on rank 0 (-549 / -72 us);
  - per launch, the low+inject 15.4 -> 9.5 us and the gate 14.2 -> 8.2 us (ratios 0.62 and 0.57). Card 1's probe matches
    card 0's to 4 us per half.
- Exchange statistics (`OWNRT_TP_EXCHANGE_STATS`, four cards). The new exchanges' own time is 1.07-1.15 us (low, 160
  values per card) and 1.62-1.66 us (gate, 5,120 values). Their waits are 1.0-2.2 us on card 0 and 0.7-1.6 us on card 1.
  Per half on rank 1, own time grows 0.157 -> 0.285 ms and wait 0.144 / 0.099 -> 0.334 / 0.177 ms; on rank 0,
  0.148 -> 0.265 and 0.084 / 0.103 -> 0.215 / 0.184 ms. With about 1 us of launch each, the 102 / 92 new exchanges
  cost about 0.45 ms per half against the 0.6 ms kernel saving.

**Prompt reading** (1,024-row prompt, 4 chunks of 256 rows; the second request after a reset, warm;
[results/t2-prompt-times.json](results/t2-prompt-times.json)):

| rank | off | `1` (prefill unchanged) | `low,gate,final,prefill` | change with `prefill` |
| --- | --- | --- | --- | --- |
| 1 | 2918.1 / 2923.2 ms | 2932.6 / 2942.2 ms | 2882.7 / 2865.6 ms | -46.5 ms (-1.6%) |
| 0 | 1669.8 / 1678.4 ms (prefill 1619.7 / 1627.8) | 1679.1 / 1682.6 | 1627.3 / 1629.0 (1577.1 / 1578.8) | -46.0 ms (-2.7%) |

The first requests show the same change (rank 1 3033.7 -> 2990.9 ms, rank 0 1817.8 -> 1775.8 ms).

## End gate (fresh four-card lab servers)

Tooling: [suite/](suite/), a copy of the fixed-cost-2 suite. Port 18177, `sc117-tp-svc-hs-*` units, and a
per-server receipt field in `suite.sh`.
- Both arms run build r1 ([receipt](results/engine-receipt-40388fc92c43.json)), so the A/B isolates the flag:
  - A = `fc2` (the m2 flag set: tptsxqckhcb + `OWNRT_DRAFT_FAST=1` + `OWNRT_TARGET_FAST=1`);
  - B = `hsp` = A + `OWNRT_TP_HC_SPLIT=low,gate,final,prefill`.
- Rank 0 runs on 23:00.0 + 27:00.0, rank 1 on 43:00.0 + 47:00.0.
- The lab adapter's `TP_KEYS` forwards `OWNRT_TP_HC_SPLIT`. Both rank processes of B r1 carried it
  ([suite/logs/rank-env-hsp-r1.txt](suite/logs/rank-env-hsp-r1.txt), from `/proc/<pid>/environ`), and the unit
  environments are in `suite/logs/arm-*-unit-env.txt`.
- Every server passed its 13-case startup batched-prefill gate (13/13) and the F32 self-tests and state oracles. Each
  then served the 12-prompt suite (one cold request each, 512 cap, greedy) and the 3,490-token TTFT request.
- The 131072 servers also served the 121,854-token / 512-output request.
- The kernel log stayed clean before and after every server and over the whole chain
  ([suite/logs/kernel-log-post-endgate.txt](suite/logs/kernel-log-post-endgate.txt)).

| server | median tok/s | mean | range | outputs | TTFT 3,490 | hit cycle | miss interval | rank 0 path | rank 1 path |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| A r1 (65536) | 92.77 | 93.09 | 89.69-97.95 | = B19 | 6.56 s | 8.839 ms | 16.89 ms | 8.837 | 8.795 |
| **B r1** | **94.04** | 94.46 | 91.13-99.20 | = B19 | 6.40 s | **8.683 ms** | 16.55 ms | 8.686 | 8.635 |
| A r2 | 92.53 | 93.01 | 89.50-97.91 | = B19 | 6.56 s | 8.831 ms | 16.87 ms | 8.840 | 8.805 |
| **B r2** | **94.31** | 94.65 | 90.95-99.42 | = B19 | 6.39 s | **8.673 ms** | 16.54 ms | 8.669 | 8.649 |
| A r4 (131072) | 92.68 | 93.03 | 89.54-97.83 | = B19 | 6.57 s | | | | |
| **B r4 (131072)** | **93.94** | 94.48 | 91.20-99.50 | = B19 | 6.42 s | | | | |

- Mean of medians at 65536: 92.648 -> 94.175 tok/s (**+1.65%**). Per prompt B/A is 1.0115-1.022 in every cross-pair,
  12/12 faster ([suite/results/suite/summary.json](suite/results/suite/summary.json)).
- At 131072: 92.68 -> 93.94 (+1.36%), 12/12 faster (1.009-1.019).
- Outputs: ids, sha256 and MTP guesses and hits equal to B19 on all six servers; 0 cached tokens.
- Hit cycle ([suite/results/hitcycle-endgate.json](suite/results/hitcycle-endgate.json); the 3,490-token request, 40 hits
  and 23 misses per server): -0.157 ms (-1.8%), and a miss -0.33 ms.
  - Rank 0's path 8.838 -> 8.678 ms: speculative half 7.861 -> 7.695, draft unchanged at 0.96-0.97.
  - Rank 1's path 8.800 -> 8.642 ms. Both stages moved by the same amount, so they are still within 0.05 ms.

**Long request at 131072** (121,854 prompt tokens, 512 output; [long_probe.py](suite/long_probe.py)):

| server | TTFT | decode tok/s (511 tokens) | output ids sha256 | = 3+1 262K reference | MTP hits |
| --- | ---: | ---: | --- | --- | --- |
| A r4 | 221.31 s | 88.56 | `bf1f0867d1bd` | yes | 418 / 511 |
| **B r4** | **215.69 s** | **89.82** | `bf1f0867d1bd` | yes | 418 / 511 |

**An attempted A at 131072 (server fc2-r3) halted in its first startup self-test.**
- Rank 0 failed with "TP card-1 release deadline". There was no device fault (kernel log clean), and nothing was
  retried.
- Cause: the ranks' bounded wait defaults to 60 s (`--wait-seconds`). A fresh server's first half JIT-compiles every
  kernel inside its enqueue loop: 52.9 s at 65536 with the fc2 flags, 61.4 s at 131072 (server fc2-r4). Rank 0's card-1
  worker counts its release deadline (`rank.hpp` `tp_issue_card1`) from the start of that loop.
- Fix (lab adapter copy only, both arms): 131072 servers pass `--wait-seconds 300` (`SC117_LAB_WAIT_SECONDS`, set by
  [run_arm_suite.sh](suite/run_arm_suite.sh)). It changes a deadline only. The 65536 servers ran without it.
- The halted server's directory is kept in the archive; fc2-r4 / hsp-r4 are fresh servers under new names.
- The 60 s default leaves only about 7 s of margin over the cold first half at 65536 too.

## Next lever

The new exchanges now cost about as much as the work they remove. Writing the half rows straight from the GEMV into
both cards' y, with the counter, flag and wait in the GEMV's last work-group (round-1 lever F4, exchange stores in the
producer's tail), would remove one launch and the separate copy per site. That is about 1-2 us of the 4.5 us, so
0.1-0.2 ms per half on each rank, and the same tail would serve the 69 / 76 existing exchange sites. The cost to check
first is one system-scope release fence per work-group: the gate launch has 640 work-groups, against at most 16 in the
exchange kernel.

## Files

- Engine change: [engine-hc-split.patch](engine-hc-split.patch) (apply after the fixed-cost-2 patch);
  [verify_receipt.py](verify_receipt.py).
- Harness (copies of fixed-cost-3's, with the `hs=TOKENS` extra): [run_phase.sh](run_phase.sh),
  [launch_phase.sh](launch_phase.sh), [compare.sh](compare.sh), [compare_driver.py](compare_driver.py),
  [halves.py](halves.py), [sites.py](sites.py), [klog.py](klog.py), [archive_runs.sh](archive_runs.sh), [drivers/](drivers/).
  New: [cpu_plan_check.py](cpu_plan_check.py), [xstats.py](xstats.py).
- End gate tooling: [suite/](suite/) (copy of fixed-cost-2's; arms `hs`, `hsp`; per-server receipts; `TP_KEYS` +
  `OWNRT_TP_HC_SPLIT`).
- Raw runs: `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/hc-split-gates-runs` (s1, g1, g2, p1, t1, t2; 3,655
  files, `.sha256` beside it). End gate: `.../2026-10-30/hc-split-endgate` (all seven server work directories,
  including the halted fc2-r3). Build r1 and its source tree: `.../2026-10-30/engine-builds/hc-split-r1`
  ([suite/archive_endgate.sh](suite/archive_endgate.sh)). The private tree `/dev/shm/hcsplit-2026-10-30/tree` and
  `build-r1` stay in place, because the receipt pins their paths.

## Incidents

- No device incident: kernel log clean before every phase, after every arm and server, and over the end-gate chain.
- Server fc2-r3-c131072 halted on the 60 s wait deadline (End gate, above). This was a host-side deadline; no GPU work
  was lost.
- The first CPU plan check refused to run: `native priority differs from declared --native-nice`, because the engine
  requires nice 19 and the check had been started at nice 10. It was rerun at nice 19.
- The end-gate chain waited 15 min for MemAvailable: another agent's 29 GB of `/dev/shm` runs, which were archived
  meanwhile.
