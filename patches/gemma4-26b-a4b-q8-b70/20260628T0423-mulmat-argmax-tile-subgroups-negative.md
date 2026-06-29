# 2026-06-28T0423 - MUL_MAT_ARGMAX tile-subgroup tuning negative

## Patch Tested

Source tree:
`/home/steve/src/llama.cpp-gemma-record-repro-c926`

Added a default-off tuning knob for the SYCL fused verifier LM-head argmax
path:

- `ggml/src/ggml-sycl/mmvq.cpp`
  - added parser for `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS`;
  - allowed valid subgroup counts `1`, `2`, `4`, `8`, `16`, `32` up to
    `WARP_SIZE`;
  - replaced the hardcoded `num_subgroups = WARP_SIZE` in the four
    `mul_mat_vec_q_argmax*` launchers with the parsed value.
- `ggml/src/ggml-sycl/mmvq.hpp`
  - declared `ggml_sycl_mul_mat_vec_q_argmax_tile_subgroups()`.
- `ggml/src/ggml-sycl/ggml-sycl.cpp`
  - sized `GGML_OP_MUL_MAT_ARGMAX` scratch by
    `ceil_div(nrows, ggml_sycl_mul_mat_vec_q_argmax_tile_subgroups())`.
- `scripts/run-gemma4-26b-first-baseline.sh` and
  `scripts/run-gemma4-26b-llamacpp-replica.sh`
  - passed the env through and recorded
    `llama_sycl_mul_mat_argmax_tile_subgroups` in summaries.

The patch is intended to preserve exact verifier semantics. It only changes
tile geometry/scratch sizing for the already-default-off fused verifier
argmax path.

## Result

Strict 128-token four-lane screen, stamp `20260628T042332Z`.

All lanes:

- fixed realistic suite;
- each prompt once;
- `cached_tokens=0`;
- UD-Q8_K_XL target/verifier, Q4_0 MTP draft;
- `MAX_TOKENS=128`, metric tokens 1-100 after TTFT.

| Lane | Summary | Median 1-100 | p10 | Full128 |
| --- | --- | ---: | ---: | ---: |
| control | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-argmaxtile-control-128-20260628T042332Z/summary.json` | `98.4448` | `85.7686` | `95.7296` |
| fused argmax default | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-argmaxtile-fused-default-128-20260628T042332Z/summary.json` | `88.7342` | `76.8173` | `89.3138` |
| fused argmax, tile subgroups 8 | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-argmaxtile-fused-tile8-128-20260628T042332Z/summary.json` | `84.3517` | `77.6629` | `83.5912` |
| fused argmax, tile subgroups 4 | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-argmaxtile-fused-tile4-128-20260628T042332Z/summary.json` | `82.4487` | `75.4398` | `85.0958` |

## Decision

Reject for promotion.

The current fused verifier LM-head argmax path is slower than the existing
backend-argmax-IDs route, and reducing tile subgroups makes it worse. Keep this
as a durable default-off experiment artifact, but do not include it in the
headline recipe or submit it to LocalMaxxing. Future LM-head work should use a
different design rather than tuning this two-stage fused argmax kernel.
