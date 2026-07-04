# GLM-4.7-Flash UD-Q4_K_XL Rapid Snapshot

Audience: benchmark readers and future optimizers who need a strict one-B70
llama.cpp baseline for GLM-4.7-Flash on Intel Arc Pro B70.

## Status

- Model: `unsloth/GLM-4.7-Flash-GGUF`
- Base model family: `zai-org/GLM-4.7-Flash`, 30B-A3B MoE
- File: `GLM-4.7-Flash-UD-Q4_K_XL.gguf`
- HF revision: `0d32489ecb9db6d2a4fc93bd27ef01519f95474d`
- Local path:
  `/mnt/usb-models/llm-models/glm-4.7-flash-gguf/GLM-4.7-Flash-UD-Q4_K_XL.gguf`
- File size verified: `17520169312` bytes
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Source snapshot recorded by the runner: `/home/steve/src/llama.cpp`
  `fdb1db877c526ec90f668eca1b858da5dba85560`, clean at run time
- Result status: strict-valid rapid snapshot, but slow relative to the Qwen3
  30B-A3B GGUF rows on the same host. Treat this as expected-performance
  evidence for this runtime/model combination, not a frontier result.
- LocalMaxxing: approved as `cmr6xkr2f00gomn01k4u2dua8`.

## Headline Strict Row

Use the conservative standalone confirmation, not the faster four-GPU screen
rows.

- Evidence:
  `data/rapid-model-snapshots-b70/glm-4.7-flash-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128-20260704T221455Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/glm-4.7-flash-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128-20260704T221455Z`
- Primary metric: `40.7691297367011 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `40.01936615541169 tok/s`
- mean: `40.26057811873019 tok/s`
- full after-TTFT median: `40.67843679094294 tok/s`
- wall-clock full-output median: `38.164814138737015 tok/s`
- TTFT median: `206.20633498765528 ms`
- Prompt cache: disabled at the server (`--cache-ram 0`) and per request
  (`{"cache_prompt":false}`)
- `cached_tokens=0` on all `12/12` prompts
- `realistic_final_gate.passed=true`

## Quick Screen

All rows below used the same strict rapid realistic suite, one cold response per
prompt, server prompt cache disabled, per-request `cache_prompt=false`, and
`cached_tokens=0` on every request. Four-way screen rows ran concurrently on
GPUs 0-3 and are support/diagnostic only unless independently confirmed.

| Label | Median tok/s 1-100 after TTFT | Result |
| --- | ---: | --- |
| `poll100-confirm-ctx4096` | `40.7691297367011` | promoted conservative standalone |
| `poll100-confirm-gpu1-ctx4096` | `40.69448541933854` | standalone support |
| `poll0-confirm-ctx4096` | `40.26920254834211` | standalone no win |
| `poll100-freq2800-ctx4096` | `40.28100299317759` | no win; temporary GPU0 2800/2800 MHz lock, then restored |
| `secondscreen-poll0-ctx4096` | `44.12772006015564` | four-GPU-active support only; not headline |
| `poll100-ctx4096` | `43.961846688326546` | four-GPU-active support only; not headline |
| `default-ctx4096` | `43.889325874008236` | four-GPU-active support only; not headline |
| `secondscreen-ctx1024` | `43.577157910785374` | four-GPU-active support only |
| `secondscreen-ub128-ctx4096` | `43.01738632760778` | four-GPU-active support only |
| `secondscreen-ub1024-ctx4096` | `42.96398053825505` | four-GPU-active support only |
| `ub512-ctx4096` | `42.78754997492771` | first screen no win |
| `ctx2048` | `42.45966898905738` | first screen no win |

Conclusion: the fast `~44 tok/s` rows appear only in four-GPU-active screens.
Standalone confirmations on GPU0 and GPU1 repeatedly landed around `40.7 tok/s`,
so the promoted row uses the conservative standalone result. A temporary GPU0
core-frequency lock (`2800,2800`) held under load and reported `Not Throttled`,
but did not improve throughput, so it was restored to the default `400,2800`.

## Reproduce

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/glm-4.7-flash-gguf/GLM-4.7-Flash-UD-Q4_K_XL.gguf \
MODEL_ALIAS=glm-4.7-flash-udq4-rapid \
LABEL=glm-4.7-flash-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128 \
GPU_INDEX=0 PORT=19674 \
CTX_SIZE=4096 BATCH_SIZE=1024 UBATCH_SIZE=256 POLL=100 \
FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
MAX_TOKENS=128 METRIC_TOKENS=100 \
scripts/run-rapid-llamacpp-realistic-candidate.sh
```

The runner defaults to server prompt cache disabled (`--cache-ram 0`) and
per-request prompt cache disabled (`{"cache_prompt":false}`). Do not remove
either for headline claims.

## Validity

This row uses the shared rapid realistic suite:

- `repro/rapid-model-snapshots-b70/realistic-suite-v1.json`;
- one cold response per prompt;
- `temperature=0`;
- no speculation, no n-gram/history acceleration, no response reuse;
- no context checkpoints;
- server and per-request llama.cpp prompt cache disabled;
- `cached_tokens=0` for every request.

The benchmark uses streamed text/reasoning deltas for token timing because
llama.cpp does not provide vLLM-style streamed token IDs here. The promoted row
emitted enough streamed deltas for the 100-token metric window.

## Notes For Future Work

- Start with F16 KV for GLM-4.7-Flash. Public llama.cpp reports mentioned
  GLM-4.7-Flash failures with FlashAttention plus KV quantization, especially
  on longer prompts.
- Q8 files are too tight for a clean one-B70 row (`Q8_0` is about `31.8GB`,
  `UD-Q8_K_XL` about `35.6GB`) once KV and runtime overhead are included.
- The model is architecturally different from Qwen3 30B-A3B: GLM-4.7-Flash uses
  `Glm4MoeLiteForCausalLM`, MLA-style attention, 64 routed experts plus one
  shared expert, and 4 experts per token. The current llama.cpp/SYCL path is
  much slower here than on Qwen3 30B-A3B, even though both are 30B-A3B class.
- General-use sampling suggestions from Z.ai/Unsloth (`temperature=1.0`,
  `top_p=0.95`, `min_p=0.01`, neutral repeat penalty) are deployment guidance,
  not part of this deterministic benchmark row.
