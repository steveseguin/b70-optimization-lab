# Gemma 4 26B A4B vLLM/XPU Online Quantization Smokes

Date: 2026-06-23
Owner/agent: Codex
Scope: official HF `google/gemma-4-26B-A4B-it` checkpoint on one B70 replica,
vLLM/XPU V1, chat API, fresh-response validation only.

## Hypothesis

The official HF checkpoint plus vLLM online quantization could be a better
single-GPU B70 runtime than llama.cpp Q8 if the XPU MoE kernels and graph replay
outweighed llama.cpp's GGUF/SYCL path. The priority was INT8-or-better quality:
`int8_per_channel_weight_only` first, then FP8 online quantization only as a
diagnostic/lower-precision comparison.

## Shared Run Identity

- model: `/mnt/fast-ai/llm-cache/hf/models--google--gemma-4-26B-A4B-it/snapshots/20da991ab4afab98e8f910c4a2e8f4fbefc404ad`
- shards: 2 safetensors, `51,612,009,916` bytes
- runtime: editable vLLM from `/home/steve/src/vllm`, version
  `0.20.2rc1.dev13+g9557d9108.d20260620`
- torch: `2.11.0+xpu`
- API mode: `/v1/chat/completions`, `--language-model-only`,
  `--generation-config vllm`
- prefix cache: disabled with `--no-enable-prefix-caching`
- parallelism: one complete model replica, `--tensor-parallel-size 1`,
  `--pipeline-parallel-size 1`, `--max-num-seqs 1`
- device selection fix: use `ONEAPI_DEVICE_SELECTOR=level_zero:*` plus
  `ZE_AFFINITY_MASK=$GPU_INDEX`. The earlier `level_zero:$GPU_INDEX` form only
  exposed GPU 0; GPUs 1-3 saw zero XPU devices.
- runner: `scripts/run-gemma4-26b-vllm-int8pc-candidate.sh`

Validity note: these are repeated-prompt benchmark smokes, so the first request
is recorded separately and headline claims must stay below promotion status
unless a full validity gate is run. Prefix caching is disabled and there is no
draft/history source; the successful summary files report that no cached-token
usage was available/reported and include first-request throughput. Treat the
first request as the fresh-response indicator and the mean as smoke evidence
only, not a LocalMaxxing-grade headline.

## Results

