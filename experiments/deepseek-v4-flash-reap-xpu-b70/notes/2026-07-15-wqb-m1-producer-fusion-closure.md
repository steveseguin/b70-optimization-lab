# WQ_B M=1 producer-fusion closure

Date: 2026-07-15

Status: projection geometry understood; producer/consumer fusion rejected before
model integration.

## Question

The promoted QNorm/RoPE/direct-FP8-KV kernel removes one real graph node. The
next possible boundary was the preceding TP4 WQ_B projection: M=1, K=1024,
N=8192, BF16 activation, checkpoint-layout E4M3FN weights, and a `[8,64]`
block-scale grid. A complete replacement had to preserve the promoted output
and save at least 11.63 us per layer, or 0.50 ms/token over 43 layers.

## Padded-DPAS rejection

The first Triton proof fabricated an M=16 tile with fifteen zero rows so it
could use `tl.dot`. It passed no exact changed-input epoch and was about 8.13x
slower than oneDNN:

- 0/40 exact epochs;
- 199,171 mismatched BF16 elements in aggregate;
- maximum absolute difference 0.0078125;
- oneDNN median 28.5870 us;
- candidate median 232.4491 us;
- projected projection-only loss 8.7661 ms/token.

This rejects only BM16/BN64/BK32/four-warps with padded M, not all WQ_B
fusion. The raw result is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/wqb-fp8-bf16-gemv-card0-smoke3-20260715.json`
(SHA-256 `7445c0b5ea8e1cf727d9673b970a365ad0807b39d5e114448d971f0ee5a3de49`).
The synthetic scale distribution is not the real K160 UE8M0 distribution, and
the incomplete invocation metadata means this row is feasibility evidence,
not a production benchmark.

## True-M=1 subgroup result

XPU-kernel commit `de979b9328408302129c10ba04ed2fe090d414df`
adds a benchmark-only SYCL operator. A subgroup splits K=1024 across 16 lanes,
keeps weight reads coalesced, and emits one or more output values. Twelve
geometries were screened on every B70.

The one-output-per-subgroup form reaches 23.559-23.700 us across the four
cards. That is within measurement noise of, and on some cards slightly faster
than, the paired oneDNN reference. It is a 9.8x improvement over the padded-M
Triton proof and proves that direct scalar/subgroup M=1 is a viable projection
geometry.

It is not a viable complete fusion:

- all four cards pass 0/40 bitwise-exact epochs versus oneDNN, with one BF16
  step maximum error;
- one output per subgroup needs sixteen workgroups per 512-wide Q head, so no
  legal in-kernel head-wide RMS reduction can follow without another global
  boundary;
- the eight-output-per-subgroup form is the smallest tested topology that can
  place one 512-wide head in one 1024-thread workgroup, but its projection alone
  is already 53.330-53.644 us;
- that consumes essentially the entire current oneDNN-plus-fused-epilogue
  budget before RMSNorm, RoPE, and direct KV insertion, and cannot satisfy the
  11.63 us/layer integration gate.

The four raw result files are
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/wqb-sycl-fp8-bf16-gemv-card{0,1,2,3}-20260715.json`.

## Decision

Do not connect either WQ_B candidate to the model and do not run another TP4
server for this boundary. Preserve the benchmark operator and scripts so a
future Xe2 DPAS epilogue or workgroup-cluster primitive can reuse the measured
geometry. The result also explains why simply writing a custom GEMV is not the
remaining win: oneDNN is already at the memory-bound floor, while head-wide
normalization requires a topology that gives back the saved time.

The nonspeculative record remains 40.135724 tok/s. With the remaining exact
base candidates now below the 0.50 ms integration gate, the attached one-layer
MTP is the next bounded lane. Keep it separate from the base record and require
target-verified acceptance, cold cached-zero requests, and a positive complete
cycle result before any tuning.
