# Four-card prompt reading: rank-0 host work removed, exact (2026-10-30)

**Question.** On the four-card layout (`tptsxqckf`, binary `0509ad71a0fd`, 84.49 tok/s decode) a 121,854-token prompt
takes 250.5 s to its first token. Rank 0 is the critical path: 466.5 ms prefill + 60.3 ms draft per 256-row chunk,
against 468 ms on rank 1. The previous campaign attributed about 35 ms per chunk to rank-0 host work:
- row replays of six glue ops, 13 ms, with both cards near idle;
- lookup rows computed on the host, 15.6 ms;
- draft staging, 6 ms.

Remove that work exactly, each piece behind its own default-off flag, and measure the long request again.

**Answer.** The four-card layout now reads the 121,854-token prompt in **239.4 / 239.3 s** (two fresh servers) against
**250.5 s** for `tptsxqckf` on the same binary (−11.1 s, −4.4%). That is at or below the 3+1 262K layout (241–251 s).
- Decode after it is unchanged: 81.3 / 81.4 against 81.5 tok/s.
- All 512 outputs equal the 3+1 reference, the 12-prompt suite equals B19 on all three servers, and the 3,490-token
  prompt reads in 7.08 s instead of 7.37 s.
- **Exactness:** five new default-off flags; 35/35 rank-harness comparisons bitwise equal; every server passed the
  startup gate 13/13.
- **Per chunk:** rank 0 now spends 446 ms on prefill + 57 ms on the draft = 503 ms (was 465 + 61 = 526). Rank 1 spends
  465 ms.
- **Short of about 223 s, because one attribution was wrong.** The glue replays (12.4 ms) and the lookups (−9.7 ms) came
  off as projected. The 6 ms "draft staging" did not: the draft chunk is device-bound (3,840 single-row kernels,
  0.22 ms per row). Taking staging, guards and copy submissions off its thread saved only 4 ms.
- **Rank 0 has not reached rank 1:** it is 38 ms per chunk slower, and all of that is the draft chunk (§5).

## 1. What was built (engine r2 `c8e173bf4e7d` = `0509ad71a0fd` + five default-off flags)

| Flag | What it does | Where |
|---|---|---|
| `OWNRT_PREFILL_SPECIAL_ROWS=1` | `begin`, `commit`, `broadcast`, `ple_hash`, `ple_gate` and `ple_add` run as one launch per chunk instead of 256 row replays. Every row runs the unchanged single-row body on its own row of each row-major binding, and `begin`/`commit` also on their own row of the position array. `ple_hash` rows run in order in one work-group, with a global barrier between rows, because each row carries the token history to the next. | `prefill_engine.hpp` `prefill_special_rows_site`, `adapter.cpp` Glue token rows |
| `OWNRT_PREFILL_LOOKUP_THREADS=N` | The chunk's lookup ids are computed in row order, with the token history advancing as before. N host threads then dequantize contiguous row ranges, using the same `gsq::element` on the resident table bytes. `read()`'s counters are added after the join, and a non-resident table falls back to the sequential loop. | `prefill_engine.hpp` `prefill_lookup_rows_threaded`, `main.cpp` `Weights::resident` |
| `OWNRT_DRAFT_CHUNK_STAGE_THREAD=1` | A helper thread stages the draft rows (the same bytes into the same pinned rows). A row's copy is issued only after the thread has published that row (release/acquire, 10 s deadline). | `mtp.hpp` `replay_chunk_rows` |
| `OWNRT_DRAFT_CHUNK_GUARD_ROW=1` | The cooperative stop check (`Engine::guard`) runs once per draft row instead of before each of its 15 sites. The per-site deadline check stays. | `mtp.hpp` |
| `OWNRT_DRAFT_CHUNK_ROW_COPY=1` | A draft row's two staging copies become one prepared `KioCopy` kernel per staging row. It is captured once, replayed like the sites, and runs on the same in-order queue at the same point, storing every byte unchanged. It replaces two runtime memcpy submissions. | `mtp.hpp` `build_chunk_row_copies` |

- Built r1 `2bca4e65084d` (the first four flags) and r2 `c8e173bf4e7d` (+ `ROW_COPY`), both on `0509ad71a0fd`.
  Receipts are in `engine/receipts/`.
- The fifth flag was added after r1's measurement showed that the draft chunk's main thread was not paced by staging or
  guards, but by the per-row copy submissions (§3).

## 2. Gates (rank harnesses at 131,072; 35/35 comparisons bitwise equal; 0 kernel-log fault lines)

[results/gates.json](results/gates.json), produced by [gates_summary.py](gates_summary.py) from `logs/*-compare.txt`.

