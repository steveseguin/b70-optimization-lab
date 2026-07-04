# DeepSeek-Coder-V2-Lite-Instruct Q4_K_M Rapid Snapshot

Audience: benchmark readers and future optimizers who need a strict one-B70
llama.cpp baseline for DeepSeek-Coder-V2-Lite-Instruct on Intel Arc Pro B70.

## Status

- Model: `bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF`
- Original model: `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct`
- Model family note: DeepSeek-Coder-V2 Lite is a MoE coder model in the 16B
  total / 2.4B active class.
- File: `DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf`
- HF revision: `8f248fa2072348f77a8bc37754e470de1f61866e`
- Local path:
  `/mnt/usb-models/llm-models/deepseek-coder-v2-lite-instruct-gguf/DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf`
- File size verified: `10364416768` bytes
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Source snapshot recorded by the runner: `/home/steve/src/llama.cpp`
  `fdb1db877c526ec90f668eca1b858da5dba85560`, clean at run time
- Result status: strict-valid rapid snapshot. This is a useful coder-model
  expected-performance row; it is slower than the Qwen3 30B-A3B GGUF rows but
  faster than the GLM/Mistral rapid snapshots.

## Headline Strict Row

Use the conservative lower of the two standalone `ctx=2048` confirmations.

- Evidence:
  `data/rapid-model-snapshots-b70/deepseek-coder-v2-lite-q4km-llamacpp-faon-cacheoff-ctx2048-confirm-realistic128-20260704T231049Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/deepseek-coder-v2-lite-q4km-llamacpp-faon-cacheoff-ctx2048-confirm-realistic128-20260704T231049Z`
- Primary metric: `57.09651439511314 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `56.93158901082582 tok/s`
- mean: `57.08323191156333 tok/s`
- full after-TTFT median: `56.71077678017971 tok/s`
- wall-clock full-output median: `53.41444662060785 tok/s`
- TTFT median: `139.8265556199476 ms`
- Prompt cache: disabled at the server (`--cache-ram 0`) and per request
  (`{"cache_prompt":false}`)
- `cached_tokens=0` on all `12/12` prompts
- `realistic_final_gate.passed=true`
- LocalMaxxing: approved as `cmr6zbkbw00hpmn01nq858vcg`.

## Quick Screen

All rows below used the same strict rapid realistic suite, one cold response per
prompt, server prompt cache disabled, per-request `cache_prompt=false`, and
`cached_tokens=0` on every request. Four-way screen rows ran concurrently on
GPUs 0-3 and are diagnostic/support only unless independently confirmed.

| Label | Median tok/s 1-100 after TTFT | Result |
| --- | ---: | --- |
| `ctx2048` | `57.21192316867396` | standalone support |
| `ctx2048-confirm` | `57.09651439511314` | promoted conservative standalone |
| `ctx4096-default` | `56.03330573597446` | strict-valid baseline |
| `ctx4096-ub512` | `56.12564201373243` | no material win |
| `fourway-ctx2048` | `43.31155837045327` | four-GPU-active support only |
| `fourway-ub512-ctx4096` | `42.49284651812975` | four-GPU-active support only |
| `fourway-default-ctx4096` | `40.541902174501836` | four-GPU-active support only |
| `fourway-poll100-ctx4096` | `38.05749045183228` | four-GPU-active support only |

Conclusion: `ctx=2048` is a small standalone win for this short-context rapid
suite. The concurrent four-GPU screen substantially underreported throughput,
so promote from standalone confirmations only.

## Reproduce

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/deepseek-coder-v2-lite-instruct-gguf/DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf \
MODEL_ALIAS=deepseek-coder-v2-lite-q4km \
LABEL=deepseek-coder-v2-lite-q4km-llamacpp-faon-cacheoff-ctx2048-confirm-realistic128 \
GPU_INDEX=0 PORT=19720 \
CTX_SIZE=2048 BATCH_SIZE=1024 UBATCH_SIZE=256 POLL=50 \
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

- FlashAttention with F16 KV worked cleanly for this Lite GGUF on the current
  llama.cpp/SYCL build. Older community reports around DeepSeek V2 GGUF warned
  about FlashAttention and KV-quantized cache issues, so keep F16 KV as the
  conservative starting point.
- This result is a rapid snapshot, not a deep model-specific optimization lane.
  If revisited, compare other Q4-class quants or a current vLLM/XPU path before
  spending time on micro-knobs.
