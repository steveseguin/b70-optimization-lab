# Persistent card-1 submission thread and per-thread page faults (2026-10-29)

**Question.** In the four-card service (77.11 tok/s, arm `tptsxq`), every TP half carried 6–12 host page faults and one
rank-1 half took 35.7 ms with 12,298 faults ([qsa-split section 6](../qsa-split-2026-10-29/RESULT.md)). The prime suspect
was the `std::thread` that `TpWorker` created and joined in every half for card 1's submissions. Does one persistent
card-1 thread per TP process remove the faults and the stalls, exactly?

**Answer.** It is exact, but it is not the cause and it is not faster.
- **Attribution (new per-thread fields):** thread start and exit cost **0 faults** in every run (the "other" class
  below). All TP faults are inside the two submission loops, and they stay the same with the persistent thread.
- **The bursts are a doubling ladder.** Per thread they come in sizes of about 100 → 196 → 387 → 772 → 1,539 →
  3,075 → 6,147 pages (0.4 → 24 MiB; 24-byte records × 2^14…2^20). Later bursts hit card 0's and card 1's submitting
  threads in the same half. The 12,294–12,298-fault halves (30–50 ms) are two 6,147-page bursts at once.
  - They occur on **every TP server** (24–28 bursts each, with either thread form).
  - The largest occur only in the 512-token requests, which fits one record per submission per queue, kept for a whole
    request.
  - **TP-specific:** the same 1,116-half token-by-token rank-1 harness shows 17 ladder bursts on two cards and none on
    one card.
- **Suite at 65536, four fresh servers (A/B/A/B), same binary:** **77.04 tok/s (current flags) against 76.87
  (+ persistent thread), 0.998×.** Per-prompt median ratios 0.990–0.999. All 5,965 outputs equal B19 on all four servers.
- **Rank harnesses:** card 1 starts its loop 7 µs after the job is published, against 26 µs for a new thread. Medians
  are unchanged (rank 1 −0.004 to −0.089 ms, rank 0 +0.01 / −0.01 ms half + draft). Rank 1's p90 is worse
  (10.59–11.03 against 10.24–10.44 ms), and it is worse in the suite too (10.95 / 11.26 against 10.55 / 10.54 ms).
- **Secondary, done:** the startup state-dump check is now O(runs). Lab servers are ready after **612–718 s against
  1,039–1,043 s** (the QSA-split servers before it; 728–732 s without the split). The check is just as strict.
- Gates all bitwise; 0 exchange timeouts; kernel log clean throughout; `sc117-lan` not touched.

Binary `1c667aea0690…` (build r1, [receipt](../../../engine/receipts/1c667aea0690.json)), built from `engine/src` into
`/dev/shm/engine-build-tp-persistent-20261029-r1`; engine commit `192420e9c`. Context 65536, B19 flags, F32. The
previous binary is `cb04951c3fb4` (qsa-split).

## 1. What was built (opt-in; default paths unchanged)

- **`OWNRT_TP_PERSISTENT_THREAD=1`** (with `OWNRT_TP_THREADS=1`; `rank.hpp` `TpPersistent`):
  - card 1's submission thread is created once per TP process, at its first threaded half;
  - between halves it is parked on a condition variable (it wakes once a second to check for a stop; no spinning);
  - per half, `begin()` publishes a job (generation, fixture, gated release) under the mutex. The thread then runs
    `tp_issue_card1`, the loop now shared with the per-half `TpWorker`: the same release index, stop bound and
    per-half deadline. It then publishes completion;
  - `finish()` waits for completion with `TpWorker`'s join deadline. A deadline poisons the thread (card 1 left
    untouched, as `TpWorker`'s detach), and later halves are refused;
  - teardown (`run_rank`, before the devices shut down) stops it with a bounded join and writes
    `tp-submit-thread.json`. Both thread forms write it: threads created, jobs, poisoned/joined, card-1 fault totals.
- **Per-thread faults in `timings.jsonl`** (both forms; diagnostic only):
  - `thread_minor/major_faults`: the half's thread (`RUSAGE_THREAD`, same window as the process counters);
  - `card1_thread_minor/major_faults`: card 1's thread over its issue loop;
  - `card1_thread_start_us`: time from publish (or thread creation) to the start of card 1's loop.
  - [faults.py](faults.py) splits each half into main / card1 / other (= process − main − card1).
- **Dump coverage by intervals** (`state_dump`, secondary task): both cards' non-empty runs are sorted by one-card
  start and must tile `[0, elements)` exactly. Each run must start where the previous one ended: earlier is an
  overlap, later is an element not covered. This is the same condition as the element-by-element check, which built
  its message string once per element (about 470 M per QSA-split dump).
