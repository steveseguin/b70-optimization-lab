# Embedded-MTP cross-band, recovery, and four-service closeout

Date: 2026-08-10

## Decision

The integrated publisher-MTP Q8_0 identity retains its target-verified decode
gain at the correctness-required middle and near-32K ubatch settings, and four
independent one-slot services retain essentially all of the prompt-balanced
isolated realistic-suite rate. Both packets are parallel service evidence:
`performance_promotable=false` and `localmaxxing_submission_ready=false`.
They do not replace the separately approved isolated one-B70 LocalMaxxing
record `cmsn6b0bm0074o001uw5f9kod`, prove same-server c2, or qualify an eight-
slot serving claim.

Full integrated-MTP c2/32K remains a fit `NO-GO`. The measured one-slot MTP3
residency is `29,911 MiB`; adding the second target/draft KV and recurrent-state
allocations projects about `32,683 MiB`, beyond safe B70 capacity before useful
headroom. Do not launch that shape and do not hide the miss with CPU offload.
The sealed ordinary target-only VDR2 c2 packet remains the honest functional
comparator and performance failure.

## Identity

- Model: `unsloth/Qwen3.6-27B-MTP-GGUF` revision
  `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`.
- Artifact: `29,047,084,160` bytes, SHA-256
  `9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`.
- Runtime: llama.cpp `15586e2d7165570fb3aa7c26e0d442e289ef69de`,
  binary SHA-256
  `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`.
- Target/draft KV: F16; VDR2; DNN off; SYCL optimization on; MTP3 target-
  verified speculation.

## Failed crossover attempts and recovery

The failures remain negative evidence; neither contains a measurement.

1. `embedded-mtp-vdr2-crossband-crossover-20260810T120559.307858138Z`
   failed during wave-1 bring-up. BDF `0000:43:00.0` (logical GPU 2) logged
   CCS/BCS resets and `Fault response: Unsuccessful -ENOENT`; its service did
   not complete normal teardown, and another still-changing server log made
   the 114-entry root manifest stale. Logical GPU 3 logged an IGC termination
   during teardown. The root correctly remains `FAIL`, has no completion seal,
   and records `all_gpus_idle=0`, `all_ports_closed=0`, `body_completed=0`.
   The stale root-manifest SHA-256 is
   `4b897e44454881851647815a18f7a5caf8bce5290f8596c32e5511ddf9b6d331`;
   it fails on the changed
   `wave1/gpu1-middle-mtp3/server.stdout.log`. Do not repair or relabel it.
2. Commit `6892f215d` hardened ownership, serialized readiness, cleanup, and
   sealing. The next root,
   `embedded-mtp-vdr2-crossband-crossover-20260810T122232.328585286Z`,
   then failed closed before measurement because per-child telemetry inherited
   `ZE_AFFINITY_MASK=$gpu` and asked `xpu-smi -d $gpu` for a now filtered and
   reindexed device set. GPU 1's retained `xpu-smi-loaded.txt` and all 30
   bounded retries say `Error: device not found`. Cleanup is conclusive, but
   the same window also contains a real BDF `0000:43:00.0` GuC timeout/reset
   storm (`3,060` retained fault-scan lines), so no performance interpretation
   is allowed. Its 92-entry root manifest verifies at
   `726f4b388eb03be3f9e9879e6427fcf117a896e9eaceeaa8419d53b1a0d52098`;
   the root remains `FAIL` with no completion seal.
3. Commit `76ec2046c` moved discovery/stats calls under one global lock and a
   telemetry-local environment that clears Level Zero, oneAPI, SYCL, and UR
   device selectors while enabling Sysman. This preserves workload affinity
   without applying it to host-global physical-device telemetry.

The real GPU-2/GuC contamination was recovered without PCI FLR or a reboot.
Following the passive-first policy, all four B70s were unbound and the `xe`
module was reloaded. The frozen recovery root is:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/recovery/xe-reload-20260810T0833.fxkD91
```

It verifies four exact BDF/UUID mappings and idle readings, the exact peer-test
stdout `peer kernel read ok across 4 devices`, four per-card tensor smokes, one
four-rank XCCL init/barrier/all-reduce, and an official-isolated VDR2 generation
canary. The canary is `PASS_ORACLE_EXACT`, 2/2 full-512 rows, cache zero,
`65/65` offload, and `43 -> 43 MiB` cleanup; D100/D511 are
`16.576241 / 16.580272 tok/s`. No B70/xe fault followed the reload. The one
retained corrected PCIe receiver event belongs to NVMe BDF `0000:01:00.0` and
reported no further action; it is not a B70 event.

The read-only recovery packet has 127 files. Its 125-entry root manifest
excludes only the root manifest and completion file and includes the nested
80-entry generation-canary seal:

- root manifest:
  `a898b658f3029524bcddc5c70b6e1f07d1753e3d640aefba815ad2cee3524db5`;
- summary:
  `666aa4722017478e979c7ed719bf693512fb9fc401ba4b01b538bf655d5cff53`;
- completion:
  `c2810643aefb403670a2c94054f95d341cb9940d7d9a008215bb8a2683d7b455`;
- generation-canary manifest:
  `c7512a3ad9396f4c654379650d087457f1f7c8617d12170bd91532086637d012`.

## Recovered middle/near-32K crossover

Commit `9cac98d3a` reactivated the telemetry-sanitized harness. The successful
two-wave same-card crossover is:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/embedded-mtp-vdr2-crossband-crossover-20260810T125036.354085966Z
```

