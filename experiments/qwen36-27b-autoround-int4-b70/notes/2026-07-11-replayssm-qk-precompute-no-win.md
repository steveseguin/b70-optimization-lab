# ReplaySSM Q/K precompute and reuse: no win

## Hypothesis

The ReplaySSM recurrent kernel repeats Q/K normalization and the four-token
`K*K` / `K*Q` matrices in every value-head/value-bucket workgroup. Precompute
those K-head-owned values once, retain `v_dim_per_sg=4`, and let the recurrent
kernel load compact normalized Q/K and FP32 matrices.

## Implementation

The prototype added graph-capturable out-variant operations for Q/K precompute
and precomputed ReplaySSM decode. It preserved the legacy op as the default and
specialized the experiment for the promoted TP2/FP16 MTP3 shape: local heads
`8/24`, head dimensions `128`, spec length `4`, cache length `8`.

The source snapshot is:

`patches/qwen36-27b-autoround-int4-b70/vllm-xpu-replayssm-qk-precompute-aggregate-20260711.patch.gz`

This is an **aggregate dirty-tree snapshot** of the four touched kernel/API
files, not a clean patch against upstream. It contains pre-existing valuable
Qwen ReplaySSM changes and must not be applied wholesale without review. The
prototype symbols are `gdn_replayssm_precompute_qk` and
`gdn_replayssm_spec_decode_precomputed`; use those names to isolate the lane.

The benchmark base was corrected from global TP1/BF16 dimensions to the actual
per-rank TP2/FP16 record dimensions. `--tp-size 1` remains available, and
`--precomputed-qk` explicitly requests the experimental operations. The
production extension can still run the control without that flag.

## Four-GPU result

Raw artifacts:

- control identity check:
  `/mnt/usb-models/llm-optimization-artifacts/qwen27-replayssm/qk-precompute-baseline-20260711T225706Z`;
- candidate/control same-process runs:
  `/mnt/usb-models/llm-optimization-artifacts/qwen27-replayssm/qk-precompute-candidate-20260711T231223Z`.

Compact data:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-qk-precompute-4gpu-20260711.json`

The control stage-plus-decode path measured `36.66-36.79 us/layer`. The
candidate measured `44.91-45.42 us/layer`, a consistent `+22.52%` to `+23.46%`
regression. Median components were:

- Q/K precompute: `6.65 us`;
- legacy decode: `29.87 us`;
- precomputed decode: `33.87 us`.

The consumer itself is about `4 us` slower, likely because global normalized
Q/K and matrix loads replace register-local work while the new specialization
does not reduce the dominant state/history math. Even zero-cost fusion of the
precompute into stage-conv cannot recover that loss.

Parity was also not exact: output differed by at most `0.00048828125`, and
`d_cache` by at most `0.00390625`; all other compared mutable state was exact.
These are small FP16-order effects, but there is no speed benefit to justify a
quality investigation.

## Decision

Closed without an endpoint run and not eligible for LocalMaxxing. The
prototype source was removed after snapshotting and the production extension
and GDN library were restored. Do not retry a separate global Q/K precompute
buffer. A future attempt would need to share data within a fused producer or
workgroup design without adding global loads, and must first explain how it
avoids the measured `~4 us` consumer regression.
