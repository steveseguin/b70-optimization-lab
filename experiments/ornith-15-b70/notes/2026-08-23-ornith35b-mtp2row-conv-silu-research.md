# Ornith 1.5 35B two-row MTP convolution + SiLU

## Outcome

**EXACT, SMALL POSITIVE SIGNAL; NOT PROMOTED.** The accepted one-token
Qwen/Ornith recurrent convolution + SiLU fusion was extended to exactly two
MTP1 verifier tokens. It preserved the canonical transcript and activated in
every recurrent verifier layer. Mirrored means were positive both in isolation
and on the preferred verifier stack, but pairwise outcomes split and the
marginal signal did not meet the fresh-server promotion gate.

## Candidate and arithmetic

The default-off `GGML_SYCL_FUSED_ORNITH_SPEC_CONV_SILU=1` path requires the
exact two-token convolution shape: 8,192 channels, four taps, and five
contiguous source values per channel (three history values plus two current
tokens). Token 0 consumes source offsets 0-3 and token 1 consumes offsets 1-4,
matching stock `SSM_CONV`. The original FP32 accumulation loop and SiLU
expression are preserved; only the raw convolution output and standalone SiLU
launch are elided.

All eight fixed-seed 128-token transcripts across both screens had SHA-256
`0f162aebc81f0a28ffd82704b20729ca4dc71b929644c5803639a3ad40828a2e`.
Each candidate recorded exactly 2,490 two-row convolution/SiLU hits.

## Isolated screen

| arm | generation tok/s |
| --- | ---: |
| control A1 | 63.4 |
| candidate B1 | 65.1 |
| candidate B2 | 64.9 |
| control A2 | 65.3 |

Arm means were `64.35 -> 65.00 tok/s` (+1.01%). The pairwise outcomes split.

## Marginal screen on the preferred MTP1 stack

Both arms enabled the exact two-row residual/RMS and ordered-MoE fusions. Only
the convolution flag differed.

| arm | generation tok/s |
| --- | ---: |
| stack control A1 | 66.8 |
| stack + convolution B1 | 67.7 |
| stack + convolution B2 | 67.2 |
| stack control A2 | 67.4 |

Arm means were `67.10 -> 67.45 tok/s` (+0.52%). Candidate B2 did not beat the
closing control, so the result is not order-resistant enough to justify a
fresh-server suite.

## Decision

Retain
`../patches/llamacpp-ornith15-mtp2row-conv-silu-research-20260823.patch`
as an exact, stackable research candidate. Do not enable it by default, call it
a validated serving gain, or change the preferred MTP1 stack or 129.568 tok/s
target-only package. Revisit only with a lower-noise protocol or as part of a
larger exact recurrent verifier fusion.

