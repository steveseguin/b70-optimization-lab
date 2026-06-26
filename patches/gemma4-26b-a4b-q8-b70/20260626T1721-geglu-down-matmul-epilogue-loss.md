# Gemma4 26B Q8: GEGLU Down Matmul-Epilogue Prototype Loss

Date: 2026-06-26

Scope: `/home/steve/src/llama.cpp-gemma-record-stack`

## Intent

Try an intermediate Gemma4 MoE fusion for verifier-sized MTP rows:

1. use `GGML_OP_MOE_GEGLU_SELECTED_DOWN_WEIGHTED_SUM`;
2. compute routed GEGLU rows into a contiguous scratch buffer;
3. reuse the existing per-expert Q8_0 `mul_mat` schedule;
4. fuse route scatter, optional down-scale, and weighted-sum epilogue.

The goal was to beat the valid fresh-response record:
`103.2992004295621 tok/s`.

## Code Shape

Main touched areas:

- `src/llama-graph.cpp`
  - new env gate: `LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE`;
  - emits `ggml_moe_geglu_selected_down_weighted_sum()` without enabling the
    older direct fused GEGLU-down path.
- `ggml/src/ggml-sycl/ggml-sycl.cpp`
  - new SYCL helper for GEGLU down matmul epilogue;
  - placement support for `GGML_OP_MOE_GEGLU_SELECTED_DOWN_WEIGHTED_SUM`;
  - graph scratch guard and batch-size handling for the new backend-only op;
  - diagnostic env: `LLAMA_GEMMA4_MOE_GEGLU_SUPPORT_DEBUG`.

Important implementation lesson: the routed expert `ids` tensor is a strided
view in real warmup graphs (`ne=[8,2]`, `nb=[4,512]`), not contiguous. The
helper must not assume `ggml_is_contiguous(ids)`. The working prototype copies
the covered device span, packs dense host ids for route sorting/profile
accounting, and keeps the original device ids plus original strides for the
final device epilogue.

## Validation Result

Run:

`data/gemma4-q8-gpu0-geglu-down-matmul-epilogue-short-pmin0136-20260626T172132Z/summary.json`

Identity:

- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- GPU: single B70, `GPU_INDEX=0`
- MTP: `n_max=7`, `n_min=2`, `p_min=0.136`
- record flags preserved: q-only MTP inputs, backend argmax ids, deferred
  target `h_nextn`, selected-softmax, weighted-sum, graph on, VMM off.
- experiment flag: `LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1`

Outcome:

- canary: `32/32` repeats, `128` rows, pass;
- benchmark cached tokens: `[0, 0, 0, 0]`;
- fresh row0: `46.15915016610455 tok/s` after TTFT;
- repeated-row mean: `47.29437104441836 tok/s` after TTFT, support-only.

## Decision

Loss. Do not promote and do not submit to LocalMaxxing.

The route-pack plus per-expert matmul decomposition is correct enough for the
screen, but it is far slower than the current `103.299 tok/s` fresh record.
Future work should skip this exact decomposition and either:

- build a deeper single-output Gemma4 small-token MoE op that fuses router
  selection, selected-softmax, gate/up, GEGLU, down, and weighted sum together;
  or
- improve MTP acceptance/cost outside the MoE block.
