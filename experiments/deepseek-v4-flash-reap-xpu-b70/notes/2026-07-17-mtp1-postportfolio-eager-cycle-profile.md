# MTP1 Post-Portfolio Eager-Cycle Profile

Date: **2026-07-17**

Status: **complete; subgroup-split MXFP4 gate remains the next bounded work**

## Purpose And Identity

The preceding eager-cycle profile predates the promoted QNorm-M2 plus
route-direct portfolio. The exact record source, kernel, oneCCL, quantization,
MTP1, and model selectors were therefore reloaded as an eager diagnostic twin:

- vLLM `4a6fd874725312c53883b1d53970af1d0eccfc3f`;
- XPU kernels `18a44f440ca3ac2006d5ba19cd12ccca0a0c9982`;
- oneCCL `48fda4f0e074db005596d6899d5227d3f0316c12`;
- unchanged K160 model and MXFP4 N64 policy;
- QNorm/RoPE/FP8-KV maximum M=2 enabled;
- route-direct compact M=2 enabled;
- graph replay disabled only for operator/shape attribution.

The reusable launcher is
`../scripts/serve-k160-mtp1-postportfolio-eager-profile.sh`. Raw evidence is:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-postportfolio-eager-profile-20260717T032135Z`

The profiled request produced 18 fresh tokens with `cached_tokens=0`. Four
uncompressed rank traces total about 1.47 GB. The tracked streaming summary is
`../data/eager-cycle-postportfolio-20260717-summary.json`.

## Method And Limits

The existing streaming summarizer associates XPU kernels with the enclosing
decode context through host submission timestamps while retaining device-event
durations. The first decode context is discarded on every rank, leaving ten
MTP1 contexts per rank.

The classifier now recognizes the promoted compact MXFP4, native router,
direct-remap, routed activation/gather, and QNorm/RoPE/FP8-KV kernel names.
This changes attribution labels, not event timing.

Kineto still distorts oneCCL durations and host context time. Those values are
excluded from the additive noncollective total. Three prompt-shape Triton
kernels compiled after profiling began; dropping an additional one, two, or
three retained contexts changes the cross-rank noncollective mean only from
17.8497 to 17.8771, 17.9152, or 17.9379 ms/cycle. The device attribution is
stable enough for boundary selection, but it is not a replay wall-cycle
prediction.

## Post-Portfolio Device Attribution

| Bucket | Cross-rank mean ms/MTP1 cycle |
| --- | ---: |
| Dense GEMM | 6.5639 |
| Compact routed MXFP4 GEMM | 3.9424 |
| Native MHC post/pre | 2.8354 |
| Other noncollective | 1.6829 |
| Attention QK/LSE | 1.2716 |
| Attention PV | 0.4798 |
| Native router select/normalize | 0.3902 |
| QNorm/RoPE/direct FP8 KV | 0.2531 |
| Direct M=2 route remap | 0.2008 |
| Routed MoE gather | 0.1497 |
| Routed clamp-SwiGLU | 0.0800 |
| **Noncollective total** | **17.8497** |

The pre-portfolio profile reclassified by the same summarizer totals
19.4779 ms/cycle. The promoted portfolio therefore removes about
**1.6283 ms/cycle** of measured noncollective work. Dense GEMMs are essentially
unchanged (6.5803 -> 6.5639 ms), as expected. The explicit compact MXFP4
kernels remain the largest open kernel family at 3.9424 ms/cycle.

The old generic router exposed 1.0191 ms/cycle in radix select/sort alone. The
new native router's complete visible kernel is 0.3902 ms/cycle. The direct
route chain adds an explicit 0.2008 ms remap while reducing compact MXFP4 work
from 4.1511 to 3.9424 ms. The total portfolio improvement is the authoritative
additive result because older generic QNorm/router support operations remain
inside the historical `other_noncollective` bucket.

## Decision

The fresh profile validates the roadmap order:

1. keep the qualified 63.851301 tok/s record immutable;
2. attempt the subgroup-split gate/up M=2 MXFP4 producer with rounded BF16 SLM
   exchange;
3. require bitwise changed-input/graph exactness and at least 0.50 ms/cycle on
   the worst card and worst valid route before model integration;
4. if that gate fails, preserve it and move to a larger
   producer/reduction/consumer or specialized-decoder boundary.

No service throughput or LocalMaxxing claim is made from the eager profile.
