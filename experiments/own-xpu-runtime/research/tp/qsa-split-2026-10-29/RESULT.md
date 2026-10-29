# QSA split by KV group across each TP rank's two cards (Stage 3, 2026-10-29)

**Question.** In the four-card TP2×PP2 service (75.88–76.06 tok/s, arm `tptsx`), rank 1 sets the pace (about 10.68 ms per
half in service). Its 7 QSA layers (23, 27, …, 47) run fully replicated on both cards. Does splitting each QSA block by
KV group (the [direct-exchange](../direct-exchange-2026-10-28/RESULT.md) "Stage 3 design") take time off, exactly?

**Answer.** Yes, exactly, and the service gets faster. With `OWNRT_TP_QSA_SPLIT=1` both TP ranks split their QSA blocks: rank 1's
half drops from 10.43 to 10.23–10.28 ms (−0.18 ms; −0.23 on its service cards) and rank 0's speculative half from 9.43
to 9.25–9.26 ms. Each card also holds half the QSA KV cache: rank 1 plans **1.03 GB less per card** at 64K (30.42 GB),
which would leave 128K within the 30 GiB cap.
- **Suite at 65536, four fresh servers in A/B/A/B order, same binary:** **77.11 against 76.18 tok/s** (pair means of the
  server medians, **1.012×**). Each split server is faster on **12/12 prompts** against each control (per prompt
  1.003–1.030×). All 5,965 output ids, hashes and MTP guesses equal B19 on all four servers.
- Every gate is bitwise: rank 1 1079/1079 and rank 0 1029/1029 target + 71/71 draft against one card, and flag-off
  against the previous binary. 0 exchange timeouts. Kernel log clean throughout.
- Cost: the lab service's one-time startup gates take about 5 minutes longer (the state-dump assembler; section 5).

Binary `cb04951c3fb4…` (build r1, [receipt](../../../engine/receipts/cb04951c3fb4.json)), built from `engine/src` into
`/dev/shm/engine-build-qsa-split-20261029-r1`; engine commit `05909448c`. Context 65536, B19 flags, F32.

## 1. What QSA costs rank 1 today, and the projection (CPU only, before building)

[projection.py](projection.py) → [projection.json](projection.json), from the retained rank-1 per-site profile
(`decode-next2/profile-final.json`, 4096-row prompt, the restructured attention on) cross-checked against the B19 rank-0
profile (`pp4-review-2026-10-28/within-layer-sizing/evidence/`, same kernels; per-layer costs agree within 1–3 µs).
Rank 1 has **7** QSA layers at split 23 (rank 0 has 5: 3, 7, 11, 15, 19).

| Rank-1 QSA sites per half (both cards, replicated) | µs |
|---|---:|
| qgate GEMV (5 × Q6_K 12,288 × 2,560 at 482 GB/s, 2 × Q5_K) | 385.8 |
| k, v GEMVs (512 rows each) | 130.8 |
| prepare | 45.6 |
| attention tiles + combine | 274.2 |
| **splittable** | **836.4** |
| replicated: selection, indexer GEMV (iq+ik), pool, attention admit | 245.6 |
| **total** | **1,082** (about 10% of the half) |

Projected saving per rank-1 half, net of the 7 extra `qsa.y` exchanges (6.1 µs each): ideal 0.376 ms; central 0.223 ms at
the harness positions (qgate halved at the same bandwidth, the small GEMVs and prepare halved above a 5 µs fixed cost,
attention −25%: 130 → 65 work-groups stay within about one wave); low 0.133 ms (only the qgate, with a 5 µs fixed cost).
The central projection is above the 0.15 ms build threshold, so it was built.

## 2. What was built: `OWNRT_TP_QSA_SPLIT=1` (opt-in; TP ranks, both)

