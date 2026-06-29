# 2026-06-28T0409 - Q8 reordered MoE rowpack launcher negative

## Patch Tested

Source tree:
`/home/steve/src/llama.cpp-gemma-record-repro-c926`

Added a default-off row-packed launcher for the existing reordered Q8_0
multi-token MoE verifier kernel:

- `ggml/src/ggml-sycl/mmvq.cpp`
  - added `launch_mul_mat_vec_q_moe_multi_token_reorder_rowpack()`;
  - added exported wrapper
    `ggml_sycl_mul_mat_vec_q_id_multi_token_reorder_rowpack()`;
  - supported `rows_pack=2` and `rows_pack=4` only;
  - Q8_0 only.
- `ggml/src/ggml-sycl/mmvq.hpp`
  - declared the wrapper.
- `ggml/src/ggml-sycl/ggml-sycl.cpp`
  - added env parser:
    `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_ROWPACK=2|4`;
  - dispatched before the generic reordered path for
    `src0=Q8_0`, reordered weights, `ne11 == 1`, `n_experts_used <= 8`;
  - updated graph eligibility to require reordered Q8_0 state.
- `scripts/run-gemma4-26b-first-baseline.sh` and
  `scripts/run-gemma4-26b-llamacpp-replica.sh`
  - added the env to pass-through, server log, and summary identity.

The math was intentionally unchanged: same route IDs, same reordered Q8 dot
product body, same accumulation order. Only launch geometry changed from
`GGML_SYCL_MMV_Y` rows per workgroup to
`GGML_SYCL_MMV_Y * rows_pack`.

## Result

Strict full512 four-lane run, stamp `20260628T040900Z`.

All lanes:

- fixed realistic suite;
- each prompt once;
- `cached_tokens=0`;
- canary `128/128`;
- UD-Q8_K_XL target, Q4_0 MTP draft;
- `MAX_TOKENS=512`, metric tokens 1-100 after TTFT.

| Lane | Summary | Median 1-100 | p10 | Full512 |
| --- | --- | ---: | ---: | ---: |
| control | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-rowpack-control-full512-20260628T040900Z/summary.json` | `93.7177` | `88.2419` | `91.6172` |
| rowpack=2 | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-rowpack2-full512-20260628T040900Z/summary.json` | `95.9153` | `87.7989` | `90.4440` |
| rowpack=4 | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-rowpack4-full512-20260628T040900Z/summary.json` | `92.9105` | `88.0608` | `90.7530` |
| rowpack=2 + unroll6/p_min=0.0300 | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-rowpack2-u6-pmin0030-full512-20260628T040900Z/summary.json` | `89.8947` | `86.6188` | `90.3944` |

## Decision

Reject for promotion.

`ROWPACK=2` is valid and not a correctness risk in this screen, but it did not
materially beat the promoted `95.8245 tok/s` strict result and hurt full512.
`ROWPACK=4` regressed. Keep the patch default-off as a durable experiment
artifact; do not submit to LocalMaxxing or include in the headline recipe.
