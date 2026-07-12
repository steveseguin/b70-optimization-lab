# Xe2 grouped W4A16 as dense Qwen projection: no integration gate

## Question

The installed Xe2 grouped-GEMM implementation has a DPAS W4A16 policy for
`M<=4`. This screen invoked it as one expert on exact TP2-local Qwen27 layer-0
weights to determine whether it could replace the dense oneDNN producer. This
is distinct from the previously rejected scalar W4A16/SwiGLU prototype.

## Result

At `M=4`, rank 0, FP16 compute:

| Projection | Shape | oneDNN eager | Xe2 grouped eager | oneDNN graph | Xe2 grouped graph |
| --- | --- | ---: | ---: | ---: | ---: |
| gate/up | `5120 x 17408` | `89.700 us` | `119.782 us` | `150.742 us` | `147.830 us` |
| down | `8704 x 5120` | `41.730 us` | `78.741 us` | `64.447 us` | `116.019 us` |

Both grouped outputs had maximum absolute difference `0.0009765625` from the
production oneDNN result because their accumulation/reduction orders differ.
The gate/up graph result is a small noisy movement, while the eager producer
and down projection are decisive regressions. It does not justify endpoint
integration or a target-output quality change.

## Decision

Close using the existing grouped-MoE W4A16 operation unchanged for dense
Qwen projections. A future DPAS producer remains credible only if it adds a
true four-row specialization and production-equivalent rounding, then beats
oneDNN across gate/up and down real-weight gates. Do not route dense layers
through the current one-expert grouped interface.

Artifacts:

- harness: `scripts/bench-qwen27-w4a16-grouped-dense.py`;
- compact result: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-w4a16-grouped-dense-gate-20260711.json`.
