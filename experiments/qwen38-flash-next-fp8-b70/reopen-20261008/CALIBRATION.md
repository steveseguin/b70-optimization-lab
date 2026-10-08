# Screen 1b memory reconstruction — CPU follow-up, 2026-10-08

**No configuration is established to meet both ≤85 GB host peak and ≥4 GiB
reserve on each card. This is missing calibration, not proof that fitting is
impossible.** The previous argument that v5 could not help relied on an
arbitrary 20 GiB overhead allowance; that argument is withdrawn. v5 is now
ported. The 90 GB gate and the watchdog have not been relaxed.

## Certified evidence and its limits

The [A364 summary](../data/20260913-tp4-mtp1-a364-native-exact-gdn-ple-only-qsa-stable-summary.json),
[A365 summary](../data/20260913-tp4-mtp1-a365-fresh-repeat-deterministic-summary.json),
[A366 summary](../data/20260913-tp4-mtp1-a366-native-exact-gdn-ple-only-qsa-stable-summary.json),
[A367 identity](../data/20260913-tp4-mtp1-a367-native-exact-gdn-identity.txt),
and [certified guide](../../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md)
identify the certified 46.854250 tok/s lane. Their raw A364–A367 run directories
are absent from `/mnt/fast-ai/bench-results` and
`/home/steve/qwen38-current-main-runs`. The recorded launcher destination,
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70`, does not exist on the
currently available filesystem. No mount, credential or device operation was
attempted. Reproduction manifests contain hashes, not the missing log bytes.

| Certified setting | Reconstructed value | Evidence boundary |
| --- | --- | --- |
| Host worker RSS, each rank | **Not recorded in available receipts** | Cannot reconstruct a peak from pins |
| Whole-host peak | **Unknown** | Cannot honestly demonstrate ±10% agreement |
| PLE storage | Native FP8, 80,000,384 rows × 160 bytes per rank on pinned CPU | TP4 partition of 320,001,536 rows; no table rows device-resident |
| PLE execution device | Rank-local XPU UVA view, one rank per card | Device-labelled tensor aliases host pages; not a second device table |
| Input embedding | 62,080 × 2,560 BF16 per rank, selected for UVA | 317,849,600 bytes/rank; shared with MTP, counted once |
| Expert host rows | 543 / 587 / 550 / 586 | Exact certified placement map; all remain callable |
| Host offload cap | 12.25 GiB/rank; actual PLE+embedding 13,117,911,040 bytes/rank | Expert rows are separately allocated, not extra generic-budget overshoot |
| GPU utilization | 0.92 | Frozen base launcher, not a measured use percentage or four-GiB reserve |
| Max model length / batched tokens / sequences | 4,352 / 64 / 1 | Same for the selected CPU packet |
| KV budget | 376,569,856 bytes/rank, full 16-bit, BLHNC | Explicit budget; no inferred graph or runtime bytes |
| Graphs | FULL_DECODE_ONLY, capture [1,2], compilation NONE, one warmup | Actual graph pool bytes not in surviving receipts |
| Per-rank VRAM weights / graphs / runtime | **Unknown measurements** | The table below is an optimistic static floor, not measured use |

The summaries' `input_embedding: "device"` label conflicts with their own
`host_offload_params`, byte count and frozen launcher. The old AMD model's
`_maybe_offload_embed_tokens` explicitly wraps the embedding through UVA;
the tensor's accelerator view explains why a device label cannot establish
physical residency. We reconstruct the declared allocation identity, not an
unavailable live observation. A314's [placement-load receipt](../data/20260907-tp4-mtp1-a314-placement-load-receipt.txt)
independently supports rounded expert bytes on ranks 1–3 but is not an A367
peak measurement.

## Formula and CPU measurement

```text
PLE[r] = (320001536 / 4) * 160 * 1 = 12800061440 bytes
Embedding[r] = (248320 / 4) * 2560 * 2 = 317849600 bytes
ExpertRow = (2*640*2560 + 2560*640) * 1 = 4915200 bytes
Pins[r] = PLE[r] + Embedding[r] + HostExpertCount[r] * ExpertRow
HostPhase = sum(live pins + private excluding pins + live copies + retained)
            + other host + active unique file pages + driver + safety
