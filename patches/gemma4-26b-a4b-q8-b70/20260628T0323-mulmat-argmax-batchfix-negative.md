# 2026-06-28T0323 - `MUL_MAT_ARGMAX` batch-size scheduler patch negative

## Patch Tested

Changed `get_op_batch_size()` in
`/home/steve/src/llama.cpp-gemma-record-repro-c926/ggml/src/ggml-sycl/ggml-sycl.cpp`
so `GGML_OP_MUL_MAT_ARGMAX` returned the hidden-row count from
`op->src[1]->ne[1]` rather than falling through to default behavior.

The intent was to fix a suspected scheduling mismatch for
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1`.

## Result

Strict 128-token four-lane screen, stamp `20260628T032313Z`:

- Controls:
  - GPU0 median100 `95.7611`
  - GPU2 median100 `98.8722`
- Fused verifier argmax lanes:
  - GPU1 median100 `87.8123`
  - GPU3 median100 `82.9537`

All lanes passed correctness and had `cached_tokens=0`, but fused verifier
argmax remained materially slower than the current verifier backend argmax IDs
path.

## Decision

Reject and revert. Do not use
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` for the current Gemma 26B Q8 strict
lane. The patch was removed from source after the screen.

Supporting details are recorded in:

- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md`
- `data/gemma4-q8-gpu*-strict-vdr2-f16p021-*-20260628T032313Z/summary.json`

