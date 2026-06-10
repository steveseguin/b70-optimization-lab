# Qwen3.6 INT8 Redundant GemmaRMSNorm Cast Rejection

Date: 2026-06-10

## Context

I tested a small vLLM source candidate that skips `out.to(orig_dtype)` in
`GemmaRMSNorm.forward_native` when `ir.ops.rms_norm` already returns
`orig_dtype`.

The captured Qwen3.6 graph showed this sequence:

- `vllm_ir.rms_norm.default(..., fp32_weight, eps)` returning BF16
- `rms_norm_default.to(torch.bfloat16)`
- `view(...).contiguous()`
- `_xpu_C.per_token_quant_int8_xpu(...)`

The candidate keeps the cast when the dtype differs, but avoids the redundant
BF16-to-BF16 case. This does not intentionally change model math.

Everything else stayed unchanged:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`

## Graph Check

The candidate was launched with a fresh cache root:

- `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix-skip-gemma-to`

The generated `computation_graph.py` files no longer contained the direct
`rms_norm_default.to(torch.bfloat16)` signature, so the intended graph change
was present.

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | accepted refresh | skip redundant cast |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.6912` | `97.9590` |
| output tok/s end-to-end | `97.4280` | `96.7336` |
| total client tok/s | `194.8560` | `193.4672` |
| mean client TTFT | `77.39 ms` | `76.42 ms` |

Artifacts:

- accepted refresh: `data/qwen36-quark-int8-tp4-noprefix-accepted-single-refresh2-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-skip-gemma-to-graph32k-single-20260610.json`
- patch: `patches/vllm-qwen36-skip-redundant-gemma-to-rejected-20260610.patch`

## Decision

Reject the conditional-cast candidate.

Even though the redundant cast signature disappeared from the generated graph,
single-request decode regressed by about `0.7%`. The cast was either not a
meaningful bottleneck or its removal nudged compiler scheduling in the wrong
direction. Keep the accepted `GemmaRMSNorm.forward_native` behavior.