| Gate | Rank 0 | Rank 1 |
|---|---|---|
| smallest smoke (40 rows, 16-row chunks): flags on = off | s1 (r1), s2 (r2 + row copy) | s1 |
| new binary, flags off = baseline binary `0509ad71a0fd` | g1 (r1), g2 (r2) | g1 (r1) |
| flags on = flags off (1,100 rows, 256-row chunks) | g1, g2: 1029 buffers + 71 draft, draft tokens equal | g1: 1079 |
| batched = token by token (same binary) | g1 `tbt`, g2 vs g1 `tbt` | g1 `tbt`, g2 |
| = one card at 65,536 (prefix + zeros) | `hmcn` and `m`: 1009 + 20 / 67 + 4 | 1058 + 21 |
| two requests (`sp=600`: prompt, decode, reset, prompt, decode): on = off = r7 run = one card, requests A and B; reset inventories; ones buffer | 286 / 286 inventory rows, 0 differ | 61 / 61, 0 differ |
| r2 rank 1 = r1 rank 1 | — | g2 |

- Every arm ran under all four card locks, as a transient unit, with kernel-log checks before and after. All were
  clean.
- Raw runs went to `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/prefill-host-runs-{s1,g1,s2,g2,t2}` with sha256
  verification before the `/dev/shm` copies were removed. Compact evidence is under `evidence/<phase>/`.
- The g1 compare log has three lines with no result: a spec typo (`xrank0`) for the cross-context compares. They were
  rerun in the same log, and all are equal.

## 3. Harness timing (rank alone, 131,072, 1,100 rows; mean of the full chunks after the first)

[results/harness-timing.json](results/harness-timing.json) ([summarize_harness.py](summarize_harness.py)), host clocks
only (`OWNRT_PREFILL_HOST_TRACE=1`, no profiler).

| Per 256-row chunk | tptsxqckf (r2) | + all five (r2) |
|---|---:|---:|
| rank 0 prefill wall | 435.0 ms | **415.5 ms** |
| of which inputs (lookups) | 15.8 ms | 6.1 ms |
| host active / blocked on the cards | 66.2 / 367.3 ms | 42.8 / 369.8 ms |
| the six glue ops (12 sites), host | 12.6 ms (replays) | 0.17 ms (12 launches) |
| submissions per card | 3,644 | 2,114 |
| rank 0 draft chunk (KV-only, 256 rows) | 60.2 ms | **56.1 ms** |
| rank 0 critical (prefill + draft) | 495.2 ms | **471.6 ms (−23.6)** |
| rank 1 prefill wall (r1, + `SPECIAL_ROWS`) | 466.5 ms (median 467.9) | median 463.3 ms |

- **Glue rows:** 12.4 ms of host work becomes 12 launches, and the wall drops by the same amount. These replays ran when
  both cards were idle, right after an exchange.
- **Lookups:** 15.5 → 5.8–6.1 ms with 4 threads. What remains is the in-order id/history pass and the uploads.
- **Draft chunk, re-diagnosed.** Per row the main thread took 0.229 ms. Only 0.066 ms of that was issuing the 15 sites,
  and the staging (25 µs) and the 18 guards were not the bound. Moving staging to a thread (`stage_wait` 0.01 ms) and
  guarding once per row changed nothing: wall 60.3 → 60.4 ms.
  - The rest was the two runtime memcpy submissions per row, which pace the host to the device.
  - With them prepared (`ROW_COPY`: copies 1.0 ms per chunk), the host now waits in `admit_position`'s drains (34.7 ms,
    8 per chunk). The chunk is 56.1 ms of device time: 3,840 single-row kernels + 256 copies, 0.22 ms per row.
  - The draft chunk is device-bound. Only the copy change (−4.1 ms) moved its wall.
- **Rank 1 + `SPECIAL_ROWS`:** −4 ms (begin/commit). The first full chunk of g1-r1-new had a one-off 1 s host stall in
  the routed-GEMV and attention submissions. No other run showed it, the outputs were equal, and the median ignores it.
- **One-time cost:** the first run of a new kernel JIT-compiles it (the engine is built for `spir64`). The smoke s1's
  first rank-1 prompt took 58 s with a cold `/dev/shm` kernel cache, then 0.3 s. Services absorb this before timing,
  in their startup gate.

## 4. Fresh servers at 131,072, A/B/B (binary r2 `c8e173bf4e7d` for all three)

Each server was a fresh lab service at 131,072 (`suite.sh`, A then B, B), with all four card locks held by one holder
unit. Each had to pass its own startup gate (13/13 cases, batched reading on, 256 rows) before timing, then served the
12-prompt suite, the 3,490-token probe and the 121,854-token / 512-output long request. Kernel log: 15 checks, 0 fault
lines. Results are in [results/suite/](results/suite/) and [results/suite/summary.json](results/suite/summary.json).
Work directories are archived (sha256) at `.../2026-10-30/prefill-host-suite-20261030`.

| Server | A `tptsxqckf` | B1 `tptsxqckh` | B2 `tptsxqckh` |
|---|---:|---:|---:|
| startup gate | 13/13 | 13/13 | 13/13 |
| **TTFT, 121,854-token prompt** | **250.49 s** | **239.43 s** | **239.29 s** |
| decode after it (all 511) | 81.49 tok/s | 81.27 | 81.35 |
| 512 outputs = 3+1 262K reference (`bf1f0867d1bd`) | yes | yes | yes |
| MTP on the long request (hits / guesses) | 418 / 511 | 418 / 511 | 418 / 511 |
| 3,490-token prompt TTFT | 7.37 s | 7.08 s | 7.08 s |
| 12-prompt suite median (outputs, ids, MTP = B19) | 84.24 tok/s (yes) | 84.14 (yes) | 84.27 (yes) |
| rank 0 prefill per chunk (median) | 464.8 ms | 446.3 ms | 445.9 ms |
| rank 0 draft chunk (median) | 61.3 ms | 56.9 ms | 56.8 ms |
| **rank 0 critical per chunk** | **526.3 ms** | **503.0 ms** | **502.7 ms** |
| rank 1 busy per chunk / idle in the prompt | 467.7 ms / 27.3 s | 465.1 ms / 17.5 s | 465.2 ms / 17.3 s |

