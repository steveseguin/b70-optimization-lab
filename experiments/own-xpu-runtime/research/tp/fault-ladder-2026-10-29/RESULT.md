# The TP page-fault ladder: libsycl's fast kernel cache thrashes in a two-card context (2026-10-29)

**Question.** In two-card TP processes, host page-fault bursts in the submission loops double in size (about 100 → 6,147
pages, ≈ one 24-byte record per submission per card) and cause 30–50 ms rank halves. One-card processes have none
([persistent-thread section 3](../persistent-thread-2026-10-29/RESULT.md)). What grows, who owns it, and can it be removed
exactly?

**Answer.** It is a defect in the SYCL runtime (`libsycl.so.9`, oneAPI DPC++ 2026.0.0.20260331, still present at intel/llvm
HEAD), triggered by the engine's one shared SYCL context for both cards. One engine-side change removes it exactly:
`OWNRT_TP_CARD_CONTEXT=1` (opt-in), one SYCL context per card, each over the same native Level Zero context.
- **Owner** (host-only `LD_PRELOAD` tracer, backtraces): every burst half has a `malloc` of exactly 24·2^k bytes
  (786,432 / 1,572,864 / 3,145,728 / 6,291,456) on **both** submission threads. The allocation comes from
  `sycl::detail::KernelProgramCache::saveKernel` (+0x26aec4) ← `ProgramManager::getOrCreateKernel` ← `enqueueImpKernel` ←
  `queue_impl::submit_kernel_scheduler_bypass` ← `handler::finalize` ← `queue::submit_with_event_impl` ←
  `ownrt::BoundSyclSubmission` ← `ownrt::Device::issue` (main thread / `TpWorker`). The burst is the copy of the old
  contents: half the new block. One card: no `saveKernel` allocation after the first half.
- **Mechanism** (disassembly of 2026.0 + DPC++ source):
  - `saveKernel` appends `{string_view name, device}` (24 B) to `MProgramToFastKernelCacheKeyMap[program]`. Nothing trims
    it while the program lives: one vector per program per card.
  - It then calls `MFastKernelCache.try_emplace(name, FastKernelSubcacheWrapper(subcache, ctx))`. When the name is already
    cached in this context, the temporary wrapper is destroyed, and its destructor erases **every** subcache entry of this
    context, the other card's included.
  - So in one context with two devices, each card evicts the other's entry for every shared kernel. Nearly every
    submission misses the fast lookup, takes the slow path and appends a record.
  - It is unbounded: in service each rank's RSS grew **+217 to +395 MB per ~100 s** of decode.
