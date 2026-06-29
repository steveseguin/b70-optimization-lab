# 2026-06-29 GEGLU + VDR2 Selected-Down Screen

## Goal

Test whether the older `LLAMA_GEMMA4_MOE_FUSED_GEGLU_DOWN_WEIGHTED_SUM=1`
idea becomes useful after wiring it into the current reordered-Q8 VDR2
selected-down backend. The previous GEGLU/down fusion lost partly because it
fell back to the non-reordered selected-down path. This screen preserved the
current record stack and added a reordered GEGLU quantizer feeding the existing
VDR2 selected-down weighted-sum kernel.

## Patch

- source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/20260629-geglu-vdr2-selected-down-experiment.patch`
- source worktree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- build:
  `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`
- primary source file:
  `ggml/src/ggml-sycl/ggml-sycl.cpp`

The useful delta in the patch is:

- add `moe_geglu_quantize_row_q8_1_reorder_sycl`, which computes
  `GEGLU(gate, up)` directly into the SoA/reordered Q8_1 row layout expected by
  the VDR2 selected-down kernel;
- route `GGML_OP_MOE_GEGLU_SELECTED_DOWN_WEIGHTED_SUM` through
  `moe_selected_down_weighted_sum_q8_0_reorder_vdr2_sycl` when down weights are
  reordered and `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`;
- fix the SYCL `supports_op` predicate so reordered down weights are accepted
  for this op only when the VDR2 selected-down flag is enabled.

## Validation

Screen type: strict128 diagnostic only, fixed realistic suite, `cached_tokens=0`,
target Q8 UD-Q8_K_XL verifier, Q4_0 MTP draft, no history/ngram/cache reuse.
This is **not** eligible for LocalMaxxing submission or headline promotion.

Control lanes used the promoted VDR2 selected-down record recipe:

| label | flag | median tok/s 1-100 | p10 | mean | gate | canary |
|---|---:|---:|---:|---:|---:|---:|
| `gemma4-q8-gpu0-gegluvdr2-control-strict128-20260629T170150Z` | off | `113.75302875540123` | `105.03464546361195` | `114.22147204284018` | pass | `1024/1024` |
| `gemma4-q8-gpu1-gegluvdr2-control-strict128-20260629T170150Z` | off | `114.91893901717035` | `101.79541875617713` | `112.57128732254357` | pass | `1024/1024` |

First candidate attempt:

| label | result |
|---|---|
| `gemma4-q8-gpu2-gegluvdr2-on-strict128-20260629T170150Z` | crashed before benchmark |
| `gemma4-q8-gpu3-gegluvdr2-on-strict128-20260629T170150Z` | crashed before benchmark |

Crash cause: `GGML_OP_MOE_GEGLU_SELECTED_DOWN_WEIGHTED_SUM` was created, but
the SYCL `supports_op` predicate rejected reordered down weights, so the graph
scheduler assigned the backend-only op to CPU. CPU then aborted with:

```text
GGML_OP_MOE_GEGLU_SELECTED_DOWN_WEIGHTED_SUM is backend-only
```

After the support-predicate fix, candidate lanes passed:

| label | flag | median tok/s 1-100 | p10 | mean | gate | canary |
|---|---:|---:|---:|---:|---:|---:|
| `gemma4-q8-gpu2-gegluvdr2-onfixed-strict128-20260629T171520Z` | on | `115.16445944122788` | `104.6495356564455` | `114.93024646029782` | pass | `1024/1024` |
| `gemma4-q8-gpu3-gegluvdr2-onfixed-strict128-20260629T171520Z` | on | `113.30629123717347` | `101.6855625289027` | `112.0246191811067` | pass | `1024/1024` |

## Decision

Closed as negative / inconclusive. The fixed candidate is mechanically valid
and quality-clean, but it does not clearly beat the paired controls and remains
below the promoted full512 record `115.8466634928202 tok/s`.

Do **not** run full512 or submit this path as-is. Keep the patch default-off as
a preserved experiment artifact. If revisiting this area, use profile evidence
to target a smaller post-GEMM fusion or the LM-head verifier path; GEGLU-before-
down plus VDR2 selected-down did not produce a reliable speedup.
