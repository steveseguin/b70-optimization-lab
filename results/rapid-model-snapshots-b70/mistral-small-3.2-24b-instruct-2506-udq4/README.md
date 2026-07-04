# Mistral Small 3.2 24B Instruct 2506 UD-Q4_K_XL Rapid Snapshot

Audience: benchmark readers and future optimizers who need a strict one-B70
llama.cpp baseline for this dense 24B model.

## Status

- Model: `unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF`
- File: `Mistral-Small-3.2-24B-Instruct-2506-UD-Q4_K_XL.gguf`
- HF revision: `b750ec2299225e492f1bd27cab88a0a595fa848f`
- Local path:
  `/mnt/usb-models/llm-models/mistral-small-3.2-24b-instruct-2506-gguf/Mistral-Small-3.2-24B-Instruct-2506-UD-Q4_K_XL.gguf`
- File size verified: `14548880928` bytes
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Source snapshot recorded by the runner: `/home/steve/src/llama.cpp`
  `fdb1db877c526ec90f668eca1b858da5dba85560`, clean at run time
- Result status: strict-valid rapid snapshot; valid but underwhelming. Dense
  24B active compute is a very different class from Qwen3 30B-A3B MoE.
- LocalMaxxing: approved as `cmr6ura7300e4mn01yrdw7wto`.
  Queue:
  `experiments/rapid-model-snapshots-b70/localmaxxing/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-realistic128-20260704.queue.json`.
  Response:
  `data/localmaxxing-responses/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-realistic128-20260704.submit.log`.

## Headline Strict Row

- Evidence:
  `data/rapid-model-snapshots-b70/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-faon-cacheoff-v2-ctx4096-realistic128-20260704T205443Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-faon-cacheoff-v2-ctx4096-realistic128-20260704T205443Z`
- Primary metric: `27.29674347655439 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `27.126019755475596 tok/s`
- mean: `27.356226121944818 tok/s`
- full after-TTFT median: `27.224403742105483 tok/s`
- wall-clock full-output median: `20.63443091122179 tok/s`
- TTFT median: `1501.7739470349625 ms`
- Prompt cache: disabled at the server (`--cache-ram 0`) and per request
  (`{"cache_prompt":false}`)
- `cached_tokens=0` on all `12/12` prompts
- `realistic_final_gate.passed=true`

## No-Win / Reference Rows

- Q8 fit check:
  `data/rapid-model-snapshots-b70/mistral-small-3.2-24b-instruct-2506-udq8-llamacpp-faon-ctx4096-realistic128-20260704T201848Z.json`
  passed the strict gate but was only `16.380395177161446 tok/s`.
- First Q4 attempt:
  `data/rapid-model-snapshots-b70/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-faon-ctx4096-realistic128-20260704T202421Z.json`
  is invalid. It came from a contaminated multi-range resume; the run emitted
  no stream text chunks and must not be used as a model/runtime result.
- Quick variant screen, all strict/cache-off unless noted:
  - `POLL=100`: `24.956425259573045 tok/s`;
  - `UBATCH_SIZE=512`: `25.267271232446316 tok/s`;
  - `CTX_SIZE=2048`: `24.978475041077193 tok/s`;
  - FlashAttention off: did not reach readiness promptly; killed during model
    fitting/loading.

Conclusion: keep the simple FA-on, F16 KV, `ctx=4096`, `BATCH=1024`,
`UBATCH=256`, server-cache-off recipe as the representative row. The rapid
screen found no easy knob win.

## Reproduce

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/mistral-small-3.2-24b-instruct-2506-gguf/Mistral-Small-3.2-24B-Instruct-2506-UD-Q4_K_XL.gguf \
MODEL_ALIAS=mistral-small-3.2-24b-instruct-2506-udq4-rapid \
LABEL=mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-faon-cacheoff-v2-ctx4096-realistic128 \
GPU_INDEX=0 PORT=19641 \
CTX_SIZE=4096 BATCH_SIZE=1024 UBATCH_SIZE=256 \
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
llama.cpp does not provide vLLM-style streamed token IDs here. All rows emitted
enough streamed deltas for the 100-token metric window.