Each band used two B70s with control/MTP order swapped in wave 2. Middle kept
the correctness-required `-b 1024 -ub 128`; near-32K used
`-b 1024 -ub 1024`. Every one of the eight arms passed its two full-512 scored
rows and same-lifetime replay, cache-zero, full-offload, counter, and cleanup
gates. Same-card control/MTP tokens and content are exact for both prompts.
The first scored requests genuinely overlap on all four cards for
`65.930913 s` and `65.114247 s` in waves 1 and 2.

| Band | Control D99 | MTP3 D99 | D99 ratio | Control D511 | MTP3 D511 | D511 ratio |
|---|---:|---:|---:|---:|---:|---:|
| Middle | `15.071645` | `41.973818` | `2.784953x` | `15.016412` | `44.485167` | `2.962436x` |
| Near-32K | `13.665655` | `39.619374` | `2.899193x` | `13.662820` | `41.491243` | `3.036799x` |

Middle PP/TTFT ratios are `0.972501x / 1.028366x`; near-32K ratios are
`0.953361x / 1.048888x`, within the preregistered regression bounds. Minimum
same-row D99/D511 gains are `2.778348x / 2.956873x` at middle and
`2.850318x / 3.002378x` near 32K. MTP acceptance is `0.971867` at middle and
`0.974392` near 32K, with `2.900763 / 2.915709` accepted tokens per target
verification.

The packet classifies `PASS_CROSSBAND_MTP_RETENTION_WIN`, but remains
`parallel-functional-screen`, nonpromotable, and non-LocalMaxxing:

- 260-entry root manifest:
  `40e8892aee31e8aeb8e46d473d1c9e6a399edfe0416f154d47f8e63a76434fb3`;
- comparison:
  `53d739a21fd9052a4ae09db71c5bc8c4fa04ab65b969a03f3970374e269609e5`;
- completion:
  `1e791ec09fecf4f4d727d1a7a0a6158d554dc28d9ced398e81fa47ad685ca6c5`.

The root and all eight 26-entry child manifests verify.
Independent manifest/lifecycle and raw-metric audits returned `GO` with no
discrepancies.

## Four-service realistic scaling

The three-wave, four-service packet is:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/embedded-mtp-four-service-realistic-20260810T131718.247962407Z
```

One integrated-MTP process ran on each B70 at `-c 32768 -np 1`; this is four
independent slots, not c2. The fixed 12-prompt suite was partitioned into three
synchronized four-request waves. Recomputed four-way overlaps are
`8.747546 / 15.359000 / 15.232755 s`. All 12 rows pass the sealed retained-
position exactness policy and are cache-zero. Two UTF-8-buffered positions were
not directly observed in the current SSE; their IDs are transitively bound to
the sealed isolated capture rather than represented as newly observed IDs.
Every service loaded `29,911 MiB`, stayed fully offloaded at `66/66`, produced
positive bound MTP counters, and returned `43 -> 43 MiB` with no survivor,
listener, or forced kill. Device and server fault scans are empty.

The preregistered denominator is the sum of four prompt-balanced isolated
service medians, not global median times four. Aggregate D99 is
`139.098563 tok/s` versus `138.594926` reference (`1.003633879x` retention);
aggregate full-window rate is `136.884848 tok/s` versus `137.042399`
(`0.998850347x`). Prompt-normalized service fairness is `0.970874` for D99 and
`0.976385` for full-window rate; the minimum per-prompt D99 retention is
`0.990555918`. Bound service counters total 3,716 accepted / 6,427 drafted
tokens over 2,145 verifications. Every prompt, per-service, aggregate,
fairness, overlap, identity, lifecycle, and scan gate passes. An independent
raw-artifact audit returned `GO` with no discrepancies.

The packet classifies `PASS_REALISTIC_MTP_FOUR_SERVICE_SCALE`, with evidence
class `official-four-service-realistic-scaling-gate`; its own policy still sets
`performance_promotable=false` and `localmaxxing_submission_ready=false`:

- 112-entry root manifest:
  `e9329ff9ac1e71c076d42c6df5c97f1532577c3048b6c7911a8c56f1a24f9448`;
- capture:
  `0a1e1911a425803dd12cb4bd3d0ee7a3c249802203ae11a6ff671e2adaa00107`;
- four-service gate:
  `c91df0d92f1b254e13b54e092cb10a2c633ad08b5199a06c3d31b4bf12f8ef02`;
- completion:
  `bc2aa4e270ed318ec21c40bf4d0466ccb0a837f33bd8eedc5608322bd25d0f98`.

## What to do next

Bank the short, middle, near-32K, and four-service MTP evidence without
relabeling it as production or c2. The next useful work is durability and
turnover: a clean-build/second-card isolated reproduction where needed, at
least 100 mixed cold requests, one hour of four-service turnover, and a
production-facing routing/lifecycle design with sustained fairness and clean
restarts. Keep the ordinary c2 performance failure and integrated-MTP c2 fit
`NO-GO` visible. A materially different lower-memory concurrency design needs
a new identity and preregistration; unchanged c2 or CPU-offload retries do not.
