# Record-lane noncollective gates

Date: 2026-07-15

Status: closed without promotion; the strict record remains 40.020972 tok/s.

## Paired reference

The same-hour promoted-path control reached **40.023086 tok/s** median and
39.626888 p10 over the strict 12-prompt cold suite. All cached-token counts
were zero. This reproduces the 40.020972 record closely enough to classify the
following candidates without attributing their losses to thermal drift.

Evidence:
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/paired-control-20260715T0940Z`.

## Corrected eager timeline

A new phase-correct eager profile captured seven complete decode tokens at the
current tuned attention geometry. Rank 0 device totals were:

- generic dense `gemm_kernel`: 46.074 ms, or about 6.582 ms/token;
- MXFP4 `MoE::GemmCuteName`: 24.352 ms, or about 3.479 ms/token;
- `MhcPreM1Fused<true,false>`: 20.233 ms, or about 2.890 ms/token;
- tuned split-FP8 QK plus PV: 10.164 ms, or about 1.452 ms/token.

Do not add the profiler operator row for `mhc_post_pre_m1_out` to the MHC
kernel time. It is the enclosing correlated operator, not additional device
work. The earlier roughly 4 ms MHC attribution double-counted this boundary.
PTI still distorts oneCCL durations and cannot be used for collective timing.

Evidence:
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/record-lane-eager-tuned-profile-20260715T0730Z`.

## Closed scheduling and geometry gates

1. Shared/routed expert overlap was bitwise exact but regressed from 237.043
   to 286.704 us per layer at the EP4 rank-0 distribution, projecting a 2.135
   ms/token loss. Independent streams contend rather than overlap on B70.
2. Attention input-projection multistream overlap was also bitwise exact but
   projected a 2.575 ms/token regression: C128 lost 0.805 ms and C4 lost 1.771
   ms. Do not enable the NVIDIA-style auxiliary streams on XPU.
3. MHC post/pre `BLOCK_N=24`, WG256 saved only 0.955 us per boundary, or 0.081
   ms across 85 boundaries. WG128 was slower and numerically wrong. The
   promoted `BLOCK_N=12`, WG256 binary was restored.

Evidence:

- `shared-routed-overlap-ep4-microgate-20260715T0715Z.json`;
- `attention-input-overlap-microgate-20260715T0750Z.json`;
- `mhc-post-pre-geometry-20260715/`.

## C4 projection-fusion correction

The first horizontal-fusion microgate appeared promising because three BF16
projections collapsed from about 111 to 75 us. That modeled dead work. At the
record lane's 1,024-token context, C4 full selection bypasses the indexer, so
production does not execute the 64-wide index-weight or 512-wide indexer
compressor projections. Reintroducing them in a fused GEMM was invalid as an
optimization.

The duplicate-storage implementation reached 39.599640 and 39.605295 tok/s.
Rebinding the original parameters as packed views restored the baseline 24.88
GiB model footprint but still reached only 39.675887 tok/s. Both are rejected.
The vLLM experiment and reverts remain in history at `faa4ed6bc`, `be0f03f16`,
`e91e35ee9`, and `a9b19b98f`.

## Dedicated compressor GEMV

A Triton M=1 BF16-to-FP32 GEMV beat `torch.mm` by 1.34-1.60x in isolation.
The live-only implementation correctly targeted the 21 C4 and 20 C128 MLA
compressors and preserved changed-input arithmetic replay, but it was not
bitwise equivalent to oneDNN (maximum FP32 difference about 2.4e-7). Every
strict-suite output hash changed, and the end-to-end median was only 39.724930
tok/s versus the 40.023086 paired control. Reduction geometries from K16
through K1024 produced no bitwise match. Preserve the microkernel as research,
but do not promote an approximate compressor path that perturbs attention and
expert routing.

Evidence:

- `bf16-gemv-triton-microgate-20260715T0900Z.json`;
- `bf16-gemv-exact-search-20260715T1020Z.json`;
- `triton-compressor-gemv-20260715T1000Z/`.

The vLLM implementation and reverts are preserved at `745b40898`,
`c49231369`, `45ac86aa4`, and `44c5f959f`.

## MXFP4 small-N race diagnosis

The grouped-GEMM dynamic scheduler reset its global atomic counter from
workgroup 0 while other workgroups could already increment it. N32's doubled
tile count exposed that race during command-graph replay. Moving the reset to
an ordered queue fill made N32 and N128 bitwise identical to N64 for all 40
changed-input graph epochs.

This explains the previous misleading candidates:

- fixed N32 saved only about 1.05 us for a complete two-GEMM MoE layer, far
  below the full-model gate;
- fixed N128 measured 134.840 us versus 134.444 us for paired N64, so it is
  0.3% slower;
- the former N128 end-to-end speed gain accompanied changed outputs because
  the unsafe scheduler was not doing equivalent work.

The fix and explicit revert are preserved in XPU-kernel history at `a7a0300`
and `eeff530`. The promoted N64 binary was restored. Evidence is
`mxfp4-n32-racefix-graph-gate-20260715T1045Z.json` and
`mxfp4-n128-racefix-graph-gate-20260715T1100Z.json`.

## Decision and next boundary

Do not spend another server load on auxiliary streams, generic C4 horizontal
fusion, approximate compressor GEMV, or MXFP4 N32/N128. The record remains
the exact split-FP8 B4/QK16 lane.

The remaining path to a material base-decode gain is no longer a local launch
parameter. It requires a fused producer/consumer boundary that preserves the
existing exact dense and routing results—most likely the ordered collective
plus MHC consumer—or a heterogeneous attention prologue that retains oneDNN's
FP32 compressor result exactly. Require at least 0.50 ms/token in a hardware
gate before another four-GPU integration.