- Lab ([lab/](lab/)):
  - the adapter passes `OWNRT_TP_PERSISTENT_THREAD` to TP ranks;
  - the service keeps every request's per-half rows (`req-*/rank*/timings.jsonl` → `control/run-*/tp-evidence/`)
    before it releases a request directory.
  - So tails are now measured over the whole suite, not only over the last request.

## 2. Gates (all bitwise; [logs/p2-gate-compare.txt](logs/p2-gate-compare.txt))

Context 65536; 1,100 prompt rows in 256-row chunks, then 16 decode halves (rank 1: 23:00.0 + 47:00.0; rank 0:
23:00.0 + 27:00.0; one card on 23:00.0). Driver commands as in qsa-split ([run_phase.sh](run_phase.sh), extra `pt`).

| Comparison | Rank 1 | Rank 0 (target, draft) |
|---|---|---|
| one card, new vs previous binary | 1079/1079 | 1029/1029, 71/71 |
| TP flags off (`tptsxq` set), new binary vs previous binary one card | 1079/1079 | 1029/1029, 71/71 |
| TP flags off vs one card | 1079/1079 | 1029/1029, 71/71 |
| **+ persistent thread vs one card**: rank 1 batched; rank 0 `hmcn` | **1079/1079** | **1029/1029, 71/71** |
| + persistent thread vs previous binary one card | 1079/1079 | 1029/1029, 71/71 |
| + persistent thread, prompt token by token (1,116 jobs, rank 1) | 1079/1079 | — |
| + persistent thread, timed cancels `x` / all-miss `m` vs one card with the same pattern (and vs `hmcn`) | — | 1029/1029, 71/71 each |

- Draft tokens equal in every rank-0 comparison. Card 1 equals card 0 on every buffer both hold (728 / 670) in all
  7 TP runs. 0 exchange timeouts and 0 aborts.
- Speculation events: `hmcn` 4 hits, 4 misses, 4 cancelled, 8 redos; `x` 5 misses + 11 cancelled (one card: 11 + 5);
  `m` 16 misses; 16 redos each.
- Thread records: one persistent thread per process for every job (16 / 24 / 32 / 1,116 jobs, all completed and
  joined, none poisoned). The flag-off runs created one thread per job (16 / 24).
- The first device run of the new path was the smallest smoke (16 rows, 4 halves; `p1-smoke`): rank 1 1079/1079 and
  rank 0 1029/1029 + 71/71 against one card.
- Kernel log clean before each phase (24 h) and after every arm.

## 3. Where the faults are (per thread)

Decode halves at positions 1,102+ (gates: 14 rank-1 / 21–28 rank-0 halves; timing: 46 / 62), sums, with median and
max per half ([results/p2-gate-faults.json](results/p2-gate-faults.json),
[results/p3-timing-faults.json](results/p3-timing-faults.json)):

| Run | Process | Main thread | Card-1 thread | Other | Card-1 start (µs, median) |
|---|---|---|---|---|---:|
| rank 1, per-half thread (gate / timing ×3) | 91 / 280 / 292 / 364 | **0** | 91 / 280 / 292 / 364 (median 3, max 18–53) | **0** | 25.4–26.7 |
| rank 1, persistent (gate / timing ×3) | 97 / 328 / 379 / 345 | **0** | 97 / 328 / 379 / 345 (median 3–4.5, max 26–53) | **0** | 6.9–7.4 |
| rank 0, per-half thread (gate / timing ×2) | 0 / 53 / 53 | 0 | 0 / 53 / 53 (one 49-fault half) | 0 | 26.3–26.7 |
| rank 0, persistent (gate, x, m / timing ×2) | 0, 0, 0 / 54 / 25 | 0 | 0, 0, 0 / 54 / 25 | 0 | 6.8–7.9 |
| one card, rank 1 / rank 0 | 0 / 0 | 0 / 0 | — | 0 | — |

**Suite** (every decode half of the 13 suite requests per server, both ranks; [results/suite/tails.json](results/suite/tails.json)):

