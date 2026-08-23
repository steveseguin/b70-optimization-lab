# Ornith 1.5 35B-A3B: embedded MTP and verifier fusion screen

Date: 2026-08-23 EDT

Status: **research retained; user package remains target-only**

## Why this was tested

Ornith 1.5 is retrained from the Qwen family and retains Qwen-derived MoE,
Gated Delta Net, and embedded next-token-prediction structure. That makes our
Qwen verifier and recurrent-kernel work the right source of hypotheses, while
still requiring independent Ornith exactness and throughput gates.

The model declares one embedded next-token-prediction layer. llama.cpp can use
it through `--spec-type draft-mtp`, so this screen tested MTP depth and then
ported two already-proven one-row fusion boundaries to the verifier's small
multi-row shape.

## Embedded MTP is not yet a deployment win

All server rows used the fixed 12-prompt realistic suite, one cold response per
prompt, 512 generated tokens, `cached_tokens=0`, and the tokens 1-100 after
TTFT metric.

| Lane | Median tok/s | Draft acceptance | Decision |
| --- | ---: | ---: | --- |
| Accepted target-only package | **117.446** | n/a | keep |
| Embedded MTP3 | 52.427 | 2,462 / 10,976 = 22.43% | reject |
| Embedded MTP1, first control | 79.074 | 2,232 / 3,893 = 57.33% | diagnostic only |

The embedded predictor is functional, but verifier cost overwhelms the saved
target work. MTP3 is especially poor because its acceptance falls sharply.

## Small-row residual/RMS verifier fusion

The first Qwen-derived transfer extends the accepted residual-add/RMSNorm/mul
and shared-MoE-add/residual/RMSNorm/mul kernels from one row to independent
2-4 row verifier batches. It is default-off behind
`GGML_SYCL_FUSED_ORNITH_SPEC_RESIDUAL_RMS=1`.

A forced greedy 128-token control/candidate comparison on one frozen binary was
byte-identical (`6a91ba76...`). The candidate recorded 3,524 residual/RMS hits
and 3,360 shared-residual/RMS hits, versus 81 and zero in the control.

The full mirrored server order was candidate/control/control/candidate:

| Arm | Run medians, tok/s | Run means, tok/s |
| --- | --- | --- |
| Control | 74.652, 78.429 | 75.188, 78.065 |
| Candidate | 80.622, 77.355 | 79.373, 76.895 |

Across all 24 rows per arm, the grand prompt mean improved
`76.627 -> 78.134 tok/s` (**+1.97%**), with the candidate ahead on 8/12
prompt-level paired averages. The mean of the two run medians improved 3.20%.
This is a modest verifier-path positive, not the 8% suggested by the first
screen.

It is retained as research only: even the improved MTP1 lane is far below the
117.446 tok/s target-only package.

## Small-row GDN RMS/gate transfer

The second transfer extends the accepted per-head GDN
RMSNorm/weight/SiLU/gate kernel across independent verifier tokens behind
`GGML_SYCL_FUSED_ORNITH_SPEC_GDN_RMS_GATE=1`. Two control and two candidate
forced-greedy runs were all byte-identical (`6a91ba76...`), and each candidate
recorded 2,520 hits.

Mirrored generation rates were `64.3, 64.2 tok/s` for control and
`64.4, 64.1 tok/s` for candidate. Both means are exactly **64.25 tok/s** at
the reported precision. The path is exact but neutral, so no server suite was
run and the flag is rejected.

## Determinism clarification

Fresh-process prose hashes are not a valid candidate-specific oracle on this
runtime: the stock SYCL path already varies across processes, as documented in
the first Ornith MoE fusion. A repeated realistic prompt also exposed more
variation than the existing short `red, blue, green, yellow` canary. Future
Ornith gates should retain the short semantic battery but add a realistic
same-process repeat case; shallow exact-answer stability must not be described
as general transcript determinism.

Candidate correctness here therefore uses the established same-frozen-binary,
forced-greedy on/off comparison plus exact activation counts. Performance uses
mirrored fresh processes and never derives throughput from serialized op
timings.

## Artifacts and package decision

The combined default-off research source is preserved as
`../patches/llamacpp-ornith15-embedded-mtp-verifier-fusions-research-20260823.patch`.
Raw server JSON, metrics, forced-output records, and the structured summary are
under `../data/2026-08-23-ornith35b-embedded-*`.

Neither flag is included in the user recipe. The source and build were restored
to the accepted nine-feature target-only stack after capture.