- **Fix:** each card gets its own SYCL context, and each context holds both devices over the same native L0 context. The
  ze context, peer access and the context device list (UR v2's P2P residency) are unchanged. Each card's cache only ever
  sees its own device. `peer_copy` / `peer_wait` (cross-queue SYCL events, unused with `OWNRT_TP_EXCHANGE=direct`) are
  refused with the flag.
- **Faults:**
  - Suite, every decode half of both ranks: **81K / 81K / 83K / 74K → 0 / 0 / 0 / 0**.
  - Token-by-token rank-1 harness: 14 bursts and 14,569 faults → 1 / 921. One card: 1 / 2,255. The one remaining burst
    is the first decode half (lazy kernel loads), as on one card.
- **Suite at 65536** (four fresh servers A/B/A/B, same binary):
  - **77.17 → 78.46 tok/s (1.0167×)**, 12/12 prompts faster in all four cross-pairs.
  - **Full request time 0.983×** (12/12 shorter).
  - **Max rank half 31–42 ms → 12.2–13.9 ms.**
  - All 5,965 outputs equal B19 on all four servers.
- All gates are bitwise (rank 1 1079/1079 ×8; rank 0 1029/1029 + 71/71 ×9 incl. hit/miss/cancel). Flag-off equals the
  previous binary. 0 exchange timeouts. Kernel log clean throughout. `sc117-lan` not touched.

Binary `5921bb96f630…` (build r1, [receipt](../../../engine/receipts/5921bb96f630.json)), built from `engine/src` into
`/dev/shm/engine-build-fault-ladder-20261029-r1`; engine commit `9d19335fa` (`single_device.cpp` only). Previous binary
`1c667aea0690`. Context 65536, B19 flags, F32.

## 1. Finding the allocation (CPU-side tooling only)

- [tracer/alloc_trace.c](tracer/alloc_trace.c), an `LD_PRELOAD` shim:
  - It is active only in the `sc117-engine` process; the [lab driver copy](tp_rank1_driver.py) sets it for the engine
    alone and also records each call's CLOCK_MONOTONIC times.
  - It logs malloc/calloc/realloc/aligned/mmap of 256 KiB or more, plus frees of logged blocks, with `backtrace()` frames
    and the thread's minor-fault count. glibc's `__libc_*` allocator is used unchanged.
  - [symbolize.py](tracer/symbolize.py) resolves frames through the saved `/proc/self/maps`;
    [correlate.py](tracer/correlate.py) maps every half to its allocations.
- Runs, rank 1 on 23+47, 1,100 prompt rows token by token + 16 decode halves (the `g-r1-tptqp-tbt` harness without `pt`):
  - Smoke first (`f1`).
  - Then `f2`, binary 1c667aea0690: [results/trace/f2-tp-bursts.json](results/trace/f2-tp-bursts.json) and
    [f2-tp-alloc-groups.json](results/trace/f2-tp-alloc-groups.json).

| Half (TP, flag off) | Process faults (main / card 1) | Logged allocations in the half |
|---|---|---|
| 114, 147, 164, 190 | 197–200 (98–101 / 99–100) | 786,432 B on the main thread **and** on that half's card-1 thread |
| 231, 293, 323, 378 | 390–391 | 1,572,864 B on both |
| 448, 595, 656, 760 | 774–776 | 3,145,728 B on both |
| 903 | 1,543 (772 / 771) | 6,291,456 B on both |

- Each burst is half the new block. That is `std::vector` growth copying 2^k old 24-byte records: 24·2^14 B = 96 pages,
  where 98–101 were measured.
- Each size recurs about four times because each program (kernel family) has its own vector per card. Doubling times
  double (114 → 231 → 448 → 903), as for monotonic growth at about 290 records per half per vector.
- A few halves get a reallocation with 3–8 faults: freed blocks were reused.
- One card (`t-r1-one-trace`): 0 `saveKernel` allocations after the first half. TP: 46 call-stack groups, all `saveKernel`.
- [fast_cache_unit_test.cpp](fast_cache_unit_test.cpp) ([output](fast_cache_unit_test.out)): OpenCL CPU device split into
  two sub-devices, no GPU opened. One kernel is submitted alternately to two in-order queues; the result is the
  steady-state heap slope after warm-up.

| Form | Heap growth per submission | Host time per submission |
|---|---:|---:|
| one context, both devices, two queues (today's TP group) | **40.37 B** | 8,953 ns |
| one context per queue, each with both devices (the fix) | **0.06 B** | 7,490 ns |
| one queue alone | 0.11 B | 7,852 ns |

  4/4 checks pass; results are equal in every form.

## 2. What was built (opt-in; default paths unchanged)

`OWNRT_TP_CARD_CONTEXT=1` in `single_device.cpp` (`make_sycl_device_group`, `SharedGroup`, the group constructor of
`SyclDevice`):
- It creates one `sycl::make_context<level_zero>({native, {both devices}, keep})` per member, and each `SyclDevice` uses its
  own. Allocations, frees and queues follow the card's context (as before, through its queue).
- Without the flag one shared context is made, exactly as before.
- The label becomes `…:shared-native-card-context` (teardown `receipt.json`); the drivers record `OWNRT_TP_CARD_CONTEXT` in
  `tp_env`.
- `peer_copy` / `peer_wait` throw with the flag. Their `depends_on` would become a cross-context SYCL dependency, a
  scheduler path the gates do not cover. The direct exchange uses neither.
- Lab: the [adapter](lab/adapter6_tp.py) passes `OWNRT_TP_CARD_CONTEXT` to TP ranks; [arm_env.py](arm_env.py) arm `tptsxqc`
  = `tptsxq` + the flag; [run_phase.sh](run_phase.sh) extras `cc` and `trace`.

Rejected: one SYCL context per card with only its own device. UR L0 v2 makes device allocations resident on the
context's P2P devices, and the direct exchange stores into peer memory, so that variant risks a GPU page fault. Per-card
kernel bundles would be a new per-submission path (`tryGetKernel` builds a `kernel_impl` each time).

## 3. Gates (all bitwise; [logs/c2-gate-r1-compare.txt](logs/c2-gate-r1-compare.txt), [logs/c3-gate-r0-compare.txt](logs/c3-gate-r0-compare.txt))

Context 65536; 1,100 prompt rows (256-row chunks, or token by token for `tbt`), then 16 decode halves. Rank 1 on
23:00.0 + 47:00.0, rank 0 on 23:00.0 + 27:00.0, one card on 23:00.0. First device run of the new path: the smallest smoke
(`c1`, 16 rows, 4 halves): rank 1 1079/1079, rank 0 1029/1029 + 71/71.

| Comparison | Rank 1 | Rank 0 (target, draft) |
|---|---|---|
| one card, new vs previous binary | 1079/1079 | 1029/1029, 71/71 |
| TP flags off (`tptsxq`), new binary vs previous one card / vs new one card | 1079/1079 ×2 | 1029/1029, 71/71 ×2 |
| **+ `OWNRT_TP_CARD_CONTEXT=1` vs one card / vs previous one card** (rank 0 `hmcn`) | **1079/1079 ×2** | **1029/1029, 71/71 ×2** |
| + flag, prompt token by token (traced) vs one card | 1079/1079 | — |
| flag off token by token (traced); one card token by token (traced) vs one card | 1079/1079 ×2 | — |
| + flag, timed cancels `x` / all-miss `m` vs one card with the same pattern, and vs `hmcn` | — | 1029/1029, 71/71 ×4 |

- All decode tokens and draft tokens are equal. Card 1 equals card 0 on every buffer both hold (728 / 670) in every TP run.
- **0 exchange timeouts / aborts.**
- Speculation events: `hmcn` 4 hits, 4 misses, 4 cancelled, 8 redos; `x` 7 misses + 9 cancelled (one card 11 + 5);
  `m` 16 misses; 16 redos each.
- Kernel log clean before each phase (24 h) and after every arm.

**Faults** ([results/c2-rank1-faults.json](results/c2-rank1-faults.json), [results/c3-rank0-faults.json](results/c3-rank0-faults.json)),
token-by-token rank 1, same binary, 1,115 halves after the first:

| Run | Faults | Bursts > 150 | Median / max per half | Host enqueue loop, prompt / decode halves (median ms) |
|---|---:|---:|---|---|
| flag off | 14,569 | 14 | 5 / 1,542 | 6.84 / 6.95 |
| **flag on** | **921** | **1** (first decode half, 525) | **0** / 525 | **4.87 / 5.16** |
| one card | 2,255 | 1 (first decode half, 2,012) | 0 / 2,012 | 3.78 / 3.79 |

Batched decode halves: flag on 0 faults (= one card), flag off 86. Rank-0 gates: 0 faults in every decode half (both forms,
short runs).

## 4. Rank harness timing, A/B/A/B in one phase ([results/c4-timing-rank1.json](results/c4-timing-rank1.json), [c4-timing-rank0.json](results/c4-timing-rank0.json))

| | Flag off (run 1 / 2) | + flag (run 1 / 2) |
|---|---:|---:|
| rank 1 half (48 halves, median of 3..48), 23 + 47 | 10.209 / 10.240 | 10.193 / 10.190 |
| rank 0 speculative half (64 hits), 23 + 27 | 9.240 / 9.251 | 9.241 / 9.244 |
| host enqueue loop, rank 1 / rank 0 (median ms) | 6.17, 6.26 / 5.98, 5.93 | **4.78, 4.84 / 4.55, 4.61** |
| faults in timed halves, rank 1 / rank 0 | 305, 290 / 54, 58 | **0, 0 / 0, 0** |

Per-card contexts cost no device time. The host submission loop is about 1.4 ms shorter per half: the slow lookup is gone.

## 5. Suite at 65536

Run as persistent-thread section 5 ([suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh)):
- the lab service on 127.0.0.1:18171, one fresh transient unit per server (`Restart=no`, `KillMode=process`, no SIGKILL,
  `LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19);
- all four card locks held by `sc117-tp-svc-fl-locks-20261029`; `NEOReadDebugKeys=1 EnableDeferBacking=0`;
- order tptsxq-r1, tptsxqc-r1, tptsxq-r2, tptsxqc-r2; binary 5921bb96f630 everywhere; `sc117-lan` not touched.
- A first `tptsxq-r1` launch completed its 12 prompts (median 77.32) but halted at the long-prompt probe: `ttft-doc.txt`
  had not been copied into this folder. It was stopped cleanly (terminal.json, kernel log clean), kept as
  [results/suite/pilot-tptsxq-r1-halted-ttft-packaging](results/suite/pilot-tptsxq-r1-halted-ttft-packaging/). After the
  file was copied, the whole A/B/A/B order was run fresh.

| Server | Median tok/s | Mean | Range | 12-prompt request time (s) | Outputs | Ready after | TTFT, 3,490 tokens |
|---|---:|---:|---:|---:|---|---:|---:|
| tptsxq-r1 | 77.18 | 77.50 | 74.73–81.75 | 86.795 | = B19, all 12 | 627 s | 9,826 ms |
| **tptsxqc-r1** | **78.62** | 78.87 | 76.12–82.82 | **85.228** | = B19, all 12 | 602 s | 9,822 ms |
| tptsxq-r2 | 77.15 | 77.37 | 74.58–81.31 | 86.908 | = B19, all 12 | 627 s | 9,812 ms |
| **tptsxqc-r2** | **78.29** | 78.64 | 75.82–82.43 | **85.488** | = B19, all 12 | 582 s | 9,824 ms |

- **Pair means: tptsxq 77.17, tptsxqc 78.46 tok/s, 1.0167×**; full request time 0.983×
  ([results/suite/summary.json](results/suite/summary.json)).

| Pair | Medians | tok/s per prompt: median (range), faster on | Request time per prompt: median (range), shorter on |
|---|---:|---|---|
| tptsxqc-r1 / tptsxq-r1 | 1.019 | 1.017 (1.013–1.023), 12/12 | 0.983 (0.975–0.986), 12/12 |
| tptsxqc-r2 / tptsxq-r2 | 1.015 | 1.017 (1.007–1.026), 12/12 | 0.983 (0.975–0.993), 12/12 |
| tptsxqc-r1 / tptsxq-r2 | 1.019 | 1.019 (1.013–1.025), 12/12 | 0.980 (0.976–0.987), 12/12 |
| tptsxqc-r2 / tptsxq-r1 | 1.014 | 1.016 (1.003–1.020), 12/12 | 0.985 (0.976–0.992), 12/12 |

**Tails and faults**, every decode half of the 13 client requests per server ([results/suite/tails.json](results/suite/tails.json)):

| Server | Rank | Halves | Faults (main + card 1) | Halves > 200 faults | Median / p90 / p99 / **max** (ms) |
|---|---|---:|---:|---:|---|
| tptsxq-r1 | 0 | 7,473 | 81,389 | 6 | 9.178 / 10.062 / 11.133 / **31.09** |
| | 1 | 6,029 | 80,675 | 7 | 10.331 / 10.529 / 11.708 / **33.21** |
| **tptsxqc-r1** | 0 | 7,473 | **0** | 0 | 9.244 / 9.283 / 9.417 / **12.24** |
| | 1 | 6,029 | **0** | 0 | 10.274 / 10.438 / 10.661 / **13.91** |
| tptsxq-r2 | 0 | 7,473 | 83,094 | 5 | 9.173 / 10.248 / 11.188 / **32.85** |
| | 1 | 6,029 | 74,190 | 8 | 10.313 / 10.517 / 12.146 / **41.93** |
| **tptsxqc-r2** | 0 | 7,473 | **0** | 0 | 9.257 / 9.297 / 9.614 / **13.01** |
| | 1 | 6,029 | **0** | 0 | 10.294 / 10.472 / 10.950 / **13.86** |

- The flag-off worst halves are the 12,295-fault double bursts; with the flag no half has a fault.
- Rank 0's p90 drops by 0.8–1.0 ms. Its median is 0.07 ms higher in the service, but equal in the isolated harness
  (section 4); the long request's trace agrees ([results/suite/long-prompt-trace.json](results/suite/long-prompt-trace.json):
  rank-0 speculative half 9.22 → 9.29–9.31, rank 1 10.41–10.43 → 10.37–10.39).
- **Host memory** ([results/suite/rss-growth.json](results/suite/rss-growth.json), RssAnon from `/proc`, every 30 s), from
  ready to the end of the suite (~100 s of serving):
  - flag off: rank 0 +395 / +316 MB, rank 1 +346 / +217 MB;
  - flag on: 0 / −128 MB.
  - In continuous decode the defect grows each TP rank by gigabytes per hour, and its bursts keep doubling.
- **Outputs:** all 5,965 ids, hashes and per-prompt MTP guesses and hits equal B19 on all four servers;
  `cached_tokens=0`; the long prompt's 64 ids hash to `29426ae7332a…` on all four.
- Startup gates passed on every server (F32 self-tests, pinned 4096/65536 state oracles, 13/13 batched-prefill cases).
  Teardowns clean. The kernel log was clean before, after ready, after the suite and after each server.

Archives (sha256-verified), all under `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/`:
- suite servers: `fault-ladder-suite-20261029/` (1,252 files, 495,545,675 B) and the pilot `fault-ladder-suite-pilot-tptsxq-r1/`;
- harness runs: `fault-ladder-runs-{f1,f2,c1,c2,c3,c4}/`;
- tracer build, unit-test binary, symbolised reports and the build log: `fault-ladder-tools/`.

## Next

1. **Service:** add `OWNRT_TP_CARD_CONTEXT=1` to the four-card flag set (arm `tptsxqc`, binary 5921bb96f630 or later). Without
   it, a long-running four-card service leaks host memory without bound and its tail halves keep growing.
2. **Upstream:** report the `saveKernel` defect to intel/llvm (the temporary `FastKernelSubcacheWrapper` in `try_emplace`
   erases this context's entries for all devices, and `MProgramToFastKernelCacheKeyMap` grows per save). Other lab processes
   with one SYCL context over several devices that share kernels (PP4, draft split, …) have the same exposure.
3. **Re-test closed host-side levers on the fixed path:** the persistent card-1 thread (its worse p90 may have come from
   the slow lookup) and the remaining host enqueue gap to one card (4.6–4.8 ms against 3.2–3.8 ms per half).

## Files

- Engine (commit `9d19335fa`): `stage2/packet194-expert-diet-engine/single_device.cpp`; receipt
  [5921bb96f630](../../../engine/receipts/5921bb96f630.json).
- Tracer and unit test: [tracer/](tracer/), [fast_cache_unit_test.cpp](fast_cache_unit_test.cpp).
- Lab (copies of persistent-thread's tooling): [run_phase.sh](run_phase.sh), [compare_phase.sh](compare_phase.sh),
  [tp_rank1_driver.py](tp_rank1_driver.py) (call times, tracer for the engine only), [arm_env.py](arm_env.py), [lab/](lab/),
  launch JSONs, suite scripts, [suite_compare.py](suite_compare.py) (+ request times), [tails.py](tails.py).
- Evidence: [evidence/](evidence/), [results/](results/) ([summary.json](results/summary.json)), [logs/](logs/).
