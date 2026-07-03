# 2026-07-03 - fused verifier/top-1 LM-head design blocker

## Purpose

After the BF16-scale runtime INT8 LM-head record, close the remaining
configuration branch and decide whether the next verifier/top-1 optimization is
implementable with existing primitives or requires new native XPU work.

Current valid headline record for this lane:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- mode: AutoRound INT4 W4A16 + runtime INT8 LM-head with BF16 scales;
- env: `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`, scope default `all`;
- strict fresh median tokens 1-100 after TTFT:
  `65.27648650325429 tok/s`;
- quality: `pass_all=true`, `baseline_match_all=true`, repeat32 and 1K needle
  passed.

## Closed follow-up branch

The same-window scale/scope screen after the record did not produce a headline
win:

- BF16-scale controls: `64.971` and `64.738 tok/s`;
- FP16 scales: `62.902 tok/s`, no-win;
- webhie target-only BF16 scales: `64.800 tok/s`, lower TTFT, but quality
  repeat32 failed once (`blue, green, red` instead of
  `blue, green, red, yellow`), so it is not promotable.

See:

```text
experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-scale-scope-followup-no-headline-win.md
```

## What the source currently does

The “local argmax”/`get_top_tokens()` path is still not a fused LM-head top-1.
It avoids all-gathering full logits across TP, but on this one-GPU TP1 lane it
still materializes full local logits first:

```text
/home/steve/src/vllm/vllm/model_executor/layers/logits_processor.py
  get_top_tokens() -> lm_head.quant_method.apply(...) -> dense [rows, vocab] logits
  -> logits.max/argmax/reduce

/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py
  _greedy_sample() -> model.get_top_tokens(hidden_states) when enabled,
  otherwise model.compute_logits(hidden_states).argmax(dim=-1)

/home/steve/src/vllm/vllm/v1/sample/rejection_sampler.py
  greedy verification consumes target logits and runs target_logits.argmax(...)
```

The active runtime INT8 LM-head path in
`/home/steve/src/vllm/vllm/model_executor/layers/vocab_parallel_embedding.py`
does:

```text
per_token_quant_int8_xpu(hidden_states)
int8_gemm_w8a8(hidden_q, hidden_scales, lm_head_int8_weight_t, scales)
```

That is already much faster than the original BF16 LM-head, but it still writes
the full `[rows, vocab]` BF16 logits tensor.

## Existing native primitives are not enough

The current XPU extension has:

- `int8_gemm_w8a8` and `int8_gemm_w8a8_out`, backed by oneDNN matmul;
- per-token INT8 quantization helpers;
- sampler/top-k kernels that operate over an existing logits tensor.

Relevant files:

```text
/home/steve/src/vllm-xpu-kernels/csrc/xpu/onednn/int8_gemm_w8a8.h
/home/steve/src/vllm-xpu-kernels/csrc/xpu/onednn/onednn_matmul.cpp
/home/steve/src/vllm-xpu-kernels/csrc/xpu/torch_bindings.cpp
```

The oneDNN wrapper configures scales and scratchpad, executes matmul, and writes
`DNNL_ARG_DST`. It does not expose a top-1/candidate reduction epilogue, and the
current sampler/top-k kernels only run after dense logits exist. Therefore an
exact top-1 verifier win cannot be obtained by routing through the existing
Python flags or by calling the existing top-k sampler.

## No-win prototypes to avoid repeating

Already tried and preserved:

- output-buffer reuse for INT8 LM-head: valid but no-win (`62.428 tok/s` in
  that earlier window);
- exact target argmax-only plumbing: no-win because `get_top_tokens()` still
  paid the full LM-head projection;
- naive fused scalar top-1 XPU prototype:
  `2704.287 ms` median versus `2.690 ms` for
  `per_token_quant_int8_xpu + int8_gemm_w8a8 + argmax`; correct but about
  1000x too slow.

Artifacts:

```text
experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-int8-lmhead-reuse-out-no-win.md
experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-int8-lmhead-fused-top1-microbench-no-win.md
```

## Required real implementation

The next viable source target is a real native tiled kernel or equivalent
oneDNN/custom epilogue that fuses the INT8 LM-head projection with the exact
greedy verifier outputs needed by MTP:

1. Quantize hidden rows to INT8 as today, or fuse quantization if practical.
2. Compute the LM-head dot products using a tiled GEMM design, not scalar
   per-token/per-vocab loops.
3. Reduce per row to the exact max token/value while respecting:
   - `org_vocab_size` / padding mask;
   - optional scale and soft-cap;
   - NaN sanitation policy;
   - deterministic tie behavior close enough to current `argmax` for strict
     hash gates.
4. For rejection sampling, also return candidate draft-token logits and any
   bonus-token values needed to preserve target-verified acceptance semantics.
5. Fall back to dense logits when logprobs, non-greedy sampling, logits
   processors, penalties, bad-word masks, or allowed-token masks are active.

This is not a config sweep. It requires either:

- extending `vllm-xpu-kernels` with a production tiled
  `int8_lm_head_top1/candidate_max` op; or
- finding/upstreaming a oneDNN matmul epilogue that can emit top-1/candidate
  reductions without writing dense logits.

Until that exists, the current valid headline lane remains the BF16-scale
runtime INT8 LM-head record at `65.276 tok/s`.

## Suggested next action

Do not continue trying scale dtype, output reuse, Python argmax variants, or
scalar fused top-1. If pursuing more speed on this model, start a dedicated
native-kernel lane with a tiny correctness-first prototype that returns:

```text
top_token_ids[int64/int32], top_values[bf16/fp32], candidate_values[bf16/fp32]
```

for `rows <= 4`, `hidden=5120`, `vocab=248320`, then microbench against the
current INT8 GEMM path before integrating into vLLM. Promote only after strict
fresh realistic suite + repeat32/needle quality gates.
