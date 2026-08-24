# Ornith 1.5 35B MTP1 verifier stack

## Outcome

**RESEARCH POSITIVE; TARGET-ONLY PACKAGE UNCHANGED.** Stacking the exact
multi-row residual/RMS verifier fusion with the two-row ordered MoE reduction
produced a repeatable CLI gain and a strong fresh-server A/B/B/A result. The
assisted lane is still far below the then-current target-only result: a
`129.568 tok/s` legacy 100-event compatibility mean, corresponding to the
preferred conventional `128.272782 tok/s` mean. This is an optimization
substrate for further MTP work, not a user default.

## Stack

The candidate enables:

```text
GGML_SYCL_FUSED_ORNITH_SPEC_RESIDUAL_RMS=1
GGML_SYCL_FUSED_ORNITH_SPEC_MOE_ADD_REDUCE=1
```

Both paths are default-off and fail closed outside their exact small-row
shapes. Residual/RMS assigns an independent workgroup to each row; the MoE path
keeps weighted products graph-visible and preserves the seven sequential FP32
expert additions independently for each verifier token.

## Same-binary exactness and CLI timing

All A/B/B/A extracted transcripts had SHA-256
`0f162aebc81f0a28ffd82704b20729ca4dc71b929644c5803639a3ad40828a2e`.
Each candidate recorded 3,402 two-row MoE reductions, 3,524 total
residual/RMS hits, and 3,360 shared-MoE residual/RMS hits.

| arm | generation tok/s |
| --- | ---: |
| control A1 | 64.9 |
| candidate B1 | 67.5 |
| candidate B2 | 67.1 |
| control A2 | 65.3 |

Means improved `65.10 -> 67.30 tok/s` (**+3.38%**), with both candidates above
both controls.

## Fresh-server interaction test

Every arm used the fixed 12-prompt suite once per prompt with cold responses,
512 output tokens, `cached_tokens=0`, and all freshness/finality gates passing.

| arm | median tok/s | mean tok/s | accepted / drafts |
| --- | ---: | ---: | ---: |
| control A1 | 78.502 | 77.807 | 2,234 / 3,890 |
| candidate B1 | 80.604 | 81.165 | 2,242 / 3,882 |
| candidate B2 | 83.302 | 82.084 | 2,243 / 3,881 |
| control A2 | 79.422 | 77.640 | 2,194 / 3,931 |

Pooling 24 rows per condition gives median `79.422 -> 82.483` (**+3.85%**) and
mean `77.723 -> 81.624` (**+5.02%**). Candidate prompt-paired averages won
11/12, and both candidate runs exceeded both controls on median and mean.

Pooled draft acceptance also rose `56.62% -> 57.77%` (+1.16 percentage
points). This may explain part of the end-to-end improvement, so the server
delta is reported as measured rather than treated as a pure kernel-time gain.
The same-binary exact-output CLI result supplies the independent kernel signal.

## Decision and artifacts

Retain
`../patches/llamacpp-ornith15-mtp1-verifier-stack-research-positive-20260823.patch`
as the preferred MTP1 research base. Do not add the flags to the target-only
package. Structured results are in
`../data/2026-08-23-ornith35b-mtp1-verifier-stack-summary.json`; raw CLI,
server, and metrics artifacts share the `2026-08-23-ornith35b-mtp1-stack-`
prefix.
