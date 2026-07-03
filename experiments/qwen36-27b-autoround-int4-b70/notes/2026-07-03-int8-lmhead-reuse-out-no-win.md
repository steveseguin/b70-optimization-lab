# 2026-07-03 - INT8 LM-head Output-Reuse Experiment

## Goal

Test whether removing per-call output allocations from the experimental XPU
INT8 LM-head path improves the strict fresh-response Qwen3.6 27B INT4
AutoRound record without changing model quality or benchmark validity.

Current valid record before this experiment:

- `VLLM_XPU_LM_HEAD_INT8=1`, MTP3, graph capture size 8.
- Median tokens 1-100 after TTFT: `62.62792826965406 tok/s`.
- Fresh-response gate: fixed realistic suite, each prompt once,
  `cached_tokens=0`.
- Full quality gate had already passed for the promoted INT8 LM-head path.

## Patch

The experiment keeps the same INT8 math and changes only allocation behavior:

- `vllm/model_executor/layers/vocab_parallel_embedding.py`
  - adds `VLLM_XPU_LM_HEAD_INT8_REUSE_OUT=1`;
  - preallocates/caches per-shape INT8 quant buffer, scale buffer, and BF16
    output buffer;
  - calls output-form custom ops on the INT8 LM-head path.
- `vllm-xpu-kernels/csrc/xpu/onednn/onednn_matmul.cpp`
  - avoids allocating a temporary expected output tensor inside
    `int8_gemm_w8a8_out` shape validation.

Patch snapshots:

- `patches/qwen36-27b-autoround-int4-b70/vllm-active-state-before-lmhead-reuseout-20260703T142734Z.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-active-state-before-lmhead-reuseout-20260703T142734Z.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-lmhead-int8-reuseout-no-promote-20260703.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-int8-gemm-out-shape-no-promote-20260703.patch`

## Build Note

The first rebuild accidentally used oneAPI 2026.0 and produced extensions
requiring `libsycl.so.9`, while the active vLLM/XPU runtime is aligned to
`libsycl.so.8`. Import failed with:

```text
ImportError: libsycl.so.9: cannot open shared object file
```

Fix:

- rebuild the changed `_xpu_C` extension with oneAPI compiler `2025.3`;
- replace stale package shared objects with sycl8-compatible artifacts;
- restore FA2 `_vllm_fa2_C.abi3.so` and `libattn_kernels_xe_2.so` from the
  known sycl8 digest backup at
  `/home/steve/src/vllm-xpu-kernels-digest-sycl8-20260612dj/`.

Smoke after repair:

```text
ops True True True
```

Meaning: `per_token_quant_int8_xpu_out`, `int8_gemm_w8a8_out`, and FA2
`varlen_fwd` were registered.

## Strict Fresh-Response Run

Command:

```bash
cd /home/steve/llm-optimizations
export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/opt/intel/oneapi/compiler/2025.3/lib:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
LABEL=qwen27-int8lmhead-reuseout-mtp3-cg8-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_REUSE_OUT=1 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result file:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-reuseout-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T155846Z.json`

Validity:

- `realistic_final_gate.passed`: `true`
- `fresh_response_validity.valid`: `true`
- `cached_tokens_all_zero`: `true`
- prompt suite: `qwen36-27b-autoround-int4-b70-realistic-v1`
- each prompt run once; no repeated/warmed prompt averaging.

Metrics:

- median tokens 1-100 after TTFT: `62.427810578115064 tok/s`
- p10 tokens 1-100 after TTFT: `58.00195927577769 tok/s`
- mean tokens 1-100 after TTFT: `63.21019065875485 tok/s`
- median full after-TTFT: `61.98787071746436 tok/s`
- median wall full: `47.60353640367893 tok/s`
- median TTFT: `605.8728314819746 ms`

## Decision

No promotion and no LocalMaxxing submission.

The run is valid but does not beat the current `62.62792826965406 tok/s`
record. The delta is within normal run-to-run variance. The output-reuse path
is not worth carrying as a promoted production optimization unless a later
experiment shows it enables another larger change.

## Follow-Up

The dominant verifier cost remains the LM-head computation itself, not Python
allocation overhead. Next useful lanes:

1. Exact candidate-vs-max / compact argmax verifier path that avoids materializing
   all vocab logits for verification.
2. Head-only bonus-token path that preserves the bonus pipeline while reducing
   target LM-head rows.
3. Row-adaptive verifier output rows, if the current vLLM verifier plumbing can
   be made to consume compact outputs without changing correctness.
