# Rapid Model Snapshot Results

This ledger records useful short-context decode snapshots from the 4x Intel Arc
Pro B70 system. Rows here are either strict-valid fresh-response results or
clearly labeled references. Synthetic, warmed, repeated-prompt, cache-assisted,
or history-accelerated diagnostics do not belong here as headline rows.

Strict headline rows use:

- `repro/rapid-model-snapshots-b70/realistic-suite-v1.json`;
- one cold response per prompt;
- `cached_tokens=0` for every request;
- no prompt/KV/context/response reuse;
- primary metric `median_tok_s_1_100_after_ttft`;
- target-verified speculation only.

## Current Candidates

| Model | Runtime | Quantization | Status | Notes |
| --- | --- | --- | --- | --- |
| Qwen3 30B-A3B / Qwen3-Coder 30B-A3B | vLLM/XPU first, llama.cpp fallback | GPTQ/INT4/FP8 or GGUF Q4/Q6 | Next vLLM target | Best new-model fit for Intel/vLLM XPU MoE work; useful general/coder comparison. |
| Mistral Small 3.2 24B Instruct | llama.cpp first | GGUF Q4/Q6/Q8 | Downloading first GGUF target | Practical one-B70 dense model; good first rapid llama.cpp snapshot. |
| Gemma 4 12B | vLLM and/or llama.cpp | INT4/AutoRound or GGUF | Quick TP1 failed | TP1 graph and eager vLLM/XPU strict attempts both failed on first prompt with XPU FlashAttention `UR_RESULT_ERROR_OUT_OF_RESOURCES`; use existing TP4/c8 production docs as reference. |
| Phi-4 family | llama.cpp/vLLM | Q4+ | Queued | Small practical reference if setup is quick. |
| DeepSeek-R1-Distill-Qwen 14B/32B | llama.cpp/vLLM | Q4+ | Later | Reasoning-family reference after first three lanes. |

## Skipped For This Rapid Pass

| Model | Reason |
| --- | --- |
| Kimi K2.x | Too large for a clean local rapid pass on 4x B70. |
| GLM 5.2 large variants | Too large for the current rapid one-GPU target. |
| DeepSeek V4 Flash | 284B total parameter footprint; earlier notes show no clean TP4 fit. |
| Llama 4 Scout | Lower priority because model quality/usefulness is uncertain for this effort. |

## Published / Promoted Rows

No rapid-snapshot rows have been promoted yet.

Existing non-rapid reference rows remain in their model result folders:

- Gemma 4 26B Q8 one-B70 llama.cpp: `124.97714084813418 tok/s`, LocalMaxxing
  `cmr1u77na01k2ld01kalwzs1e`;
- Qwen3.6 27B INT4 AutoRound one-B70 vLLM: `65.27648650325429 tok/s`,
  LocalMaxxing `cmr5iu3gk00bfq901nidgcana`;
- Qwen3.6 27B GGUF Q4 one-B70 llama.cpp: `30.678766952807752 tok/s`,
  LocalMaxxing `cmr6mn5ct0076mn01on3dnpyn`.
