# Ornith 1.5 35B two-row MTP recurrent alpha-gate

## Outcome

**EXACT, PERFORMANCE NEUTRAL; DO NOT PROMOTE.** The accepted one-token
Qwen/Ornith `alpha + bias -> softplus -> multiply by ssm_a` fusion was
extended to exactly two MTP1 verifier tokens. It preserved the canonical
transcript and fired in every recurrent verifier layer, but did not improve
mirrored generation throughput.

## Candidate

The default-off `GGML_SYCL_FUSED_ORNITH_SPEC_ALPHA_GATE=1` path requires an
exact contiguous 64-element FP32 alpha tensor. The 32-element bias and
`ssm_a` operands must be graph-valid broadcasts. The fused kernel uses those
same repeat periods and, as in the accepted one-row path, materializes and
rereads the rounded FP32 ADD output before applying softplus and multiplication.

All four fixed-seed 128-token transcripts had SHA-256
`0f162aebc81f0a28ffd82704b20729ca4dc71b929644c5803639a3ad40828a2e`.
Each candidate recorded exactly 2,490 two-row alpha-gate hits.

## Measurements

| arm | generation tok/s |
| --- | ---: |
| control A1 | 65.0 |
| candidate B1 | 64.3 |
| candidate B2 | 65.6 |
| control A2 | 65.1 |

Arm means were `65.05 -> 64.95 tok/s` (**-0.15%**). The pairwise outcomes
split, so the result is neutral rather than evidence of a regression. The
fusion removes two generic launches in each of 30 recurrent layers per
two-row verifier cycle, but that launch reduction was not measurable in
end-to-end generation.

## Decision

Retain
`../patches/llamacpp-ornith15-mtp2row-alpha-gate-neutral-20260823.patch`
as exact negative research. Do not run a fresh-server promotion screen, enable
the speculative flag by default, or change the preferred MTP1 research stack
or target-only package.