HostPeak = max(HostPhase over construction/loading/MTP/KV/capture/serving)
```

| Rank | Calculated pins GB | CPU measured RSS growth GB | CPU measured locked GB |
| --- | ---: | ---: | ---: |
| 0 | 15.786865 | 15.786865 | 15.786865 |
| 1 | 16.003133 | 16.003133 | 16.003133 |
| 2 | 15.821271 | 15.821271 | 15.821271 |
| 3 | 15.998218 | 15.998218 | 15.998218 |
| Sum (ranks measured sequentially) | **63.609487** | **63.609487** | **63.609487** |

[CPU dry measurement](cpu-buffer-measurement.json): exact real shapes allocated
with anonymous mmap, filled in 64 MiB chunks, and OS-locked with `mlock` under
the existing unprivileged limit. One rank at a time, a hard **20 GB process
address-space bound**, and the existing 80 GB/32 GiB pressure checks. No torch,
XPU allocator, device access or model payload read. Largest process RSS was
**16.161030 GB**; metadata/controller RSS was about 0.158 GB. Every rank released
all locked mappings before the next. Allocation-size error is **0%**.

This confirms that pins already appear in RSS: do not add them to that RSS
again. It does **not** establish XPU allocator retention, CCL/driver costs,
checkpoint page lifetime, graph pools, or a four-worker server peak. The
required certified peak error remains **unknown**, not 0%. The old 20 GiB
allowance is retained only as a labelled sensitivity case: 63.609487 GB +
20 GiB + 256 MiB = **85.352759 GB**, below 90 GB but above the requested 85 GB.
It is neither calibrated nor sufficient for admission.

## Enumerated V30 placements

All rows use the native host PLE split above, full-precision KV budget
376,569,856 bytes/rank, FULL_DECODE_ONLY (MTP1 [1,2], MTP0 [1]), no compiler,
length 4,352, TP4/EP4. The additional masks extend the certified map with
callable host rows, balanced by layer; they do not claim the extra experts
are never routed to. They are CPU planning alternatives, not timed results.

| Placement | Pins GB | Remaining host budget at 85 GB | MTP1 maximum possible minimum reserve GiB | MTP0 maximum possible minimum reserve GiB | Calibrated peak |
| --- | ---: | ---: | ---: | ---: | --- |
| Certified v5 | 63.609 | 21.391 GB | 2.140 | 2.796 | Unknown |
| Lab long-context v5 | 68.731 | 16.269 GB | 3.225 | 3.881 | Unknown |
| v5, 1,000 host experts/rank | 72.132 | 12.868 GB | 4.232 | 4.888 | Unknown |
| v5, 1,100 host experts/rank | 74.099 | 10.901 GB | 4.690 | 5.345 | Unknown |
| v5, 1,200 host experts/rank | 76.065 | 8.935 GB | 5.148 | 5.803 | Unknown |

Reserve columns are **upper bounds**, using an optimistic weight floor and
34,242,297,856 bytes/card (historical rank0 capacity only, not a current four-card
attestation). They omit scales, most replicated storage, runtime, graph pools,
allocator slack and workspace. Formula:

```text
Vfloor[r] = ceil((checkpoint loaded-weight bytes + 3 * replicated HC bytes)/4)
            - Pins[r] + KVbudget
ReserveUpper[r] = historical capacity - Vfloor[r]
```

MTP1 weight bytes = 185,486,485,760, replicated HC = 1,310,720,000;
MTP0 = 182,788,766,464 and 1,271,398,400 respectively. Header reads exclude
known ignored weights and nonweight buffers/scales, deliberately making this a
lower bound. Certified MTP1 Vfloor = **29.751 / 29.549 / 29.718 / 29.554 GiB**,
including 0.350708 GiB KV each. No invented weights/KV/graphs measurement split.

The certified placement cannot establish the new reserve target even at the
optimistic floor. Larger placements could fit **if** the missing overheads
fit the remaining budgets. For example, 1,100 rows/rank MTP1 needs ≤10.901 GB
of all nonpin host memory and ≤0.690 GiB/card of costs omitted by the floor.
Neither has supporting measurements, so none is selected as an admitted fit.
The watchdog also stops at **80 GB total accounted pressure**; a configuration
merely below 85 GB is not guaranteed to finish under that unchanged guard.

The default packet uses certified-v5 MTP1 as the least-changed reconstruction
candidate, **not as a claimed solution**. The arbitrary overhead assumption is
not lowered to make a green result.

## What changed and what still needs measuring

The new Python/Triton source port adapts the lab's
[final v5 series](../../../patches/qwen38-flash-next-fp8-b70/vllm-placement-mtp1-005dc578/README.md),
credited there to Codex Agent and Claude Fable 5.1. Creation allocates compact
resident and host tensors directly; the loader writes through logical row
views; all block scales stay on device; the same Triton K-loop loads through
per-expert offset tables. Logical expert counts survive tuning, dispatch,
workspace sizing and parameter replacement. It refuses incompatible backends,
rebalancing, all-host layers, and storage-changing postprocessing.

Compared with certification: same declared placement, PLE/embedding bytes,
KV budget, utilization, capacity and graph settings; newer NVIDIA-derived V30
model path instead of the older AMD-derived lab path; official native kernels
and fused GDN rather than certified exact GDN; different compiler/toolchain,
collectives and tuned MoE context; direct final-size creation plus bounded
copies/drained cancellation. **No exact-output or speed equivalence is claimed.**

Compared with stock V30: retained pinned Lumnus Python overlay enables this
model's XPU route; lab direct PLE allocation/coverage, embedding UVA, v5 expert
placement/Triton addressing, loader bounds and shutdown guard are added. No
native wheel or sampler replacement, table requantization, pruning, KV
compression or external PLE table. Source checkout and existing run artifacts
stay untouched; the overlay applies only to a future disposable container.

Non-launch measurements still needed:

1. Recover the archived A364–A367 `server.log`/supervisor/process/cgroup records
   from their existing storage, without mounting or operating GPUs in this task.
   Logs must contain RSS/private/pinned accounting and host trough/peak to
   support ±10% calibration; their hashes alone cannot do that.
2. The implemented CPU dry construction resolves logical buffer bytes and OS
   RSS double counting. True XPU pinned-pool retention cannot be measured under
   a no-GPU rule; substituting `mlock` for that allocator would be dishonest.
3. Existing archived per-card allocation snapshots could resolve capacity,
   loaded weights, cache and graph pools. V30's new runtime workspace/lifetime
   still needs separate evidence; the old server's peak alone cannot bound it.

The result therefore remains **REFUSED**. Nothing was launched or connected.
