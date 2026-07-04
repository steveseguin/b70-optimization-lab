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
| Qwen3 30B-A3B Instruct 2507 | llama.cpp/SYCL on one B70 | GGUF UD-Q4_K_XL | Strict-valid first-pass row promoted | `107.48388363267362 tok/s` median tokens 1-100 after TTFT, `cached_tokens=0`, prompt cache disabled. Packet: [qwen3-30b-a3b-instruct-2507-udq4](qwen3-30b-a3b-instruct-2507-udq4/README.md). Official GPTQ vLLM path is runtime-blocked on the current local XPU build by missing GPTQ ops. |
| Qwen3-Coder 30B-A3B Instruct | llama.cpp/SYCL on one B70 | GGUF UD-Q4_K_XL | Strict-valid first-pass row promoted | `108.1165394591524 tok/s` median tokens 1-100 after TTFT, `cached_tokens=0`, server prompt cache disabled with `--cache-ram 0`. Packet: [qwen3-coder-30b-a3b-instruct-udq4](qwen3-coder-30b-a3b-instruct-udq4/README.md). Small poll/context sweeps found only sub-percent movement; `POLL=100`, `ctx=4096` is the representative row. |
| Phi-4 mini instruct | llama.cpp/SYCL on one B70 | GGUF Q4_K_M / Q8_0 | Strict-valid rapid rows promoted | `96.54834088986573 tok/s` for Q4_K_M and `72.24629337909391 tok/s` for Q8_0, `cached_tokens=0`, prompt cache disabled. Packet: [phi4-mini-instruct-gguf](phi4-mini-instruct-gguf/README.md). Concurrent four-GPU screens were lower, so standalone confirmations are the promoted rows. |
| DeepSeek-Coder-V2-Lite-Instruct | llama.cpp/SYCL on one B70 | GGUF Q4_K_M | Strict-valid rapid row promoted | `57.09651439511314 tok/s` median tokens 1-100 after TTFT, `cached_tokens=0`, prompt cache disabled. Packet: [deepseek-coder-v2-lite-q4km](deepseek-coder-v2-lite-q4km/README.md). `ctx=2048` was a small standalone win over `ctx=4096`; concurrent four-GPU screens underreported and are support only. |
| Mistral Small 3.2 24B Instruct 2506 | llama.cpp/SYCL on one B70 | GGUF UD-Q4_K_XL | Strict-valid rapid row promoted as valid/modest | `27.29674347655439 tok/s` median tokens 1-100 after TTFT, `cached_tokens=0`, server prompt cache disabled with `--cache-ram 0`. Packet: [mistral-small-3.2-24b-instruct-2506-udq4](mistral-small-3.2-24b-instruct-2506-udq4/README.md). Q8 fit check passed at only `16.38 tok/s`; quick Q4 knobs found no win. |
| GLM-4.7-Flash | llama.cpp/SYCL on one B70 | GGUF UD-Q4_K_XL | Strict-valid rapid row promoted as valid/modest | `40.7691297367011 tok/s` median tokens 1-100 after TTFT, `cached_tokens=0`, server prompt cache disabled with `--cache-ram 0`. Packet: [glm-4.7-flash-udq4](glm-4.7-flash-udq4/README.md). Faster `~44 tok/s` four-GPU-active screen rows were kept as support only because standalone confirmations landed around `40.7 tok/s`. |
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

| Model | Runtime | Quantization | GPUs | Strict median tok/s | Evidence | LocalMaxxing |
| --- | --- | --- | ---: | ---: | --- | --- |
| Qwen3 30B-A3B Instruct 2507 | llama.cpp/SYCL | GGUF UD-Q4_K_XL | 1 | `107.48388363267362` | [result packet](qwen3-30b-a3b-instruct-2507-udq4/README.md), `data/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-faon-nocacheprompt-realistic128-20260704T193409Z.json` | `cmr6rr2kv008imn019frg0x3m` |
| Qwen3-Coder 30B-A3B Instruct | llama.cpp/SYCL | GGUF UD-Q4_K_XL | 1 | `108.1165394591524` | [result packet](qwen3-coder-30b-a3b-instruct-udq4/README.md), `data/rapid-model-snapshots-b70/qwen3-coder-30b-a3b-instruct-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128-20260704T214053Z.json` | `cmr6w2ekt00gimn01orbith22` |
| Phi-4 mini instruct | llama.cpp/SYCL | GGUF Q4_K_M | 1 | `96.54834088986573` | [result packet](phi4-mini-instruct-gguf/README.md), `data/rapid-model-snapshots-b70/phi4-mini-instruct-q4km-llamacpp-faon-cacheoff-confirm-ctx4096-realistic128-20260704T224303Z.json` | `cmr6yazhe00hcmn01i5gz2xe0` |
| Phi-4 mini instruct | llama.cpp/SYCL | GGUF Q8_0 | 1 | `72.24629337909391` | [result packet](phi4-mini-instruct-gguf/README.md), `data/rapid-model-snapshots-b70/phi4-mini-instruct-q8-llamacpp-faon-cacheoff-confirm2-ctx4096-realistic128-20260704T224430Z.json` | `cmr6yazvy00hgmn01s5rtowwa` |
| DeepSeek-Coder-V2-Lite-Instruct | llama.cpp/SYCL | GGUF Q4_K_M | 1 | `57.09651439511314` | [result packet](deepseek-coder-v2-lite-q4km/README.md), `data/rapid-model-snapshots-b70/deepseek-coder-v2-lite-q4km-llamacpp-faon-cacheoff-ctx2048-confirm-realistic128-20260704T231049Z.json` | `cmr6zbkbw00hpmn01nq858vcg` |
| GLM-4.7-Flash | llama.cpp/SYCL | GGUF UD-Q4_K_XL | 1 | `40.7691297367011` | [result packet](glm-4.7-flash-udq4/README.md), `data/rapid-model-snapshots-b70/glm-4.7-flash-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128-20260704T221455Z.json` | `cmr6xkr2f00gomn01k4u2dua8` |
| Mistral Small 3.2 24B Instruct 2506 | llama.cpp/SYCL | GGUF UD-Q4_K_XL | 1 | `27.29674347655439` | [result packet](mistral-small-3.2-24b-instruct-2506-udq4/README.md), `data/rapid-model-snapshots-b70/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-faon-cacheoff-v2-ctx4096-realistic128-20260704T205443Z.json` | `cmr6ura7300e4mn01yrdw7wto` |

Existing non-rapid reference rows remain in their model result folders:

- Gemma 4 26B Q8 one-B70 llama.cpp: `124.97714084813418 tok/s`, LocalMaxxing
  `cmr1u77na01k2ld01kalwzs1e`;
- Qwen3.6 27B INT4 AutoRound one-B70 vLLM: `65.27648650325429 tok/s`,
  LocalMaxxing `cmr5iu3gk00bfq901nidgcana`;
- Qwen3.6 27B GGUF Q4 one-B70 llama.cpp: `30.678766952807752 tok/s`,
  LocalMaxxing `cmr6mn5ct0076mn01on3dnpyn`.
