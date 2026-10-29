# Three exact rank-0 trims for the four-card service (2026-10-29)

**Question.** In the four-card TP2×PP2 service (74.07–74.80 tok/s, both head splits), rank 0 is the slower rank in 71%
of hit cycles, its 0.295 ms snapshot sits before every guessed half, and a miss costs 10.08 ms including a 0.55 ms
rollback ([miss-stall-2026-10-29](../miss-stall-2026-10-29/ANALYSIS.md)). Can three exact, opt-in trims take time off
rank 0: (1) the wait after the speculative snapshot copy, (2) row splits of the draft's large GEMVs across rank 0's two
cards, (3) the waits in the miss rollback?

**Answer.** Yes for all three, each bitwise equal to one card. On four fresh lab servers in A/B/A/B order (same binary, 65536), the
service with all three flags decodes **75.97 tok/s against 74.72** (pair means of the server medians, **1.017×**); each
flagged server is faster on **12/12 prompts** against each unflagged one (per-prompt 1.003–1.038×), and all 5,965 output
ids, hashes and MTP guesses equal B19 on all four servers.

| Step | Flag | Rank-0 harness, A/B/A/B in one phase | Exact |
|---|---|---|---|
| 1 snapshot | `OWNRT_SNAPSHOT_NOWAIT=1` | speculative half 9.626 / 9.630 → **9.416 / 9.415 ms (−0.21)** | 1029/1029, 71/71 |
| 2 draft GEMV | `OWNRT_DRAFT_GEMV_SPLIT=1` (qsa.qgate) | draft 1.164 / 1.165 → **1.117 / 1.110 ms (−0.05)** | 1029/1029, 71/71 |
| 3 rollback | `OWNRT_ROLLBACK_NOWAIT=1` | rollback 0.576 / 0.579 → **0.083 / 0.076 ms**; rollback + redo −0.49 ms per miss | 1029/1029, 71/71 |

Binary `3eb140d95695…` (build r4, [receipt](../../../engine/receipts/3eb140d95695.json)), built from `engine/src` into
`/dev/shm/engine-build-rank0-trims-20261029-r4`; commit `faf88166e`. Rank 0 on cards 23:00.0 + 27:00.0, context 65536,
B19 flags, TP Stage 2b layout with `OWNRT_DRAFT_HEAD_SPLIT=1` (the service's rank-0 flag set). Build r1 (`04d554479743`)
and r3 (`b187b9f0f41a`) are earlier versions of step 1 (section 1).

## Gates (all steps)

Rank-0 harness ([tp_rank0_driver.py](tp_rank0_driver.py), this folder's copy of the service-ready driver: the same
commands; it also times speculative halves, rollbacks and redos), context 65536, 1,100 prompt rows in 256-row chunks
(the 512-row raw ring wraps twice), then 16 decode steps; [run_phase.sh](run_phase.sh) / [run_phase2.sh](run_phase2.sh);
full dump compared bitwise ([evidence/](evidence/)). Patterns: `hmcn` = 4 hits, 4 completed misses, 4 cancelled at the
first launch, 8 redos; `x` = a timer publishes the miss 1–8 ms into each half (13 cancelled mid-half, 3 completed, 16
redos); `m` = 16 completed misses.

| Comparison (binary r4 unless noted) | Target | Draft | Draft tokens |
|---|---|---|---|
| one card, flags off, **vs previous binary `b7786ad42675`** | **1029/1029** | **71/71** | equal |
| TP + draft head split, flags off, **vs previous binary** | **1029/1029** | **71/71** | equal |
| TP, flags off, vs one card | 1029/1029 | 71/71 | equal |
| step 1: TP + nowait, `hmcn` / `x` vs one card (r3; r1 likewise) | 1029/1029 | 71/71 | equal |
| step 1: one card + nowait, `hmcn` vs one card (r1) | 1029/1029 | 71/71 | equal |
| step 2: TP + qgate split, with and without nowait, `hmcn`; with nowait `x` | 1029/1029 | 71/71 | equal |
| step 2: TP + nowait + split of qgate, hc.a.gate, hc.f.gate, `hmcn` | 1029/1029 | 71/71 | equal |
| step 3: TP + rollback-nowait alone, `hmcn` | 1029/1029 | 71/71 | equal |
| **all three flags, `hmcn` / `x` / `m`** | **1029/1029** | **71/71** | equal |

- The first device run of each new path was the smallest smoke (16 prompt rows, 4 steps, `hmcn`): r1 nowait, r3
  nowait, r3 GEMV split, r3 rollback-nowait, r4 nowait + rollback-nowait. All rc 0.
- Every TP run: card 1 equals card 0 on all 710 buffers both hold; 0 exchange timeouts and 0 aborts for the target's
  exchanges, the draft head split's and the GEMV split's (1,115 split draft steps per gate run, 2,230 waits per card);
  card-1 error 0. The kernel log was clean before every phase (24 h) and after every arm (0 xe/GuC/fault lines).

## 1. Snapshot: no host wait between the snapshot copy and the half (`OWNRT_SNAPSHOT_NOWAIT=1`)

**Where the 0.295 ms went.** Under TP, rank 0's speculative half ran, all on the host thread before the first kernel:
a position readback (half_step), the snapshot's drain, sticky-error and position readbacks (a second, identical position
read), the card-0 and card-1 static snapshot copies (31.4 MB on card 0), a drain in the bank rotation that waits for
both copies, the token_history readback, then two token uploads and four lookup-row uploads, each synchronous.