- Per-chunk timelines come from [analyze_long_trace.py](analyze_long_trace.py) on each server's `native-result.json`:
  [results/long-trace-*.json](results/). TTFT = 476 chunks × rank 0's critical chunk (502.7 × 476 = 239.3 s).
- The harness projected −23.6 ms per chunk. The long request measured −23.3 / −23.6 ms.

## 5. What bounds the ranks now, and the next lever

Measured, per 256-row chunk, from the long request ([results/bounds.json](results/bounds.json)):

| | Rank 0 (cards 23+27: layers 0–22, lookups, MTP draft) | Rank 1 (cards 43+47: layers 23–47, head) |
|---|---:|---:|
| prefill | 446 ms | 465 ms |
| draft chunk (device-bound) | 57 ms | — |
| **critical** | **503 ms** | 465 ms (idle 17 s per prompt) |
| harness: share of the chunk the host waits on the cards | 89% (370 of 416 ms) | 89% (416 of 467 ms) |
| exchange sites per chunk (each drains both cards) | 138 | 150 (6 per layer) |
| submissions per card | 2,114 | 2,595 |

- **Rank 0 remains the bound, by 38 ms per chunk (18 s per long prompt), and that is the draft chunk.**
  - Each prompt row replays the draft's 15 KV-only commands at M=1, so 3,840 single-row kernels plus 256 row copies run
    on card 0, at 0.22 ms per row of device time.
  - Card 1 does almost nothing during the draft chunk.
- **Both prefills are device-bound.** The host waits on the cards for 89% of the chunk. The remaining host work
  (about 43–48 ms) is mostly issuing and overlaps the device.
- **Not measured here:** the replicated work per layer (norms, hyper-connection glue, routing, `moe_combine` and status
  checks run on both cards at full M). Splitting it per class needs either device timing, which is not allowed under
  `--tp-replicate`, or a one-card host-trace run of the same flags at 65,536 to compare against. That is the measurement
  to make once rank 1 bounds.

**Next lever (not built): batched KV-only draft rows.**
- **What:** run the draft's KV-only path (merge norms and projections, `hc.a`, `qsa.k/v/ik`, prepare/pool, commit) as
  M=256 multi-row sites per chunk, as the target prefill already does for its layers. That is about 15–17 launches per
  chunk instead of 3,840 + 256.
- **Size:** the draft chunk goes from 57 ms to an estimated 5–10 ms. Rank 0 then needs about 451–456 ms, below rank 1's
  465 ms, so rank 1 becomes the bound. TTFT would be about 476 × 465 ms ≈ **221 s (−18 s, −7.5%)**. This is a
  projection, not a measurement.
- **Ceiling:** the gain stops at rank 1, so even a draft chunk of 15 ms reaches it.
- **After that:** rank 1's device time is the limit: 465 ms for 25 layers, 6 exchanges each. The next measurement is
  the replicated work per layer, against a one-card chunk at 65,536.
- **Not recommended:** moving a layer from rank 1 to rank 0. It would balance prompt reading, but rank 0 is already the
  slower stage in decode.

## Files

- Engine: `engine/src/.../prefill_engine.hpp`, `main.cpp`, `mtp.hpp`, `stage2/packet194-expert-diet-engine/adapter.cpp`.
  Receipts: `engine/receipts/2bca4e65084d.json`, `c8e173bf4e7d.json`.
- Harness, copied from prefill-speed-2026-10-29:
  - [run_phase.sh](run_phase.sh) adds extras `ep rd sr lt=N st gr rc`. Each phase ran from a frozen
    `logs/run_phase-<phase>.sh`.
  - [compare_phase.sh](compare_phase.sh) is unchanged.
  - The drivers record every `OWNRT_` key in `summary.json` (`env_flags`).
  - [lab/adapter6_tp.py](lab/adapter6_tp.py) passes the five keys to TP ranks.
  - [arm_env.py](arm_env.py) defines `tptsxqckf` and `tptsxqckh`.
  - [suite.sh](suite.sh)'s lock holder waits, bounded, for cards another agent holds.
- Launch JSONs: `rank{0,1}-launch-c{65536,131072}-{2bca4e65084d,c8e173bf4e7d,0509ad71a0fd}.json`. The baseline ones are
  the r1 launches with the baseline binary path; argv and environment are otherwise binary-independent.
- Results: `results/gates.json`, `harness-timing.json`, `g{1,2}-r{0,1}-*-host.json`, `long-trace-*.json`, `suite/`.