| Label | Quantization | Graph / config | MBT | Canary | Mean tok/s after TTFT | First request tok/s | Wall tok/s | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-vllm-int8pc-gpu0-baseline-smoke-20260623T203239Z` | `int8_per_channel_weight_only` | graph off | 1024 | 128/128 | 27.05 | 27.17 | 26.49 | valid smoke loss |
| `gemma4-vllm-int8pc-gpu1-piecewise-selectorfix-smoke-20260623T204041Z` | `int8_per_channel_weight_only` | PIECEWISE, compile `[1]` | 1024 | 128/128 | 34.89 | 35.00 | 33.96 | best INT8 vLLM smoke, still noncompetitive |
| `gemma4-vllm-int8pc-gpu2-mbt512-selectorfix-smoke-20260623T204041Z` | `int8_per_channel_weight_only` | graph off | 512 | 128/128 | 25.15 | 25.07 | 24.57 | loss |
| `gemma4-vllm-int8pc-gpu3-mbt2048-selectorfix-smoke-20260623T204042Z` | `int8_per_channel_weight_only` | graph off | 2048 | 128/128 | 25.34 | 25.37 | 24.85 | loss |
| `gemma4-vllm-fp8tensor-gpu0-piecewise-smoke-20260623T204839Z` | `fp8_per_tensor` | PIECEWISE, compile `[1]` | 1024 | 64/64 | 39.49 | 39.73 | 38.26 | diagnostic FP8 win over INT8, not Q8/INT8 promotion |
| `gemma4-vllm-fp8tensor-gpu0-mbt512-piecewise-smoke-20260623T205416Z` | `fp8_per_tensor` | PIECEWISE, compile `[1]` | 512 | 64/64 | 38.46 | 38.45 | 37.05 | loss vs FP8 control |
| `gemma4-vllm-fp8tensor-gpu1-mbt2048-piecewise-smoke-20260623T205416Z` | `fp8_per_tensor` | PIECEWISE, compile `[1]` | 2048 | 64/64 | 40.22 | 40.22 | 38.92 | diagnostic FP8 near-best |
| `gemma4-vllm-fp8tensor-gpu2-compile12-piecewise-smoke-20260623T205416Z` | `fp8_per_tensor` | PIECEWISE, compile `[1,2]` | 1024 | 64/64 | 40.31 | 40.31 | 39.03 | best vLLM smoke, still far below llama.cpp Q8 |

## Failed Launches

| Label | Failure | Evidence |
| --- | --- | --- |
| `gemma4-vllm-int8pc-gpu1-piecewise-smoke-20260623T203929Z` | bad selector: `ONEAPI_DEVICE_SELECTOR=level_zero:1` exposed no XPU device | `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-int8pc-gpu1-piecewise-smoke-20260623T203929Z.server.log` |
| `gemma4-vllm-int8pc-gpu2-mbt512-smoke-20260623T203930Z` | bad selector: `ONEAPI_DEVICE_SELECTOR=level_zero:2` exposed no XPU device | `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-int8pc-gpu2-mbt512-smoke-20260623T203930Z.server.log` |
| `gemma4-vllm-int8pc-gpu3-mbt2048-smoke-20260623T203930Z` | bad selector: `ONEAPI_DEVICE_SELECTOR=level_zero:3` exposed no XPU device | `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-int8pc-gpu3-mbt2048-smoke-20260623T203930Z.server.log` |
| `gemma4-vllm-mxfp8-gpu2-piecewise-smoke-20260623T204839Z` | XPU has no available MXFP8 MoE backend | `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-mxfp8-gpu2-piecewise-smoke-20260623T204839Z.server.log` |
| `gemma4-vllm-fp8block-gpu1-piecewise-smoke-20260623T204839Z` | FP8 block quant asserts because Gemma expert hidden dim `704` is not divisible by block size `128` | `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-fp8block-gpu1-piecewise-smoke-20260623T204839Z.server.log` |

## Interpretation

vLLM is useful as a compatibility/control lane, but not the current speed path:

- INT8 per-channel online quantization is quality-compatible in principle, but
  this vLLM scheme only quantizes MoE expert weights; dense linear layers remain
  BF16. The best graph INT8 smoke reached only `34.89 tok/s`.
- FP8 per-tensor improves to `40.31 tok/s`, showing graph and broader online
  quantization help, but it is lower precision than the Q8/INT8 target and still
  less than half of the valid llama.cpp Q8 draft-MTP record (`92.397 tok/s`
  first measured request; `92.767 tok/s` supporting repeat mean).
- `mxfp8` and `fp8_per_block` are not viable for this checkpoint on the current
  XPU stack.
- Future vLLM work should wait for either a true all-linear INT8 path, a
  prequantized INT8/B70 checkpoint, or a Gemma-specific XPU kernel improvement.
  The active optimization lane should return to llama.cpp Q8 source-level MTP
  overhead work.

## Artifacts

- Runner/wrapper: `scripts/run-gemma4-26b-vllm-int8pc-candidate.sh`
- Successful summaries:
  - `data/gemma4-vllm-int8pc-gpu0-baseline-smoke-20260623T203239Z/summary.json`
  - `data/gemma4-vllm-int8pc-gpu1-piecewise-selectorfix-smoke-20260623T204041Z/summary.json`
  - `data/gemma4-vllm-int8pc-gpu2-mbt512-selectorfix-smoke-20260623T204041Z/summary.json`
  - `data/gemma4-vllm-int8pc-gpu3-mbt2048-selectorfix-smoke-20260623T204042Z/summary.json`
  - `data/gemma4-vllm-fp8tensor-gpu0-piecewise-smoke-20260623T204839Z/summary.json`
  - `data/gemma4-vllm-fp8tensor-gpu0-mbt512-piecewise-smoke-20260623T205416Z/summary.json`
  - `data/gemma4-vllm-fp8tensor-gpu1-mbt2048-piecewise-smoke-20260623T205416Z/summary.json`
  - `data/gemma4-vllm-fp8tensor-gpu2-compile12-piecewise-smoke-20260623T205416Z/summary.json`