**Change** (`main.cpp` Engine, `strict_snapshot.hpp` begin, `rank.hpp` half_step; rank 0, prepared path):
- position and token_history are read once at the start of the half, while the queues are idle (the snapshot only reads
  them, so these are the bytes the old path read after it); the snapshot's own readbacks are skipped. The sticky error
  is checked after the half's final drain on both cards, before any reply, as packet188's `rank0_prepare=async` does;
- the snapshot copies are issued and the spare bank rotates without a drain (the static snapshot never reads or writes a
  recurrent bank; the rotation is host-only);
- the half's token and lookup rows are written to a pinned staging block per card and loaded by one ordered packet188
  `KioCopy` kernel per card (a byte copy), after the snapshot copy and before the half's kernels on each in-order queue.
- Snapshot bytes, restore and every device operation's order are unchanged. Unset, nothing is allocated.

**Build r1 found the trap.** r1 captured position and token_history by ordered device-to-pinned copies after the
snapshot and loaded each input with its own host-to-device queue copy. It saved only 0.04 ms (9.626 / 9.619 → 9.582 /
9.580): the speculative half's body grew by 0.21 ms, i.e. the host still waited for the snapshot copy inside those
queue copies. r3 removes both (reads before the snapshot, one copy kernel per card), and the copy then overlaps the
input preparation.

**Timing** (rank-0 harness, 64 speculative hits, medians of steps 3–64, A/B/A/B in one phase;
[results/s1-timing-r3.json](results/s1-timing-r3.json), [results/s1-timing-r1.json](results/s1-timing-r1.json)):

| Arm (r3) | Speculative half | Draft | Half + draft |
|---|---:|---:|---:|
| TP + draft head split (service), run 1 / 2 | 9.625 / 9.627 | 1.162 / 1.160 | 10.788 / 10.789 |
| + `OWNRT_SNAPSHOT_NOWAIT=1`, run 1 / 2 | **9.414 / 9.413** | 1.166 / 1.165 | **10.582 / 10.579** |

−0.21 ms per speculative half (−2.2%). Input preparation stays at 0.125 ms: it is CPU work (decoding the F32 embedding
and PLE rows), now overlapped with the 0.2 ms snapshot copy. Confirmed (non-speculative) halves are unchanged.

## 2. Draft GEMV row split (`OWNRT_DRAFT_GEMV_SPLIT=1`)

**Which sites qualify.** From the draft profile ([draft-split-2026-10-29](../draft-split-2026-10-29/RESULT.md) §1) and
the service's draft kernel choices (`draft-kernel-choices.json`):

