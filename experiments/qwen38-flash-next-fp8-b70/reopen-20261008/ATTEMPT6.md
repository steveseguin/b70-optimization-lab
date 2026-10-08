# Attempt 6: move more unchanged expert rows to host RAM

**Superseded after the owner's run:** the 77.955 GB host estimate below omitted
pinned allocator rounding. Attempt 5 did not establish shadow removal; it failed
before loading. The corrected steady estimate is 100.623 GB. See the
[attempt 6 analysis and attempt 7 decision](ATTEMPT7-BUDGET.md).

2026-10-08, CPU-only preparation on steve-b70s. Attempt 6 has **not run**.
The placement and utilization are updated; the certified placement and all
previous run receipts remain intact. No GPU, Docker, server, install, secret,
host-setting, Git branch/commit, or port 8188 operation occurred.

## What attempt 5 established

Its load stopped at the initial usable-memory check, before model loading.
Host pressure peaked at 12,236,701,696 bytes; MemAvailable stayed at or above
111,942,430,720 bytes. The low GPUActive observation confirms that the large
deferred-backing shadow was avoided during initialization. It does **not**
measure a completed model load, mmap cache, graph pool or ready plateau.

V30 initializes distributed contexts and performs a oneCCL all-reduce warmup
before this snapshot. Its native memory helper reports the driver's
`currUsableMemSize`, not sysman physical free bytes. The displayed 30.3 GiB
total minus 27.65/27.87 GiB usable is about 2.65/2.43 GiB already unavailable.
No `reserve-vram` option was found. The two CCL temporary-buffer switches are
enabled, but no receipt splits context, CCL, driver reservation and other
usable-memory accounting. Attributing the entire difference to oneCCL would
be unsupported. Rounded 27.87 can be below rounded 27.87 in the exact byte check.

A367 used utilization 0.92 and reported 28.62 GiB startup free on rank 0,
28.85 on ranks 1–3, about 0.97–0.98 GiB more. Its 29.57/29.37/29.54/29.38 GiB
model-load messages were PyTorch allocation deltas, **not physical VRAM peaks**.
The runtime and collective settings differ. Both use explicit KV bytes:
that bypasses utilization-based cache sizing, so 0.90 clears the startup test
but is not an enforced total-memory cap.
[Startup source and archived log citations](evidence/attempt6-startup-source-audit.md).

## Placement and device budget

`placement-attempt6-v5.json` keeps every certified host row, then adds pairs
in ascending `(A315 count, layer, expert)` order to **2,600 host rows/rank**.
Every expert remains callable. FP8 weights/scales, full 16-bit KV, mmap PLE,
target arithmetic and the MTP1 capture settings are unchanged. Old census
counts choose storage; they do not certify V30 routing or output quality.

| Rank | Old host rows | Added rows | New expert offload bytes | Added offload bytes |
| --- | ---: | ---: | ---: | ---: |
| 0 | 543 | 2,057 | 12,779,520,000 | 10,110,566,400 |
| 1 | 587 | 2,013 | 12,779,520,000 | 9,894,297,600 |
| 2 | 550 | 2,050 | 12,779,520,000 | 10,076,160,000 |
| 3 | 586 | 2,014 | 12,779,520,000 | 9,899,212,800 |

Each expert is 4,915,200 bytes across w13/w2. The generic `--cpu-offload-gb
12.25` remains the PLE/input-embedding selector cap; **it is not the expert
placement budget**. The new expert allocations are controlled by the mask.
Actual final pins are 14,171,275,264 bytes/rank including the input embedding,
1 GiB PLE cache and 163,840-byte host stage. No whole PLE table is pinned.
[Reproducible placement and input hashes](evidence/attempt6-placement.json).

The previous roughly 29.55 GiB values were optimistic **lower bounds including
KV**, not complete resident-weight bounds. The stronger header/source census
charges uncertain weights/scales fully replicated and finds 21.182598 GiB
resident weights with the new mask. Planning rounds the correction up:

| Component, every rank | GiB |
| --- | ---: |
| Resident weights: optimistic floor 19.983603 + 1.25 replication/scale allowance | 21.233603 |
| Full 16-bit KV, exactly 376,569,856 bytes | 0.350708 |
| Stable mmap PLE device step, 163,840 bytes | 0.000153 |
| Activations/workspaces | 0.500000 |
| Graph pools, decode capture sizes [1,2] | 0.500000 |
| Runtime, allocator retention and temporary storage | 0.750000 |
| **Planned engine peak** | **23.334464** |

