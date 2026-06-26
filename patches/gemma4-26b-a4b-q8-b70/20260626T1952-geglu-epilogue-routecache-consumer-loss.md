# Gemma4 GEGLU Matmul-Epilogue Route-Cache Consumer Loss

Date: 2026-06-26

## Status

Rejected after full validation. Do not promote, do not submit to
LocalMaxxing, and do not keep as the active source stack.

## Intent

The existing `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1` cache reuses host routing
metadata for the immediately following generic `MUL_MAT_ID` call. The Gemma4
GEGLU down matmul-epilogue path still copied strided `ids` back to host and
rebuilt expert counts/offsets before doing the down projection. This patch tried
to extend the same one-shot route-plan reuse into:

- `ggml_sycl_moe_selected_down_weighted_sum_matmul_epilogue`;
- `ggml_sycl_moe_geglu_down_matmul_epilogue`.

The change was metadata-only: on a strict cache hit, reuse cached `ids_host`,
`expert_row_counts`, `expert_row_offsets`, and `routed_row_src`; then clear the
cache. On miss, keep the existing dense-copy/count-sort path unchanged.

## Source Shape Tested

Source file:

```text
/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/ggml-sycl.cpp
```

Main changes tested:

- add `ggml_sycl_mul_mat_id_route_cache_matches(...)` with strict tensor/data,
  shape, stride, byte-count, and vector-size checks;
- add `ggml_sycl_build_route_slot_to_sorted_row(...)`;
- wire both matmul-epilogue down paths through the route cache hit/miss branch;
- switch the original generic `MUL_MAT_ID` route-cache hit test to the shared
  matcher.

The active test flag was:

```text
LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1
```

on top of the current record recipe:

```text
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
MTP_N_MAX=7
MTP_N_MIN=2
MTP_P_MIN=0.136
```

## Results

Screen:

```text
data/gemma4-q8-gpu2-geglu-epilogue-routecache-screen-20260626T195205Z/summary.json
```

- canary: `128/128`, pass;
- cached tokens: `[0, 0]`;
- fresh row0 after TTFT: `104.70795597094846 tok/s`;
- support mean after TTFT: `104.25250585801564 tok/s`.

Full validation:

```text
data/gemma4-q8-gpu2-geglu-epilogue-routecache-full-20260626T195349Z/summary.json
```

- canary: `1536/1536`, pass;
- cached tokens: eight rows all `0`;
- fresh row0 after TTFT: `101.8211074778421 tok/s`;
- support mean after TTFT: `102.70197770331635 tok/s`.

## Decision

Reject. The screen was variance; the full validation is below the promoted
Gemma4 Q8 one-B70 record of `103.51547512013657 tok/s`.

The result is useful only as evidence that route-plan reuse is not enough to
make the GEGLU matmul-epilogue route competitive. Future work should bias
toward a deeper small-token Gemma4 MoE fusion or an MTP acceptance/cost-curve
change, not rerunning this exact epilogue path.