Card c owns KV head c and query heads [12c, 12c+12) (query head h reads KV head h/12); every head's arithmetic is unchanged.
- **Plan** (`rank.hpp`, the TP transform; needs `OWNRT_TP_EXCHANGE=direct`, F32, SC117 QSA geometry):
  - `qsa.qgate` computes rows [6144c, 6144c+6144) (12 heads × [256 q; 256 gate], one contiguous run), `qsa.k`/`qsa.v`
    rows [256c, 256c+256). Each card loads only those weight rows (TP row runs) and writes them compactly; the existing
    p33 dense Q6, dense-block and kopt kernels run them unchanged.
  - `qsa.prepare`, `qsa.pool`, `qsa.attention` run with `Launch::heads=12, key_heads=1`.
  - **KV cache:** `qsa.keys`/`qsa.values` are planned at [context][1][256] per card: each card holds only its KV head,
    half the cache.
  - The indexer (`iq`, `ik`, the index part of prepare), the raw ring and pooled keys and `qsa.select` stay replicated, so
    both cards attend over the same selected token ids.
  - Attention writes its 12 heads into `qsa.y#tp`; one direct exchange (`tp_xgather`, rows [3072c, 3072c+3072))
    assembles `qsa.y` on both cards before the unchanged (row-split) output projection. Exchanges per half: rank 1 69 →
    76, rank 0 64 → 69.
  - The dump reassembles the one-card layout of every compact buffer, the KV cache included (`head_split_layout`; the
    assembler now sizes a compact-allocated buffer from its layout). Prefill treats the KV cache as persistent state, as
    before; the compact q/gate/kn/k/v buffers use their compact extent as the shadow row stride.
  - Writes `qsa-split.json` (layers, halved KV buffers).
- **Kernels, parameterized, not forked:**
  - `ng::Shape` gains `qsa_group_flag` (256): with it, `heads` = this card's query heads (12 or 24) over heads/12 KV heads.
    Without it (every one-card shape) the Shape and argument bytes are unchanged.
  - Generic `prepare` (groups QH+KH+4), `pool` (KV row of KH·256), `attention_score/softmax/value` and `required_bytes`
    take the geometry from the shape (`kernels.hpp`); so does the host twin `p47ref::cpu_split`.
  - p49: `tiles_heads` and `combine_blocked` become templates on the KV-head count (`tiles_heads_kv<F32,KH>`,
    `combine_blocked_kv<F32,KH>`), dispatched from the shape. KH = 2 compiles to the previous constants. `admit` and
    `admit_fast` are geometry-free; `scratch_bytes` scales with the query heads.
  - Refusals: the adapter admits a split QSA shape only on the generic prepare/pool (implementation 0) and p49 attention
    (implementation 12), F32; p49 refuses it unless `OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1` (every other variant
    indexes the 24-head layout); the selection is never split.

## 3. Gates

**CPU unit test** ([qsa_unit_test.cpp](qsa_unit_test.cpp), [output](qsa_unit_test.out); OpenCL CPU device, no GPU
opened): **2,621 checks, 0 failures.**
- Generic prepare (1/2/4/7 rows, 5 positions) and pool (1/2/4/5 rows at 7 positions, one 256-row chunk): each half
  equals the full kernel's rows for its heads; the KV cache at every position; index query, raw and pooled replicated.
- Attention, 95 cases: n = 1, 2, 31, 32, 33, 63, 64, 65, 100, 300, 513, 1025, 2047–2051, 3000 selected ids; 1/2/4 rows;
  random, signed-zero and scaled (tied-score) inputs. Generic host attention (y and probabilities), `cpu_split`, and the
  production device passes (`admit_fast`/`admit` + `tiles_heads` + `combine_blocked`): y and every valid partial
  (258 floats per row, head and tile) bitwise equal to the full-geometry run. Negative control (card 1's heads over KV
  head 0): differs in all 73 cases with nonzero K/V.

**Device gates** (context 65536, 1,100 prompt rows in 256-row chunks so the 512-row raw ring wraps twice, then 16 decode
halves; rank 1 on 23:00.0 + 47:00.0, rank 0 on 23:00.0 + 27:00.0, one card on 23:00.0; [run_phase.sh](run_phase.sh),
[logs/q2-gate-compare.txt](logs/q2-gate-compare.txt)):

