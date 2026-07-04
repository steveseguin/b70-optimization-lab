# Qwen3-Coder 30B-A3B Instruct UD-Q4_K_XL Rapid Snapshot

Audience: benchmark readers and future optimizers who need a strict one-B70
llama.cpp baseline for this coder-tuned Qwen3 MoE model.

## Status

- Model: `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF`
- File: `Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf`
- HF revision: `b17cb02dd882d5b6ab62fc777ad2995f19668350`
- Local path:
  `/mnt/usb-models/llm-models/qwen3-coder-30b-a3b-instruct-gguf/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf`
- File size verified: `17665334432` bytes
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Source snapshot recorded by the runner: `/home/steve/src/llama.cpp`
  `fdb1db877c526ec90f668eca1b858da5dba85560`, clean at run time
- Result status: strict-valid rapid snapshot. This is a useful coder-family
  companion to the Qwen3 30B-A3B Instruct first-pass row.
- LocalMaxxing: approved as `cmr6w2ekt00gimn01orbith22`.
  Queue:
  `experiments/rapid-model-snapshots-b70/localmaxxing/qwen3-coder-30b-a3b-instruct-udq4-llamacpp-realistic128-20260704.queue.json`.
  Response:
  `data/localmaxxing-responses/qwen3-coder-30b-a3b-instruct-udq4-llamacpp-realistic128-20260704.submit.log`.

## Headline Strict Row

- Evidence:
  `data/rapid-model-snapshots-b70/qwen3-coder-30b-a3b-instruct-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128-20260704T214053Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/qwen3-coder-30b-a3b-instruct-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128-20260704T214053Z`
- Primary metric: `108.1165394591524 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `106.57270050892973 tok/s`
- mean: `105.32833006465762 tok/s`
- full after-TTFT median: `107.89705487368178 tok/s`
- wall-clock full-output median: `94.7540711662736 tok/s`
- TTFT median: `164.12943904288113 ms`
- Prompt cache: disabled at the server (`--cache-ram 0`) and per request
  (`{"cache_prompt":false}`)
- `cached_tokens=0` on all `12/12` prompts
- `realistic_final_gate.passed=true`

## Quick Screen

All rows below used the same strict rapid realistic suite, one cold response per
prompt, server prompt cache disabled, per-request `cache_prompt=false`, and
`cached_tokens=0` on every request.

| Label | Median tok/s 1-100 after TTFT | Result |
| --- | ---: | --- |
| `poll100-confirm-ctx4096` | `108.1165394591524` | promoted |
| `poll100-ctx4096` | `108.0454610162192` | support |
| `ctx2048` | `108.29960743060771` | support high, did not repeat |
| `ctx2048-repeat` | `107.51485776677853` | support |
| `default-ctx4096` | `107.76254214876545` | support |
| `default-repeat-ctx4096` | `107.58751560705679` | support |
| `ctx1024` | `107.17479926752284` | support, no win |
| `ub512-ctx4096` | `107.15887820342631` | no win |
| `poll0-ctx4096` | `106.25295287132846` | no win |

Conclusion: `POLL=100` at `ctx=4096` is a small, repeatable enough first-pass
representative for this model. Treat the delta over default as within the rapid
screen's normal sub-percent variance, not as a deep optimization claim.

## Reproduce

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/qwen3-coder-30b-a3b-instruct-gguf/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf \
MODEL_ALIAS=qwen3-coder-30b-a3b-instruct-udq4-rapid \
LABEL=qwen3-coder-30b-a3b-instruct-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128 \
GPU_INDEX=0 PORT=19658 \
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
llama.cpp does not provide vLLM-style streamed token IDs here. All promoted and
support rows emitted enough streamed deltas for the 100-token metric window.