| Site | µs (profiled) | Kernel in the service | Split? |
|---|---:|---|---|
| **qsa.qgate** (12,288 × 2,560 BF16) | 121 | production `mtp36::linear`, one row per subgroup | **yes**: one input row, plain output |
| attention output | 82 | p59 with the fused combine tail (read-modify-write of all four streams, inject gains) | no: card 1 would need three inputs (qsa.y, its stream rows, inject), three exchanges for about 31 µs |
| experts gate+up / down | 71 / 50 | FP8 routed experts (`mtp_fp8_v2`) | no: card 1 needs every expert's rows (1.3–2.6 GB) plus rewritten routes, four exchanges |
| merge.projected / embedding_projected | 51 / 35 | p59 (DenseBatch4 with the fused merge add) | no: two host-uploaded inputs and strided stream outputs; three exchanges for about 33 µs |
| hc.a.gate, hc.f.gate (10,240 × 64) | 25 / 25 | production `mtp36::linear` | eligible, measured below: not clearly above the exchange cost |

**Change** (`mtp.hpp` DraftRuntime; `--tp-replicate` rank 0, prepared commands): card 0 computes rows [0, 6144) with
the unchanged kernel and its own weight; card 1 holds a byte copy of rows [6144, 12288) (31.5 MB) and runs the same
kernel on them (a row's arithmetic never depends on the row count). Per draft step: exchange X1 sends the input row to
card 1 (card 1 answers with a ping word), each card computes its rows, exchange X2 stores card 1's rows into card 0's
output at row 6144 (card 0 answers with a ping). Card 0's output is then the one-card output, so the draft's 71 mutable
allocations and every later site are unchanged. Card 1's three commands are issued just before card 0's site, on every
draft step (head on or off). The split has its own control words (two slots per site), never reset; statistics in
`draft-final-state/draft-gemv-split-exchange.json`. `OWNRT_DRAFT_GEMV_SPLIT_SITES=label,...` selects other eligible
production one-row sites (refused otherwise).

**Timing** (64 speculative hits, A/B/A/B with step 1 on in every arm; [results/s2-timing-r4.json](results/s2-timing-r4.json)):

| Arm (r4, + nowait) | Draft | Half + draft |
|---|---:|---:|
| no GEMV split, run 1 / 2 | 1.164 / 1.165 | 10.585 / 10.590 |
| **qgate split**, run 1 / 2 | **1.117 / 1.110** | **10.546 / 10.536** |
| qgate + hc.a.gate + hc.f.gate, run 1 / 2 | 1.103 / 1.111 | 10.518 / 10.532 |

- qgate: −0.051 ms on the draft, against about 0.046 ms for half the site's unprofiled time, so the two exchanges cost
  only a few µs when card 1 is idle.
- The two HC gates add −0.014 / +0.001 ms: inconsistent and within run-to-run noise. Not adopted; the default stays
  qgate alone.

## 3. Rollback waits (`OWNRT_ROLLBACK_NOWAIT=1`)

**Where the 0.55 ms went.** `undo()` drained and read the sticky error; `restore()` drained, read the error again,
issued card 0's restore copy, then the card-1 restore drained first (waiting for card 0's copy) before issuing card 1's
copy, and the final drain waited for that. The two cards' 0.2 ms copies ran one after the other.

**Change** (`strict_snapshot.hpp` restore, `rank.hpp` undo/half_step; static snapshots): the card-0 and card-1 restore
copies are issued back to back with no drain between or after them (as the `banks-batch-overlap` miss choice already
skipped the last one), and the duplicate error readback is skipped (undo() has just drained and read it, and no device
work runs in between). With `OWNRT_SNAPSHOT_NOWAIT` also on, the confirmed redo right after its rollback skips its
position and token_history readbacks: the restore copies, ordered before the redo's work, wrote back exactly the bytes
the speculative half read before its snapshot. The redo and every later command are ordered after the copies on each
card's queue, and every host read drains first. Restored bytes unchanged.

**Timing** (64 completed misses each: speculative half with a wrong token, rollback, redo; A/B/A/B with steps 1 and 2 on;
[results/s3-timing-r4.json](results/s3-timing-r4.json)):

