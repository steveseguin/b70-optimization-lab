# Qwen3 14B Instruct Q4_K_M Rapid Snapshot

Audience: benchmark readers and future optimizers who need a strict one-B70
llama.cpp baseline for Qwen3 14B Instruct on Intel Arc Pro B70.

## Status

- Model: `lm-kit/qwen-3-14b-instruct-gguf`
- Original model family: Qwen3 14B Instruct
- File: `Qwen3-14B-Q4_K_M.gguf`
- HF revision: `f723b4e01f20538b1c1e719ee83331cf2231e4ef`
- Local path:
  `/mnt/usb-models/llm-models/qwen3-14b-instruct-gguf/Qwen3-14B-Q4_K_M.gguf`
- File size verified: `9001753408` bytes
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Source snapshot recorded by the runner: `/home/steve/src/llama.cpp`
  `fdb1db877c526ec90f668eca1b858da5dba85560`, clean at run time
- Result status: strict-valid rapid snapshot. This is a useful expected
  performance row for the Qwen3 14B Instruct Q4_K_M GGUF lane, not a
  frontier-speed row.

## Headline Strict Row

Use the standalone `ctx=2048`, `ubatch=512`, `threads=12` confirmation. It was
only a small win over the simple `ctx=4096` baseline, so do not over-interpret
sub-percent micro-ranking.

- Evidence:
  `data/rapid-model-snapshots-b70/qwen3-14b-instruct-q4km-llamacpp-faon-cacheoff-ctx2048-ub512-t12-confirm-realistic128-20260705T005359Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/qwen3-14b-instruct-q4km-llamacpp-faon-cacheoff-ctx2048-ub512-t12-confirm-realistic128-20260705T005359Z`
- Primary metric: `38.249019008891544 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `37.75690009957747 tok/s`
- mean: `38.35697248748106 tok/s`
- full after-TTFT median: `38.21736308860659 tok/s`
- wall-clock full-output median: `35.62076563529337 tok/s`
- TTFT median: `240.0411400012672 ms`
- Prompt cache: disabled at the server (`--cache-ram 0`) and per request
  (`{"cache_prompt":false}`)
- `cached_tokens=0` on all `12/12` prompts
- `realistic_final_gate.passed=true`
- LocalMaxxing: approved as `cmr750k4k00lhmn01hq55eaub`
- Output shape: visible content deltas, zero reasoning deltas, and no visible
  `<think>` leakage in the strict suite.

## Quick Screen

All rows below used the same strict rapid realistic suite, one cold response per
prompt, server prompt cache disabled, per-request `cache_prompt=false`, and
`cached_tokens=0` on every request. Four-GPU concurrent rows compressed wall
time but underreported standalone throughput for this GGUF lane, so they are
support only.

| Label | Median tok/s 1-100 after TTFT | Result |
| --- | ---: | --- |
| `ctx2048-ub512-t12` | `38.36300654991402` | support, same recipe |
| `ctx2048-ub512-t12-confirm` | `38.249019008891544` | promoted standalone |
| `ctx2048-ub512` | `38.3320652330347` | support |
| `ctx2048-ub512-t4` | `38.15387756822632` | no material win |
| `ctx4096 baseline` | `37.89526590689783` | strict-valid baseline |
| `fourway poll100-ctx4096` | `31.58693859551303` | concurrent support only |
| `fourway ctx2048` | `31.454761703625266` | concurrent support only |
| `fourway default-ctx4096` | `31.31227652628796` | concurrent support only |
| `fourway ub512-ctx4096` | `31.29938033955768` | concurrent support only |

## Reproduce

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/qwen3-14b-instruct-gguf/Qwen3-14B-Q4_K_M.gguf \
MODEL_ALIAS=qwen3-14b-instruct-q4km \
LABEL=qwen3-14b-instruct-q4km-llamacpp-faon-cacheoff-ctx2048-ub512-t12-confirm-realistic128 \
GPU_INDEX=0 PORT=19760 \
CTX_SIZE=2048 BATCH_SIZE=1024 UBATCH_SIZE=512 THREADS=12 POLL=50 \
FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
MAX_TOKENS=128 METRIC_TOKENS=100 \
scripts/run-rapid-llamacpp-realistic-candidate.sh
```

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

- The `Instruct` GGUF emitted normal visible content through llama.cpp `--jinja`
  + `--reasoning off`; unlike the DeepSeek-R1-Distill diagnostic, it did not
  remain inside hidden thinking.
- Easy ctx/ubatch/thread/poll probes found only a small win. Better speed would
  likely need model-specific kernels or target-verified speculation, not more
  wrapper-level llama.cpp flag sweeps.
- Keep f16 KV for this promoted quality-preserving row. KV quantization should
  be recorded as a separate quality/performance tradeoff if tested later.
