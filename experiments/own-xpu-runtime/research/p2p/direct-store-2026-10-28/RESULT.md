# Kernel-direct cross-card exchange on two B70s (2026-10-28)

**Question.** Exact TP broke even on 2026-10-25 because each gather cost about 13 µs. Can the producing kernel write
straight into the peer card's memory and raise one flag, for well under 5 µs per exchange?

**Answer: yes for 10–40 KB.** The added cost per exchange is **1.6 µs at 10 KB and 3.3 µs at 40 KB**, against the
5 µs threshold, with zero wrong values and zero timeouts. The old event-plus-copy path costs 6.3 and 10.3 µs in the same
harness. At 160 KB the direct path costs 11 µs, which is bandwidth. **PASS.**

## Setup
- Cards 0000:23:00.0 (A) and 0000:47:00.0 (B), one SYCL context, one in-order queue each. Both card locks held,
  `taskset -c 0-3,16-19`, oneAPI 2026.0, driver 1.15.38308. The SYCL runtime reports peer access in both
  directions but **no peer atomics**. So the flag is a plain store between system-scope release fences, and nothing
  atomic touches peer memory.
- **A. Ping-pong:** one single-work-group persistent kernel per card. Each round is a payload plus a flag, then the
  same reply. One-way time = (T(K2) − T(K1)) / (2 (K2 − K1)), median of 7.
- **B. Chain (decision metric):** per card, 1,440 exchanges (48 layers × 3 × 10 tokens), submitted ahead with no host
  waits. Each exchange is:
  - a producer kernel (8×256 items, about 12 µs of ALU work) that stores its half locally and in the peer's gathered
    buffer; its last work-group then sets the peer's flag;
  - a consumer kernel (8×256, about 12 µs) that waits on its local flag with a bounded spin, then reads and checks the
    whole gathered vector.

  `none` runs the same kernels with no peer store or wait. `memcpy` pulls the peer half with a SYCL memcpy that
  depends on the peer producer's event, which is the old engine path. 7 alternating repeats for direct (5 for memcpy),
  medians. Host submission (13–15 µs per exchange; memcpy 26–28) stays below device time, so the device sets the pace.
- Payload means bytes each card sends per exchange. The gathered vector is twice that size.

## Results (attempt 2: `results/main.json`, `logs/driver.log`)

| Per direction | Ping one-way | Chain none | Chain direct | **Added, direct** | Added, memcpy |
|---:|---:|---:|---:|---:|---:|
| 4 KB | 2.98 µs | 26.12 µs | 27.54 µs | **1.43 µs** | 6.29 µs |
| 10 KB | 5.48 µs | 26.50 µs | 28.13 µs | **1.63 µs** | 6.25 µs |
| 40 KB | 17.88 µs | 27.75 µs | 31.08 µs | **3.33 µs** | 10.26 µs |
| 160 KB | 67.99 µs | 33.31 µs | 44.30 µs | **10.98 µs** | 17.62 µs |

- **Spread:** the min-to-max range of each chain median is under 0.1 µs.
- **Consumers almost never wait:** 0.4–0.6 polls per consumer work-group on average, at most 63. The cost is the
  producer's remote stores and fences, not the wait.
- **Engine copy path, same session (`bin/owner_peer`, unchanged `research/p2p/owner_peer.cpp`):** device-side round
  trip (2 copies and 2 waits) of 28.6 / 32.6 / 31.1 µs at 10 / 40 / 160 KB. An earlier run in this session gave
  24.4 / 29.0 / 28.9. That is about 12–16 µs per one-way hop, all bitwise-equal.
- **Correctness:** 0 mismatches, 0 timeouts, 0 aborts.
  - 46,080 direct exchanges, each checked on both cards.
  - 34,560 memcpy exchanges, each checked on both cards.
  - 42,390 ping round trips, checked on both sides.
  - The 4 KB one-round-trip smoke passed first.
- **Kernel log:** clean before the run (last 24 h) and after every process (`logs/kernel-log-*.txt`). No xe, GuC,
  CAT, reset or fault lines. Device time was about 4 s (attempt 1) plus 8 s (attempt 2).

## What attempt 1 showed (kept in `*attempt1*`, source `p2p_direct_store.attempt1.cpp`)
- **Stale reads inside one kernel.** Plain loads inside one persistent kernel returned the previous round's payload
  even after a system-scope acquire fence. Every element in rounds 2–10 was stale, so cached lines are not refreshed.
  - Separate consumer kernels read fresh data. An engine consumer is a new kernel, so it is not affected.
  - The ping-pong now reads the payload with system-scope atomic loads.
- **Host-memory gate failed.** A gate kernel spinning on a host-USM flag almost never saw the host's store (timed out
  at the cap in 15 of 16 gate waits). That desynchronised the cards and the 10/40 KB pre-scale gate failed, so the
  run stopped before scaling up as intended. The gate was removed. Lesson: do not gate device work on host-USM polling.

## Caveats
- Ping-pong figures above 4 KB are limited by one work-group's store and atomic-load rate, not by the link. Use the
  4 KB figure (about 3 µs) as the latency, and the chain as the decision metric.
- The chain is symmetric and lockstep, with 8-work-group producers. Real GEMV epilogues spread stores over more
  Xe-cores, which may help 160 KB, and the two cards' layer times will not match exactly.
- Not tested yet:
  - graph-captured or replayed command lists;
  - copy-engine traffic at the same time;
  - more than two cards.
- Correctness depends on fresh consumer kernels or atomic/uncached loads, and on the last-work-group counter before
  the flag store.

## Rerun
`./build.sh`, then the launch line at the top of `run_device_phase.sh` (systemd-run → flock both cards → taskset →
smoke → gate → main → owner_peer, with a kernel-log check after each). Binaries in `bin/` are git-ignored.
