# 2026-07-03 INT8 chunked top-1 argmax verifier no-win

This experiment tested whether the Qwen27 INT4 AutoRound + runtime INT8
LM-head lane could avoid materializing full verifier logits by computing only
top-1 token IDs.

## Patch

Patch artifact:
`patches/qwen36-27b-autoround-int4-b70/vllm-int8-chunked-top1-argmaxonly-no-win-20260703.patch`

Default-off flags:

- `VLLM_XPU_LM_HEAD_INT8=1`;
- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1`;
- `VLLM_XPU_LOCAL_ARGMAX_SPEC_ONLY=1`;
- `VLLM_XPU_SPEC_DECODE_ARGMAX_ONLY=1`;
- `VLLM_XPU_LM_HEAD_INT8_CHUNKED_TOP1=1`;
- `VLLM_XPU_LM_HEAD_INT8_TOP1_CHUNK_SIZE=65536`.

The patch added a diagnostic `LogitsProcessor._get_top_tokens_int8_chunked`
path. It quantized hidden states once with the existing runtime INT8 helper,
then looped over vocabulary chunks, called the existing oneDNN
`int8_gemm_w8a8` op for each chunk, and reduced each chunk to top-1 token IDs.
The sampler side reused exact greedy speculative semantics: accepted draft
prefix, target replacement on first mismatch, and target-owned bonus token on
full accept.

This was intentionally not a final fused kernel. It was a cheap screen for
whether "avoid full logits" is enough if implemented as multiple existing GEMM
calls.

## Result

Command shape:

```bash
LABEL=qwen27-int8lmhead-chunkedtop1-argmaxonly-c65536-mtp3-cg8-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LOCAL_ARGMAX_DECODE=1 \
VLLM_XPU_LOCAL_ARGMAX_SPEC_ONLY=1 \
VLLM_XPU_SPEC_DECODE_ARGMAX_ONLY=1 \
VLLM_XPU_LM_HEAD_INT8_CHUNKED_TOP1=1 \
VLLM_XPU_LM_HEAD_INT8_TOP1_CHUNK_SIZE=65536 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result JSON:
`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-chunkedtop1-argmaxonly-c65536-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T161906Z.json`

Strict fresh gate:

- `realistic_final_gate.passed=true`;
- `cached_tokens=0` for all 12 prompts;
- each prompt run once as a cold response;
- median `61.40954015865033 tok/s`;
- p10 `57.087468100403065`;
- mean `61.81715483975767`;
- TTFT median `609.1641605016775 ms`.

Current record for this quality lane remains the runtime INT8 LM-head row at
`62.62792826965406 tok/s`, with same-window support at
`62.276492398420544 tok/s`.

## Decision

No-win. The run is valid and quality-policy compliant, but it is slower than
the current strict record.

Interpretation: repeatedly launching chunked oneDNN GEMMs costs more than
materializing the full logits with the current INT8 LM-head path. This result
does **not** close the exact compact-verifier idea; it closes the cheap
Python/chunked implementation. A useful version must be a real fused
matmul-plus-top1/reduction kernel or an upstream verifier design that avoids
extra GEMM launches and avoids producing `[rows, vocab]` logits.

Do not keep this diagnostic patch active. Preserve it only as evidence that the
next verifier lane must be fused, not chunked through existing oneDNN calls.