| Comparison (full dump, bitwise) | Rank 1 | Rank 0 |
|---|---|---|
| one card, new binary vs previous binary `3eb140d95695` | **1079/1079** | **1029/1029, 71/71** |
| TP flags off (service set), new binary vs previous binary one card | 1079/1079 | 1029/1029, 71/71 |
| **TP + `OWNRT_TP_QSA_SPLIT=1` vs one card**, batched prompt | **1079/1079** | **1029/1029, 71/71** (`hmcn`) |
| TP + split, prompt read token by token (rank 1) / timed cancels `x` and all-miss `m` (rank 0) | 1079/1079 | 1029/1029, 71/71 each |

- All 16 decode tokens and the draft tokens are equal in every comparison. The reassembled KV cache, compact q, gate,
  kn, k, v and qgate rows are among the compared buffers. Card 1 equals card 0 on every buffer both hold in full (728
  on rank 1, 670 on rank 0).
- Speculation events per rank-0 run: `hmcn` 4 hits, 4 misses, 4 cancelled, 8 redos; `x` 5 misses, 11 cancelled, 16
  redos; `m` 16 misses, 16 redos.
- The first device run was the smallest smoke (16 prompt rows in one 16-row chunk, 4 decode halves; `q1-smoke`): rank 1
  1079/1079 and rank 0 1029/1029 + 71/71 against one card, first attempt.
- **0 exchange timeouts and 0 aborts** in 274,060 waits over all runs. Kernel log clean before each phase (24 h) and
  after every arm. No incidents.

**Per-card plan at 65536** (CPU plan probes, [evidence/probes/](evidence/probes/); cap 32,212,254,720 B):

| Rank | TP today (flag off) | + QSA split | Change |
|---|---:|---:|---:|
| rank 1 | 31,456,652,612 | **30,423,549,252** | −1,033,103,360 (KV −939.5 MB, weights −93.7 MB) |
| rank 0 | 25,929,055,244 | **25,208,287,244** | −720,768,000 |