| Server | Rank | Halves | Faults: main / card 1 / other | Halves > 200 faults | Median / p90 / p99 / **max half** (ms) | Worst half |
|---|---|---:|---|---:|---|---|
| tptsxq-r1 | 0 | 7,473 | 45,441 / 51,589 / 0 | 9 | 9.178 / 9.819 / 11.07 / **37.47** | req 38, 12,294 faults |
| | 1 | 6,029 | 35,906 / 43,882 / 0 | 7 | 10.350 / 10.547 / 11.69 / **36.87** | req 39, 12,295 |
| **tptsxqp-r1** | 0 | 7,473 | 33,269 / 39,483 / 0 | 10 | 9.156 / 9.987 / 11.09 / **29.52** | req 34, 12,296 |
| | 1 | 6,029 | 33,913 / 46,846 / 0 | 8 | 10.297 / 10.948 / 11.90 / **33.02** | req 38, 12,291 |
| tptsxq-r2 | 0 | 7,473 | 46,418 / 51,488 / 0 | 12 | 9.177 / 10.271 / 11.71 / **50.23** | req 33, 12,295 |
| | 1 | 6,029 | 29,716 / 44,014 / 0 | 6 | 10.334 / 10.541 / 12.41 / **41.38** | req 39, 12,294 |
| **tptsxqp-r2** | 0 | 7,473 | 49,453 / 48,960 / 0 | 11 | 9.171 / 10.376 / 11.64 / **32.06** | req 39, 12,294 |
| | 1 | 6,029 | 25,529 / 28,746 / 0 | 4 | 10.299 / 11.259 / 12.25 / **32.51** | req 38, 12,294 |

**The burst ladder** ([bursts.py](bursts.py) → [results/suite/bursts.json](results/suite/bursts.json)): every half
above 150 faults, per thread, rounds to one of 100, 196, 387, 772, 1,539, 3,075 or 6,147 pages. That is
24 B × 2^14 … 2^20 plus a page or two: a container of 24-byte records reallocated by doubling.
- Early in a server's life only card 1's thread bursts; from about request 26 both threads burst at the same size in
  the same half.
- 6,147-page bursts occur only in the 512-token client requests, and sizes recur request after request. This fits
  one record per submission per queue (about 1,300 submissions per card per half; about 1 M over a 512-token request),
  dropped at the request reset.
- It is TP-specific ([results/p4-onecard-vs-tp-tbt.json](results/p4-onecard-vs-tp-tbt.json)): rank 1, 1,100 prompt
  rows token by token + 16 decode halves, same binary.
  - Two cards (persistent thread): 17 ladder bursts, 17,951 faults after the first half.
  - One card: 1 burst (the first decode half after the prompt), 1,969 faults.
- The engine's own event lists are cleared at every drain and have fixed capacity (`SyclDevice::events_` reserves
  65,536 32-byte records and refuses more). So the container is in the SYCL / Level Zero submission path of a
  two-card shared context, or in a TP-only submission. Not yet identified.

## 4. Speed: rank harnesses, A/B/A/B in one phase

48 decode halves (rank 1, driver medians of halves 3–48) and 64 speculative hits (rank 0)
([results/p3-timing-rank1.json](results/p3-timing-rank1.json), [results/p3-timing-rank0.json](results/p3-timing-rank0.json)):

| Rank, cards | Per-half thread (run 1 / 2) | Persistent (run 1 / 2) | p90, per-half / persistent |
|---|---:|---:|---|
| rank 1 half, 23 + 47 | 10.211 / 10.224 | 10.207 / 10.193 | 10.237, 10.261 / **10.819, 11.034** |
| rank 1 half, 43 + 47 (service cards) | 10.280 | 10.191 | 10.440 / 10.590 |
| rank 0 speculative half, 23 + 27 | 9.249 / 9.243 | 9.262 / 9.244 | — |
| rank 0 half + draft | 10.358 / 10.357 | 10.376 / 10.350 | — |

- All tokens equal; 0 timeouts; 0 faults on any main thread.
- The persistent arm's slow halves are spread out; one had 443 involuntary switches of the main thread. A likely
  mechanism is wake-up placement: a woken thread returns to its previous CPU when that CPU is idle, even if its SMT
  sibling runs the other submission thread. A new thread is placed on the idlest core. This is not proven
  (CPU numbers are not recorded).

## 5. Suite at 65536