| Arm (r4, nowait + qgate split) | Speculative half | Rollback | Redo | Draft |
|---|---:|---:|---:|---:|
| run 1 / 2 | 9.427 / 9.429 | 0.576 / 0.579 | 9.327 / 9.330 | 1.118 / 1.121 |
| **+ rollback-nowait**, run 1 / 2 | 9.429 / 9.426 | **0.083 / 0.076** | 9.336 / 9.337 | 1.120 / 1.113 |

Rollback −0.50 ms; the redo grows by only 0.008 ms (the restore copies overlap its input preparation), so each miss is
about 0.49 ms shorter.

## 4. Suite at 65536: 75.97 against 74.72 tok/s (1.017×), outputs identical

Run as target-head-split-2026-10-29 section 6 ([suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh): the lab
service on 127.0.0.1:18171, one fresh transient unit per server (`sc117-tp-svc-r0t-arm-<name>-20261029`, `Restart=no`,
`KillMode=process`, no SIGKILL, `LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19), all four card locks held by
`sc117-tp-svc-r0t-locks-20261029`, `NEOReadDebugKeys=1 EnableDeferBacking=0`). Order tpts-r1, tptsx-r1, tpts-r2,
tptsx-r2, each a fresh server, never a retry. Binary `3eb140d95695` everywhere; `tpts` is the current four-card service
flag set (TP flags, `OWNRT_TARGET_HEAD_SPLIT=1`, `OWNRT_DRAFT_HEAD_SPLIT=1`), `tptsx` adds `OWNRT_SNAPSHOT_NOWAIT=1
OWNRT_DRAFT_GEMV_SPLIT=1 OWNRT_ROLLBACK_NOWAIT=1` ([arm_env.py](arm_env.py)). Each server: one cold request per frozen
prompt (512 cap, greedy), then one cold 3,490-token prompt (64-token cap). `sc117-lan` was not touched.

| Server | Median tok/s | Mean | Range | Outputs | TTFT, 3,490-token prompt | Its decode tok/s |
|---|---:|---:|---:|---|---:|---:|
| tpts-r1 | 74.95 | 75.05 | 71.99–78.94 | = B19, all 12 | 10,351 ms | 68.19 |
| **tptsx-r1** | **76.06** | 76.54 | 73.81–80.60 | = B19, all 12 | 10,125 ms | 68.05 |
| tpts-r2 | 74.49 | 74.87 | 72.07–79.00 | = B19, all 12 | 10,367 ms | 67.22 |
| **tptsx-r2** | **75.88** | 76.44 | 73.54–80.66 | = B19, all 12 | 10,146 ms | 70.25 |

- **Pair means:** tpts 74.72, tptsx **75.97** tok/s, **1.017×** ([results/suite/summary.json](results/suite/summary.json),
  [suite_compare.py](suite_compare.py)).
- **Per prompt** (median, range; prompts faster):

| Pair | Medians | Per prompt | Faster on |
|---|---:|---|---:|
| tptsx-r1 / tpts-r1 | 1.015 | 1.021 (1.003–1.027) | 12/12 |
| tptsx-r2 / tpts-r2 | 1.019 | 1.020 (1.015–1.032) | 12/12 |
| tptsx-r1 / tpts-r2 | 1.021 | 1.022 (1.007–1.038) | 12/12 |
| tptsx-r2 / tpts-r1 | 1.012 | 1.018 (1.009–1.030) | 12/12 |

- **Outputs:** all 5,965 ids, hashes and per-prompt MTP guesses and hits equal B19 on all four servers;
  `cached_tokens=0` everywhere; the long prompt's 64 output ids hash to `29426ae7332a…` on all four.
- **Gates:** on every server the startup gates passed (F32 self-tests, the pinned 4096 and 65536 state oracles, 13/13
  batched-prefill cases with no persistent-state difference), teardowns were clean (`terminal.json` passed) and the
  kernel log was clean before, after ready, after the suite and after the server. The tptsx ranks wrote
  `draft-gemv-split.json` (qsa.qgate, 6,144 / 6,144 rows).
- **TTFT** on the 3,490-token prompt drops 0.22 s (10.35 → 10.13 s): the prompt's 3,489 head-off draft replay steps
  each run the split qgate.

**The long request's trace** (positions 3,490–3,553, 40 hits and 23 misses in every server;
[results/suite/long-prompt-intervals.json](results/suite/long-prompt-intervals.json),
[results/suite/long-prompt-trace.json](results/suite/long-prompt-trace.json); medians, ms):

| Server | Hit interval | Miss interval | Rank 0 snapshot / rollback (host) | Rank-0 half total | Rank 0 ends after rank 1 by | Draft | Decode wall |
|---|---:|---:|---:|---:|---:|---:|---:|
| tpts-r1 | 10.80 | 21.07 | 0.295 / 0.552 | 9.70 | +0.17 | 1.118 | 924.0 |
| tptsx-r1 | 10.65 | **20.36** | **0.032 / 0.055** | **9.49** | **−0.08** | **1.070** | 925.8 |
| tpts-r2 | 10.97 | 21.09 | 0.295 / 0.551 | 9.70 | +0.26 | 1.119 | 937.2 |
| tptsx-r2 | 10.67 | **20.32** | **0.034 / 0.055** | **9.50** | **−0.08** | **1.069** | **896.7** |

- Misses are 0.7–0.8 ms shorter; rank 0's half plus draft now ends before rank 1's half in a typical hit cycle, so
  rank 1 (10.68 ms) sets the pace again.
- tptsx-r1's long request equals the unflagged ones only because of one rank-1 half of 35.7 ms at position 3551
  (12,298 minor page faults in rank 1's host enqueue loop; rank 1 runs no new code path). Without it the request is
  about 25 ms shorter, like tptsx-r2's.

Raw server directories (930 files, 333,787,709 B, sha256-verified):
`/mnt/raid-models/ownrt-experiment-archives/2026-10-29/rank0-trims-suite-20261029/`.

## Next

1. **Service:** the four-card service configuration can add the three flags (arm `tptsx` of [arm_env.py](arm_env.py),
   binary `3eb140d95695` or a later build with the same sources). Moving `sc117-lan` to four cards stays the owner's
   call; sessions and continuation are still refused under TP.
2. **Rank 1 sets the pace again** (10.68 ms against rank 0's draft plus speculative half of about 10.6 ms): the next
   decode lever is on rank 1, or on both stages together.
3. **Misses** still cost about 9.7 ms each (the redo of rank 0's 23 layers is a pure dependency).
4. Rank 0's input preparation (0.12 ms of CPU work decoding the F32 embedding and PLE rows, twice under TP) and the
   0.2 ms static snapshot copy kernel (31.4 MB at about 300 GB/s) are the remaining fixed costs before each rank-0 half.


## Files

- Engine (commit `faf88166e`): `main.cpp` (half-input staging, rotation without drain, `redo_known`),
  `strict_snapshot.hpp` (begin nowait, restore nowait), `rank.hpp` (half_step, undo), `mtp.hpp` (GEMV split); receipts
  [3eb140d95695](../../../engine/receipts/3eb140d95695.json), [b187b9f0f41a](../../../engine/receipts/b187b9f0f41a.json),
  [04d554479743](../../../engine/receipts/04d554479743.json).
- Lab: [run_phase.sh](run_phase.sh), [run_phase2.sh](run_phase2.sh) (adds `gsites=`), [tp_rank0_driver.py](tp_rank0_driver.py),
  [analyze.py](analyze.py), [collect_evidence.py](collect_evidence.py), [archive_runs.sh](archive_runs.sh),
  [make_receipt.py](make_receipt.py), [make_launch.py](make_launch.py), [arm_env.py](arm_env.py) (arm `tptsx`),
  [lab/](lab/) (the adapter passes the three keys to TP ranks, [diff](lab/adapter6_tp.py.vs-target-head-split.patch)),
  launch JSONs `rank0-launch-c65536-*.json`.
- Suite: [suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh), [suite_compare.py](suite_compare.py),
  [trace_summary.py](trace_summary.py), [results/suite/](results/suite/).
- Evidence: [evidence/](evidence/) (per run: summary, state hashes for gate runs, exchange and card-compare statistics),
  [results/](results/) (timings), [logs/](logs/) (phase logs, kernel-log checks, archive receipts). Raw run directories
  (sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/rank0-trims-runs-{s1,r3,r4s2,r4s3}/`.
