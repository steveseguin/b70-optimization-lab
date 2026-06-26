# llama.cpp Gemma 4 Selected-Softmax Weighted-Sum Prototype

Source tree:
`/home/steve/src/llama.cpp-gemma-record-stack`

Build target:
`build-sycl-b70-aot-bmg-g31/bin/llama-server`

## Patch Summary

Added a dormant Gemma4-focused ggml op:
`GGML_OP_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM`, enabled only when
`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1`.

The op consumes:

- down-projection expert outputs (`[n_embd, n_expert_used, n_tokens]`);
- router logits for selected experts;
- selected expert IDs.

It computes the selected softmax weights and weighted sum in one backend op,
replacing the separate selected-softmax materialization + weighted-sum op in the
guarded Gemma4 small-token path.

Touched source areas:

- `ggml/include/ggml.h`: op enum and public constructor;
- `ggml/src/ggml.c`: op name/symbol and constructor;
- `ggml/src/ggml-backend-meta.cpp`: backend metadata split handling;
- `ggml/src/ggml-cpu/ops.{h,cpp}` and `ggml/src/ggml-cpu/ggml-cpu.{c,cpp}`:
  CPU fallback / dispatch;
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: SYCL implementation and dispatch;
- `src/llama-graph.cpp`: guarded Gemma4 graph branch controlled by
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM`.

Default behavior is unchanged when the env var is unset.

## Validation

Run:
`gemma4-q8-gpu0-selectedsoftmax-weightedsum-fusedagg-pmin0136-screen-20260626T161913Z`

Summary:
`data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-fusedagg-pmin0136-screen-20260626T161913Z/summary.json`

Result:

- canary: `512/512`, pass;
- cached-token validity: all bench rows reported `cached_tokens=0`;
- fresh headline row0: `100.3584163628206 tok/s` after TTFT;
- current valid record: `103.2992004295621 tok/s` after TTFT.

Decision: **valid negative**. Do not promote as a record or submit to
LocalMaxxing. Keep as a useful failed patch because it rules out final
aggregation-only fusion as the next high-value path.

## Follow-Up

The isolated final aggregation op is too small a lever. Future Gemma work should
target one of:

- a deeper single-output small-token Gemma4 MoE op that fuses selected routing,
  gate/up, GEGLU, down projection, and weighted sum under tight Q8/Gemma4
  guards;
- MTP acceptance improvements that increase fresh accepted tokens per step
  without relying on repeated-output history or warmed continuation cache.
