# Phi-4 Mini Instruct GGUF Rapid Snapshot

Audience: benchmark readers and future optimizers who need strict one-B70
llama.cpp baselines for Phi-4-mini-instruct on Intel Arc Pro B70.

## Status

- Model: `bartowski/microsoft_Phi-4-mini-instruct-GGUF`
- Base model: `microsoft/Phi-4-mini-instruct`
- HF revision: `7ff82c2aaa4dde30121698a973765f39be5288c0`
- Local path:
  `/mnt/usb-models/llm-models/phi-4-mini-instruct-gguf/`
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Source snapshot recorded by the runner: `/home/steve/src/llama.cpp`
  `fdb1db877c526ec90f668eca1b858da5dba85560`, clean at run time
- Result status: strict-valid rapid snapshot. Q4_K_M is the faster row; Q8_0
  is retained as the higher-quality quant reference.

## Promoted Strict Rows

Both rows use the conservative standalone confirmation, not the lower
four-GPU-active screen rows.

### Q4_K_M

- File: `microsoft_Phi-4-mini-instruct-Q4_K_M.gguf`
- Size verified: `2491874688` bytes
- Evidence:
  `data/rapid-model-snapshots-b70/phi4-mini-instruct-q4km-llamacpp-faon-cacheoff-confirm-ctx4096-realistic128-20260704T224303Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/phi4-mini-instruct-q4km-llamacpp-faon-cacheoff-confirm-ctx4096-realistic128-20260704T224303Z`
- Primary metric: `96.54834088986573 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `96.35076872947823 tok/s`
- mean: `97.46057019933751 tok/s`
- full after-TTFT median: `96.58045060444897 tok/s`
- wall-clock full-output median: `91.74970215367543 tok/s`
- TTFT median: `69.93722857441753 ms`
- Same-recipe standalone repeat:
  `96.5741088959735 tok/s` at
  `data/rapid-model-snapshots-b70/phi4-mini-instruct-q4km-llamacpp-faon-cacheoff-confirm2-ctx4096-realistic128-20260704T224409Z.json`
- LocalMaxxing: approved as `cmr6yazhe00hcmn01i5gz2xe0`

### Q8_0

- File: `microsoft_Phi-4-mini-instruct-Q8_0.gguf`
- Size verified: `4084611456` bytes
- Evidence:
  `data/rapid-model-snapshots-b70/phi4-mini-instruct-q8-llamacpp-faon-cacheoff-confirm2-ctx4096-realistic128-20260704T224430Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/phi4-mini-instruct-q8-llamacpp-faon-cacheoff-confirm2-ctx4096-realistic128-20260704T224430Z`
- Primary metric: `72.24629337909391 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `71.90777370054381 tok/s`
- mean: `72.58812815357142 tok/s`
- full after-TTFT median: `72.15923782467202 tok/s`
- wall-clock full-output median: `67.59197293058796 tok/s`
- TTFT median: `119.45722799282521 ms`
- Same-recipe standalone support row:
  `72.88395951540713 tok/s` at
  `data/rapid-model-snapshots-b70/phi4-mini-instruct-q8-llamacpp-faon-cacheoff-confirm-ctx4096-realistic128-20260704T224324Z.json`
- LocalMaxxing: approved as `cmr6yazvy00hgmn01s5rtowwa`

## Quick Screen

All rows below used the same strict rapid realistic suite, one cold response per
prompt, server prompt cache disabled, per-request `cache_prompt=false`, and
`cached_tokens=0` on every request.

| Label | Median tok/s 1-100 after TTFT | Result |
| --- | ---: | --- |
| `q4km-confirm` | `96.54834088986573` | promoted conservative Q4_K_M |
| `q4km-confirm2` | `96.5741088959735` | same-recipe standalone support |
| `q8-confirm2` | `72.24629337909391` | promoted conservative Q8_0 |
| `q8-confirm` | `72.88395951540713` | same-recipe standalone support |
| `q4km-default-fourway` | `74.79866793510266` | four-GPU-active support only |
| `q4km-poll100-fourway` | `74.23238745327595` | four-GPU-active support only |
| `q8-default-fourway` | `60.15295566301178` | four-GPU-active support only |
| `q8-poll100-fourway` | `59.78046405225362` | four-GPU-active support only |

Conclusion: this small model is sensitive to concurrent four-GPU screening on
the shared host. Promote from standalone confirmations, not from concurrent
screen rows.

## Reproduce

Q4_K_M:

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/phi-4-mini-instruct-gguf/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf \
MODEL_ALIAS=phi4-mini-instruct-q4km \
LABEL=phi4-mini-instruct-q4km-llamacpp-faon-cacheoff-confirm-ctx4096-realistic128 \
GPU_INDEX=0 PORT=19710 \
CTX_SIZE=4096 BATCH_SIZE=1024 UBATCH_SIZE=256 POLL=50 \
FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
MAX_TOKENS=128 METRIC_TOKENS=100 \
scripts/run-rapid-llamacpp-realistic-candidate.sh
```

Q8_0:

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/phi-4-mini-instruct-gguf/microsoft_Phi-4-mini-instruct-Q8_0.gguf \
MODEL_ALIAS=phi4-mini-instruct-q8 \
LABEL=phi4-mini-instruct-q8-llamacpp-faon-cacheoff-confirm2-ctx4096-realistic128 \
GPU_INDEX=0 PORT=19713 \
CTX_SIZE=4096 BATCH_SIZE=1024 UBATCH_SIZE=256 POLL=50 \
FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
MAX_TOKENS=128 METRIC_TOKENS=100 \
scripts/run-rapid-llamacpp-realistic-candidate.sh
```

The runner defaults to server prompt cache disabled (`--cache-ram 0`) and
per-request prompt cache disabled (`{"cache_prompt":false}`). Do not remove
either for headline claims.

## Validity

These rows use the shared rapid realistic suite:

- `repro/rapid-model-snapshots-b70/realistic-suite-v1.json`;
- one cold response per prompt;
- `temperature=0`;
- no speculation, no n-gram/history acceleration, no response reuse;
- no context checkpoints;
- server and per-request llama.cpp prompt cache disabled;
- `cached_tokens=0` for every request.

The benchmark uses streamed text/reasoning deltas for token timing because
llama.cpp does not provide vLLM-style streamed token IDs here. The promoted rows
emitted enough streamed deltas for the 100-token metric window.

## Notes For Future Work

- Q4_K_M is the practical speed row for this model on one B70.
- Q8_0 is still useful as a compact higher-quality reference, but it is about
  `25%` slower than Q4_K_M under this harness.
- Four-way concurrent screens are still useful to compare knobs, but for small
  models they can understate standalone throughput substantially. Confirm
  standalone before publishing.
