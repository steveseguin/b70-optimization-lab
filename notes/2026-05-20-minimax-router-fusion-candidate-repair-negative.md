# MiniMax M2.7 Router-Fusion Candidate-Repair Screen

Date: 2026-05-20

## Summary

Screened whether the existing exact MiniMax candidate-repair router kernel can be
used as the first implementation of a router-linear plus MoE fusion path.

Decision: do not use the current all-256 candidate-repair kernel for router
fusion. It reproduces the exact MiniMax `sigmoid(router_logits) + bias` top-8
selection, but it is far slower than the existing XPU `linear` router path for
decode-sized inputs.

## Microbench Result

Shape: hidden size `3072`, experts `256`, top-k `8`, random XPU tensors.
Candidate list was all experts `[0..255]`, so this is exact rather than an
approximate candidate filter.

| Decode tokens | Current `linear(x.float(), w)` | Existing exact repair over 256 experts | Correctness |
| --- | ---: | ---: | --- |
| 1 | `0.032211 ms` | `0.609194 ms` | top-k ids matched, max weight diff `3.7e-08` |
| 2 | `0.022275 ms` | `0.523925 ms` | top-k ids matched, max weight diff `7.45e-08` |
| 4 | `0.022450 ms` | `0.656969 ms` | top-k ids matched, max weight diff `7.45e-08` |

## Interpretation

The existing candidate-repair kernel is useful for auditing and for future
approximate-router repair paths where the candidate set is small, but it is not
a viable replacement for the full router linear. Using it over all 256 experts
would add far more time than the router materialization currently costs.

The source-level route is still credible, but it needs a new optimized router
kernel or a different fusion boundary:

- compute the full 256-expert router scores with a proper GEMV/GEMM-style XPU
  kernel and fuse only the sigmoid+bias top-k and MoE launch boundary;
- or keep the current `linear` and focus on removing a downstream framework or
  graph scheduling boundary around `router_logits -> MiniMax top8 -> INT4 MoE`;
- do not implement naive all-expert candidate repair in the promoted path.

## Quality Status

This was a standalone kernel microbench, not a full model benchmark. It did not
change model outputs and was not submitted to LocalMaxxing.

## Next Step

Run a focused decode timing diagnostic on the promoted stack to quantify whether
router materialization is still visible at the full-model level. If the router
linear is already negligible relative to attention, collectives, and INT4 MoE,
move the next patch back to Q/K variance, attention `o_proj`, or MoE output
fusion rather than spending more time on router fusion.
