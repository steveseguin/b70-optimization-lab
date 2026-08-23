# Ornith 1.5 35B two-row MTP routed gate/up + GLU

## Outcome

**DO NOT PROMOTE.** Two forms of the Qwen-derived one-row routed gate/up fusion
were tested on Ornith's exact two-row MTP1 target verifier. The fast form
changed arithmetic and failed deterministic validation. The arithmetic-exact
form removed the standalone GLU launch but was neutral in mirrored timing.

## Aggressive form: correctness negative

The first active matcher extended the accepted one-row Q4_K MMVQ gate/up
kernel to two tokens. It fired 3,400 times and measured `81.6 tok/s` versus
`65.2 tok/s` for its adjacent control, but its generated transcript SHA-256 was
`7d8012316f06b5b9eeeca11379c6bde9a16ad604598110afdb9d577bc25c5289`
instead of the control's canonical
`0f162aebc81f0a28ffd82704b20729ca4dc71b929644c5803639a3ad40828a2e`.
The apparent speedup is invalid.

Source inspection explained the divergence. Stock two-row
`ggml_sycl_mul_mat_id` sorts routed rows by expert. Experts receiving one row
use direct-FP32 DMMV, while the candidate forced every projection through the
one-row Q8 MMVQ path. That is an arithmetic change, not an exact launch fusion.

## Conservative form: exact but neutral

The retained research patch executes both stock `MUL_MAT_ID` projections
unchanged and folds SWIGLU into the up projection's final routed-row scatter.
It therefore preserves expert sorting and the stock DMMV/MMVQ selection while
removing one generic GLU launch per layer.

All four fixed-seed 128-token transcripts had the canonical SHA-256 above.
Each candidate recorded exactly 3,320 two-row fusion hits.

| arm | generation tok/s |
| --- | ---: |
| control A1 | 65.5 |
| candidate B1 | 64.4 |
| candidate B2 | 65.9 |
| control A2 | 63.7 |

The arm means were `64.60 -> 65.15 tok/s` (+0.85%). The first pair regressed
and the second improved; the small aggregate difference is within observed
run-order noise. A heavier scatter kernel erased the expected value of
removing the tiny standalone GLU launch, so no fresh-server screen was
justified.

## Decision

Retain
`../patches/llamacpp-ornith15-mtp2row-glu-scatter-neutral-20260823.patch`
and the raw CLI evidence as negative research. Do not enable
`GGML_SYCL_FUSED_ORNITH_SPEC_MOE_GATE_UP`, do not change the preferred MTP1
research stack, and do not change the 129.568 tok/s target-only package.

