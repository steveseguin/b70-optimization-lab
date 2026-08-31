# Qwen3.8 Flash-Next FP8 A28 collective timeline

Date: 2026-08-30
Status: offline analysis complete; no GPU or endpoint claim

The three retained A28 target-decode cycles each contain 97 BF16 allreduces.
Every reduction is `[1,2560]`, or 5,120 bytes. Ordinal 0 is the embedding
tensor-parallel reduction; ordinals `2L+1` and `2L+2` are the attention and MoE
reductions for layers 0 through 47.

Kineto's normalized `args.submitted` field is a host submission-arrival proxy.
It is not collective wire latency or a direct device-arrival timestamp. Across
291 aligned observations, rank 3 submitted last 142 times and rank 2 submitted
last 128 times. Rank 0 was last 9 times and rank 1 was last 12 times. Mean,
median, and maximum cross-rank submission skew grew across the three retained
cycles:

- cycle 0: 2.749 / 2.895 / 5.640 ms;
- cycle 1: 8.312 / 9.645 / 11.059 ms;
- cycle 2: 9.228 / 11.266 / 16.362 ms.

The worst point is cycle 2, ordinal 94, the layer-46 MoE reduction. The largest
single increase is 2.908 ms at cycle 1, ordinal 22, the layer-10 MoE reduction.
At that point the preceding MoE and GEMM device durations are nearly equal
across ranks, so queue or collective scheduling is a stronger bounded
hypothesis than raw MoE arithmetic. Skew generally accumulates through runs of
GDN layers and partially resets or changes owner at full-attention layers.

## Exact low-latency threshold hypothesis

The pinned `libccl.so.1` has SHA-256
`ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3`.
Its source defaults `CCL_SYCL_ALLREDUCE_LL_THRESHOLD` to 4,096 bytes. The PCIe
allreduce path selects `Rt64_PCIE` at or below that limit and
`Rt64_128_PCIE` above it. A28's 5,120-byte reductions therefore fall just over
the low-latency threshold, and all trace receipts show `Rt64_128_PCIE`.

The next bounded test is an isolated four-rank `[1,2560]` BF16 allreduce:
compare fresh-process 4,096-byte controls with an 8,192-byte candidate. Require
exact all-rank hashes, a protocol receipt changing only from
`Rt64_128_PCIE` to `Rt64_PCIE`, slowest-rank median/p95/p99 latency, and clean
logs. This needs no model load or reboot. If it wins consistently, the later
endpoint hypothesis is a single threshold change; it is not yet an endpoint
optimization or speed claim.

The same source and trace review also corrects A27: production single-sequence
decode enters the routed MoE kernel at M1, without a per-layer EP all-gather.
A27 loaded a map containing an M4 change but selected the unchanged M1 key.
The M4 component result remains valid for M4, but it was never exercised at the
endpoint. Re-screen production M1 separately.

Structured result:
[`20260830-tp4-mtp0-a28-collective-timeline.json`](../data/20260830-tp4-mtp0-a28-collective-timeline.json).