Run as qsa-split section 5 ([suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh)):
- the lab service on 127.0.0.1:18171, one fresh transient unit per server (`sc117-tp-svc-pt-arm-<name>-20261029`,
  `Restart=no`, `KillMode=process`, no SIGKILL, `LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19);
- all four card locks held by `sc117-tp-svc-pt-locks-20261029`; `NEOReadDebugKeys=1 EnableDeferBacking=0`;
- order tptsxq-r1, tptsxqp-r1, tptsxq-r2, tptsxqp-r2, each a fresh server, never a retry. Binary `1c667aea0690`
  everywhere; `tptsxqp` = `tptsxq` + `OWNRT_TP_PERSISTENT_THREAD=1` ([arm_env.py](arm_env.py)).

| Server | Median tok/s | Mean | Range | Outputs | Ready after | TTFT, 3,490-token prompt | Its decode tok/s |
|---|---:|---:|---:|---|---:|---:|---:|
| tptsxq-r1 | 77.01 | 77.59 | 74.53–82.01 | = B19, all 12 | 718 s | 9,847 ms | 71.77 |
| **tptsxqp-r1** | 77.34 | 77.27 | 73.73–81.37 | = B19, all 12 | 657 s | 9,876 ms | 70.74 |
| tptsxq-r2 | 77.07 | 77.21 | 74.29–81.56 | = B19, all 12 | 667 s | 9,839 ms | 71.23 |
| **tptsxqp-r2** | 76.41 | 76.79 | 73.56–79.84 | = B19, all 12 | 612 s | 9,865 ms | 69.88 |

- **Pair means: tptsxq 77.04, tptsxqp 76.87 tok/s, 0.998×** ([results/suite/summary.json](results/suite/summary.json)).
- **Per prompt:**

| Pair | Medians | Per prompt: median (range) | Faster on |
|---|---:|---|---:|
| tptsxqp-r1 / tptsxq-r1 | 1.004 | 0.994 (0.980–1.013) | 4/12 |
| tptsxqp-r2 / tptsxq-r2 | 0.991 | 0.994 (0.979–1.009) | 5/12 |
| tptsxqp-r1 / tptsxq-r2 | 1.004 | 0.999 (0.989–1.014) | 6/12 |
| tptsxqp-r2 / tptsxq-r1 | 0.992 | 0.990 (0.973–1.004) | 3/12 |

- **Outputs:** all 5,965 ids, hashes and per-prompt MTP guesses and hits equal B19 on all four servers;
  `cached_tokens=0`; the long prompt's 64 ids hash to `29426ae7332a…` on all four.
- **Startup gates passed on every server** (F32 self-tests, pinned 4096 and 65536 state oracles, 13/13
  batched-prefill cases). They now finish in 612–718 s.
- The kernel log was clean before, after ready, after the suite and after each server. The only kernel line in
  the window is an AppArmor denial for the snap firmware updater.
- Long request's trace ([results/suite/long-prompt-trace.json](results/suite/long-prompt-trace.json)): rank-1 half
  10.40 / 10.37 / 10.43 / 10.54 ms, rank-0 speculative half 9.20–9.23 ms, draft 1.07 ms on all four.

Raw server directories (1,252 files, 495,413,964 B, sha256-verified):
`/mnt/raid-models/ownrt-experiment-archives/2026-10-29/tp-persistent-suite-20261029/`. Harness runs:
`…/2026-10-29/tp-persistent-runs-{p1,p2,p3,p4}/`.

## Next

1. **Find the 24-byte-per-submission record** (the real fault and stall source). Reproduce in under a minute with the
   rank-1 token-by-token TP harness (`g-r1-tptqp-tbt` arm: 17 ladder bursts). Log every allocation of 1 MiB or more,
   with a backtrace, from an `LD_PRELOAD` shim in that one run: host-only, no device profiler, no memory setting.
   Candidates:
   - the SYCL in-order queue's per-event bookkeeping in a two-device shared context;
   - the Level Zero adapter's per-command-list event lists;
   - the TP-only exchange submissions (`queue::submit` outside the prepared path).
   A fix that drops the records at each half's drain (or avoids creating them) would remove the 30–50 ms tail halves
   (4–12 per rank per suite server, the worst 29.5–50.2 ms) and the steady 2–3 faults per half.
2. **Persistent thread: closed for now** (no speed gain, worse p90). It may be worth re-testing after (1), with the CPU
   of both submission threads recorded per half to confirm or rule out the SMT placement explanation.
3. The service flag set stays `tptsxq`. Binary `1c667aea0690` with the flag off is the same service with the faster
   startup check.

## Files

- Engine (commit `192420e9c`): `rank.hpp` (`tp_issue_card1`, `TpWorker` attribution, `TpPersistent`,
  `tp_persistent_stop`, per-thread fields, interval coverage in `state_dump`), `main.cpp` (`Engine::tp_persistent`);
  receipt [1c667aea0690](../../../engine/receipts/1c667aea0690.json).
- Lab (copies of qsa-split's tooling): [run_phase.sh](run_phase.sh) (extra `pt`, thread-record check),
  [compare_phase.sh](compare_phase.sh), [faults.py](faults.py), [tails.py](tails.py), [bursts.py](bursts.py),
  [arm_env.py](arm_env.py) (arm `tptsxqp`), [lab/](lab/) (adapter key; per-request rows kept), launch JSONs, suite
  scripts, [suite_compare.py](suite_compare.py), [trace_summary.py](trace_summary.py).
- Evidence: [evidence/](evidence/) (per run: summary, rank log, timings, exchange/compare statistics, thread record;
  state hashes for gate runs), [results/](results/), [logs/](logs/) (phase logs, kernel-log checks, archive receipts).