Context capacity is **4,352**, but chunked prefill schedules at most **64 tokens**.
The workspace allowance covers that batch geometry, including an EP gathered
256-row sensitivity, rather than inventing a 4,352-row activation batch.
The workspace/graph/runtime allowances are **unmeasured estimates, not proven
upper bounds**. Complete phase bounds remain null and `qualified=false`.
[Tensor census, workspace formulas and source lines](evidence/attempt6-budget-source-audit.md).

Use the lower rounding edges 30.295 total and 27.645/27.865 usable GiB:

| Rank | Startup unavailable GiB | Engine peak GiB | Total accounted peak GiB | Headroom below 90% total GiB | Remaining usable GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 2.650 | 23.334464 | 25.984464 | **1.281036** | **4.310536** |
| 1–3 | 2.430 | 23.334464 | 25.764464 | **1.501036** | **4.530536** |

The conservative 90% line is 27.2655 GiB (about 27.27). Engine-only headroom
is 3.931036 GiB; the table also charges startup-unavailable memory, avoiding
an ambiguous headroom claim. This is usable-memory accounting, not a physical
VRAM measurement. The existing measured 4 GiB/card admission requirement and
2 GiB calibration stop stay intact. Attempt 5 had no readable sysfs VRAM
counters; a new missing-counter receipt still cannot admit generation.

## Host peak and expected cost

Predicted host pressure is **77,954,707,224 bytes (77.955 GB)**:
56.685101 GB final pins + 1.736346 GB metadata + 4.294967 GB active-file
allowance + 4.969857 GB measured attempt-5 post-hash baseline + 10 GB private
runtime/remaining-driver contingency + 0.268435 GB serialized staging.
The full 51.200246 GB PLE table stays file-backed; it is not added again.
The active-file allowance is an assumption, not a page-cache limit.
At the saved 124.179132 GB MemTotal this leaves **46.224425 GB available**.
This same conservative scenario covers loading and plateau, not a measured
phase split. A plateau at that estimate times 1.15 is **89.647913 GB**: only
0.352087 GB below the 90 GB admission line. The generation watchdog's 80 GB
pressure stop is unchanged too. Do not treat either small margin as assured fit.

The certified microbenchmark's UVA sensitivity is about **0.1 ms for each
additional selected host expert**, not for each allocated host row. For a
hypothetical uniform routing distribution, the added rows imply approximately
4.02/3.93/4.00/3.93 ms of additional work per rank per target token. Perfect
rank overlap would approach the largest figure; serial or per-layer imbalance
can move toward the **15.89 ms summed work**. A two-row MTP verification step
can double those terms. These are cost sensitivities, not a throughput forecast;
the chosen low-count rows may cost less, and the changed runtime may cost more.
The saved old census has 19,350/17,434/17,186/14,886 extra routed selections;
its final step denominator is unknown, so no per-step rate is invented.
The later matched A314 test found no measurable endpoint penalty from changing
host selection rates. That limits extrapolation of the microbenchmark; it does
not justify predicting zero cost here. Mmap misses add their separate latency.

## CPU validation and next command

**All 193 CPU tests passed (no skips), including four logical-rank rehearsals.**
The suite exercises the new mask through
real V30 model/loader construction with smaller tensors and emulated XPU
transport. They validate all 48 placement maps/rank, expert addressing,
loader cancellation, byte identity on tiny fixtures and allocation receipts.
They do not validate full-size XPU execution, MTP construction, graph capture,
peak memory or generated-output parity. Results are in
[test log](evidence/cpu-attempt6-tests.log) and
[four rank receipts](evidence/attempt6-cpu-rehearsal/).
The [dry run](evidence/attempt6-calibrate-load-dry-run.txt) verifies the sealed
inputs and builds the command without operational actions.

Prepared for the owner's separate launch window; **not executed**. Supply a
fresh health receipt and retain exclusive idle cards and the existing stop gap.
The controller still runs one load, zero generation requests, a 20-second
ready plateau and one graceful stop; no automatic retry.

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run \
  --mode calibrate-load --loading-ram-guard-gb 90 \
  --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json \
  --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt6 \
  --execute
```
