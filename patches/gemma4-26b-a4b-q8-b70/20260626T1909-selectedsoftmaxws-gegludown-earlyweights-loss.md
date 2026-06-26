# 20260626T1909 Selected-Softmax-Weighted-Sum GEGLU Down Early-Weights Loss

## Status

Valid negative. Preserve the patch idea and result so the GEGLU selected-down
family is not retried under the assumption that it only lost because selected
softmax weights were unavailable early.

## Patch Shape

Source worktree:
`/home/steve/src/llama.cpp-gemma-record-stack`.

Touched file:

- `src/llama-graph.cpp`

Behavior:

- introduce `use_selected_softmax_for_fused_geglu_down`;
- when `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1` and either
  `LLAMA_GEMMA4_MOE_FUSED_GEGLU_DOWN_WEIGHTED_SUM=1` or
  `LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1` is requested, build
  `weights = ggml_moe_selected_softmax(...)` before the GEGLU/down block;
- skip the later generic softmax normalization for those already-selected
  softmax weights;
- leave the default/current record path unchanged unless the combined
  selected-softmax-weighted-sum and fused GEGLU flags are explicitly enabled.

## Validation

Run:

- `data/gemma4-q8-gpu0-selectedsoftmaxws-gegludown-earlyweights-routecache-screen-20260626T190911Z/summary.json`

Config deltas from the current record family:

- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1`
- `LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`

Result:

- canary: `128/128`, pass;
- fresh row0 after TTFT: `100.92860408939487 tok/s`;
- supporting mean after TTFT: `100.88521816690852 tok/s`;
- row0 wall: `88.30958095057842 tok/s`;
- cached tokens: `[0, 0]`;
- current record: `103.30108468098005 tok/s`;
- previous material baseline: `103.2992004295621 tok/s`.

## Interpretation

The patch makes the intended early GEGLU selected-down path reachable and keeps
correctness, but it is still slower than the current record family. The problem
is not just that selected-softmax weights were missing; the selected-down
matmul-epilogue backend itself remains slower than the existing target/verifier
MoE decomposition for this shape.

Do not promote. Future Gemma work should move to a materially different
target/verifier design, such as graph-level multi-token assistant unroll,
shape-specific verifier MoE kernels, or an exact verifier shortcut, rather than
another GEGLU selected-down wrapper.