- The plans are exactly linear in context (rank 0's probe at 262,144 equals the 32K→64K slope to the byte). **Rank 1 at
  131,072 projects to 31,421,793,604 B per card with the split (fits, 790 MB under the cap) against 33,394,421,060
  without (does not fit).** It cannot be probed directly: 131,072 is not an admitted context for this split-23 draft
  configuration (admitted: 4096, 32768, 65536, 262144), and the one-card plan check before the TP transform would refuse
  rank 1 there (34.1 GB). Both would need changing before a 128K four-card service.
- Rank 0 fits at 262,144 with the split: 27,850,698,764 B per card (30,584,732,684 without), plus the draft on card 0.

## 4. Speed: rank harnesses, A/B/A/B in one phase

Same binary and settings as the gates, 48 decode halves (rank 1, medians of halves 3–48) and 64 speculative hits (rank 0,
medians of steps 3–64) ([results/q3-timing-rank1.json](results/q3-timing-rank1.json),
[results/q3-timing-rank0.json](results/q3-timing-rank0.json)); all tokens equal, 0 timeouts:

| Rank, cards | Service flags (run 1 / 2) | + `OWNRT_TP_QSA_SPLIT=1` (run 1 / 2) | Change |
|---|---:|---:|---:|
| rank 1 half, 23 + 47 | 10.434 / 10.424 | **10.230 / 10.277** | −0.18 ms (−1.7%) |
| rank 1 half, 43 + 47 (its service cards) | 10.440 | **10.209** | −0.23 ms |
| rank 0 speculative half, 23 + 27 | 9.428 / 9.428 | **9.260 / 9.248** | −0.17 ms |
| rank 0 half + draft | 10.546 / 10.536 | **10.379 / 10.357** | −0.17 ms |

Within the projection (central 0.22 ms, low 0.13 ms). Both stages gain about the same, so rank 1 still sets the pace by
about the same margin.

## 5. Suite at 65536

Run as rank0-trims-2026-10-29 section 4 ([suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh): the lab service
on 127.0.0.1:18171, one fresh transient unit per server (`sc117-tp-svc-qsa-arm-<name>-20261029`, `Restart=no`,
`KillMode=process`, no SIGKILL, `LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19), all four card locks held by
`sc117-tp-svc-qsa-locks-20261029`, `NEOReadDebugKeys=1 EnableDeferBacking=0`). Order tptsx-r1, tptsxq-r1, tptsx-r2,
tptsxq-r2, each a fresh server, never a retry. Binary `cb04951c3fb4` everywhere. `tptsx` is the current four-card
service flag set; `tptsxq` adds `OWNRT_TP_QSA_SPLIT=1` ([arm_env.py](arm_env.py)). Each server: one cold request per
frozen prompt (512 cap, greedy), then one cold 3,490-token prompt (64-token cap). `sc117-lan` was not touched.

| Server | Median tok/s | Mean | Range | Outputs | Ready after | TTFT, 3,490-token prompt | Its decode tok/s |
|---|---:|---:|---:|---|---:|---:|---:|
| tptsx-r1 | 76.20 | 76.35 | 73.67–80.40 | = B19, all 12 | 732 s | 10,146 ms | 69.26 |
| **tptsxq-r1** | **76.91** | 77.39 | 74.20–81.30 | = B19, all 12 | 1,039 s | **9,842 ms** | 71.39 |
| tptsx-r2 | 76.17 | 76.60 | 73.72–80.71 | = B19, all 12 | 728 s | 10,164 ms | 69.97 |
| **tptsxq-r2** | **77.30** | 77.50 | 74.79–81.14 | = B19, all 12 | 1,043 s | **9,830 ms** | 70.06 |

- **Pair means:** tptsx 76.18, tptsxq **77.11** tok/s, **1.012×** ([results/suite/summary.json](results/suite/summary.json),
  [suite_compare.py](suite_compare.py)).
- **Per prompt** (median, range; prompts faster):

| Pair | Medians | Per prompt | Faster on |
|---|---:|---|---:|
| tptsxq-r1 / tptsx-r1 | 1.009 | 1.012 (1.006–1.030) | 12/12 |
| tptsxq-r2 / tptsx-r2 | 1.015 | 1.013 (1.005–1.017) | 12/12 |
| tptsxq-r1 / tptsx-r2 | 1.010 | 1.009 (1.003–1.019) | 12/12 |
| tptsxq-r2 / tptsx-r1 | 1.014 | 1.015 (1.009–1.027) | 12/12 |

- **Outputs:** all 5,965 ids, hashes and per-prompt MTP guesses and hits equal B19 on all four servers;
  `cached_tokens=0` everywhere; the long prompt's 64 output ids hash to `29426ae7332a…` on all four.
- **Gates:** on every server the startup gates passed: F32 self-tests, the pinned 4096 and 65536 state oracles (the split
  KV cache reassembled), and 13/13 batched-prefill cases with no persistent-state difference. Teardowns were clean
  (`terminal.json` passed). The kernel log was clean before, after ready, after the suite and after each server. No
  rank-1 or rank-0 half exceeded 13 minor faults.
- **TTFT** on the 3,490-token prompt drops about 0.32 s (10.15 → 9.84 s): batched prefill runs the split QSA sites too.
- **Startup is about 5 minutes slower** (ready after 1,039 / 1,043 s against 732 / 728 s). Load and self-tests are not
  slower; all of it is in the one-time batched-prefill gate, which dumps full state on both ranks for each of its cases.
  The dump assembler (`state_dump` in `rank.hpp`) checks coverage element by element. With the split it also walks the
  per-position KV runs: 65,536 per buffer and card, 14 KV buffers on rank 1, about 470 M element checks per dump.
  Decode and serving are unaffected. Fix in Next.

**The long request's trace** (positions 3,490–3,553; [results/suite/long-prompt-trace.json](results/suite/long-prompt-trace.json);
medians, ms):

| Server | Rank-1 half | Rank-0 speculative half | Rank-0 redo | Draft | Rank 0 ends after rank 1 by | Decode wall |
|---|---:|---:|---:|---:|---:|---:|
| tptsx-r1 | 10.667 | 9.428 | 9.397 | 1.069 | −0.068 | 909.6 |
| **tptsxq-r1** | **10.422** | **9.196** | **9.174** | 1.068 | −0.052 | **882.5** |
| tptsx-r2 | 10.662 | 9.446 | 9.413 | 1.071 | −0.068 | 900.4 |
| **tptsxq-r2** | **10.435** | **9.201** | **9.179** | 1.068 | +0.023 | 899.2 |

- In service, rank 1's half is 0.24 ms shorter and rank 0's 0.23 ms shorter (redo too, so each miss is shorter). The
  two stages stay balanced: rank 1 still finishes last by a few hundredths of a millisecond in a typical hit cycle.

Raw server directories (936 files, 335,386,397 B, sha256-verified):
`/mnt/raid-models/ownrt-experiment-archives/2026-10-29/qsa-split-suite-20261029/`.

## 6. Side analysis: the 35.7 ms rank-1 half with 12,298 page faults (CPU only, retained traces)

[fault_burst.py](fault_burst.py) → [results/fault-burst.json](results/fault-burst.json), over every retained per-half row
of the four four-card suites of 2026-10-29 (14 servers; the services retain the per-half rows of the last request, the
3,490-token prompt: 2,142 halves with fault counters).

**What the trace shows.** One burst in 2,142 halves: rank0-trims `tptsx-r1`, request 40, rank 1, position 3551: half 35.71
ms (median 10.66), enqueue loop 32.85 ms (median 6.31), device wait only 2.57 ms (the cards waited on the host),
**12,298 minor faults, 0 major** (48.0 MiB of 4 KiB pages; median 6 per half), 177 voluntary context switches (median
109). Every other half of every server has at most 12 minor faults.
- **Not** a capacity re-prepare: those were at positions 3520 and 3552 (8 and 5 faults).
- **Not** host-wide at that moment: rank 0 (a separate process) had 2–7 faults in its halves at positions 3549–3552.
- **Not** swap (no swap device; 0 major faults) and **not** NUMA hinting (one node, `numa_balancing=0`).
- **Not** the rank-0 trims: rank 1 runs none of their code, and the other `tptsx` server never exceeded 9.
- **TP-specific background:** every TP server's halves carry 6–12 minor faults; the one-card (`two`) servers carry
  exactly **0**. The only host path a TP half runs that a one-card half does not is the card-1 submission thread:
  `TpWorker` (`rank.hpp`) creates a new `std::thread` in every half and joins it at the end. Each half therefore starts a
  thread on a recycled stack, TLS block and malloc arena; glibc recycles them, but a trimmed arena or evicted stack-cache
  entry is re-faulted page by page. 48 MiB is not any engine buffer of rank 1's half (its host allocations per half are
  kilobytes).
- **What it cannot show.** The counter is `getrusage(RUSAGE_SELF)` over the half, so it does not say which thread or
  which mapping faulted. Rank 1's `RUSAGE_THREAD` fault delta is measured but not written, and the worker thread is not
  measured. The host also runs heavy background reclaim and compaction (since boot: 16.8 G pages stolen by kswapd, 8.2 G
  file refaults, 5.7 G pages migrated, 9.8 M kcompactd wakeups; MGLRU on; THP `madvise`). So reclaim or migration of
  rank 1's 117 MB of mapped library pages (RssFile) is the alternative explanation, and the trace cannot rule it out.

**Proposed fix (engine only; no host memory, swap or page-cache setting):**
1. **Persistent card-1 submission thread per TP process.** Start `TpWorker`'s thread once at `prepare_commands`. Park it
   on a generation word, bounded: yield, then a futex wait with the existing `wait_seconds` deadline. Per half, publish
   (generation, fixture, gated) and keep `allow`/`stop`/`finish` unchanged: the same release index, cancellation bound
   and deadline semantics, and the same issue loop over `issue_sites[i].commands`. Exit on FINISH. This removes the
   per-half thread creation, stack, TLS and arena churn. It also saves the thread start and join (tens of µs) on every
   half of both ranks. Gate: the rank harnesses (`hmcn`/`x`/`m` on rank 0, batched rank 1) bitwise, then the TP
   per-half fault baseline must drop from 6–12 to the one-card 0.
2. **Attribution for the next burst** (diagnostic fields, no behaviour change): write the half thread's `RUSAGE_THREAD`
   minor faults (already collected) and the worker thread's own delta. On a half with more than 1,000 process faults,
   also write `/proc/self/status` RssAnon/RssFile/RssShmem after the reply, outside the timed window. Anonymous growth
   then means allocator/thread churn; file-backed re-faults mean reclaim of library pages.
Neither was implemented here: (1) touches the cancellation handshake and needs its own gated build, and (2) changes the
binary under this suite.

## Next

1. **Service:** the four-card service configuration can add `OWNRT_TP_QSA_SPLIT=1` (arm `tptsxq` of
   [arm_env.py](arm_env.py), binary `cb04951c3fb4` or a later build with the same sources). Moving `sc117-lan` to four
   cards stays the owner's call; sessions and continuation are still refused under TP.
2. **Startup gate time:** make the dump assembler O(runs) (sort each card's runs, check that they are disjoint and cover
   the buffer by intervals, keep the memcpy per run) or give the KV cache a strided layout entry. That removes the extra
   5 minutes of the batched-prefill gate. It is a dump-only change, gated by the same bitwise dump comparisons.
3. **128K on four cards:** the per-card plan now fits (31.42 GB). Two refusals stand in the way, both outside the
   kernels: the split-23 draft admits contexts 4096/32768/65536/262144 only, and the one-card plan check before the TP
   transform refuses rank 1 above 64K. Make the TP rank admit by its per-card plan (`write_tp_plan`), then probe and gate
   131072 (and 262144 on rank 0, which already fits).
4. **Decode, both stages now near 10.4 ms:** the next equal-on-both-stages levers are the remaining replicated work. Per
   rank-1 half that is about 0.25 ms of QSA selection/indexer/pool, plus the HC low/gate GEMVs (about 1.5 ms per half on
   rank 0's profile, replicated on both cards). The persistent card-1 submission thread (section 6) also removes the
   per-half thread start on both ranks.

## Files

- Engine (commit `05909448c`): `kernels.hpp` (`qsa_group_flag`, generic QSA geometry), `p49_qsa_kernel.hpp`
  (`tiles_heads_kv`, `combine_blocked_kv`, scratch), `p49_qsa_submit.{cpp,hpp}` (refusal, scratch bytes),
  `p49_qsa_reference.hpp` (host twin), `adapter.cpp` (shape flag and refusals), `main.cpp` (`prepare_site` geometry),
  `rank.hpp` (`OWNRT_TP_QSA_SPLIT` transform, halved KV buffers, layouts, dump assembly); receipt
  [cb04951c3fb4](../../../engine/receipts/cb04951c3fb4.json).
- Lab (copies of rank0-trims-2026-10-29's tooling): [run_phase.sh](run_phase.sh) (extra `qs`), [arm_env.py](arm_env.py)
  (arm `tptsxq`), [lab/](lab/) (the adapter passes `OWNRT_TP_QSA_SPLIT` to TP ranks), [plan_probe.py](plan_probe.py),
  [make_launch.py](make_launch.py), [analyze.py](analyze.py), [analyze_rank1.py](analyze_rank1.py),
  [collect_evidence.py](collect_evidence.py), [archive_runs.sh](archive_runs.sh), launch JSONs.
- Suite: [suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh), [suite_compare.py](suite_compare.py),
  [trace_summary.py](trace_summary.py), [results/suite/](results/suite/).
- Evidence: [evidence/](evidence/) (per run: summary, state hashes for gate runs, exchange, split and card-compare
  statistics; CPU plan probes), [results/](results/), [logs/](logs/). Raw run directories (sha256-verified):
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/qsa-split-runs-{q1,q2,q3}/`.
