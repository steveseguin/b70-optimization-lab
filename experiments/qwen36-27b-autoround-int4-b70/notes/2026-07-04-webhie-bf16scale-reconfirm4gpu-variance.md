# Webhie BF16-scale INT8-LM-head 4-GPU reconfirmation

Date: 2026-07-04

## Why

A later strict support/control row for the current `webhie/Qwen3.6-27B-int4-AutoRound`
BF16-scale runtime INT8-LM-head recipe landed at `66.38933459706479 tok/s`,
above the approved LocalMaxxing row (`65.27648650325429 tok/s`). Because that
row used the same recipe rather than a new optimization, it needed a same-window
reconfirmation before being treated as a record update.

## Recipe

Same as the current approved webhie recipe:

```bash
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e
MAX_MODEL_LEN=2048
MAX_NUM_BATCHED_TOKENS=1024
MAX_NUM_SEQS=1
QWEN36_27B_ENABLE_MTP=1
NUM_SPECULATIVE_TOKENS=3
QWEN36_27B_ENABLE_XPU_GRAPH=1
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0
VLLM_XPU_LM_HEAD_INT8=1
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Strict gate: fixed Qwen realistic prompt suite, chat mode, one cold response per
prompt, streamed token-ID timing, primary metric = generated tokens 1-100 after
TTFT, `cached_tokens=0` on every request.

## Results

Timestamp family: `20260704T054644Z`.

| GPU | Median tok/s | p10 tok/s | Mean tok/s | Median TTFT ms | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| 0 | `63.972500904331326` | `54.655039016018286` | `63.52058428086462` | `606.0511196264997` | pass, `cached_tokens=0` |
| 1 | `64.62640783691708` | `57.76457207713447` | `63.941091141099626` | `611.933589912951` | pass, `cached_tokens=0` |
| 2 | `64.74069837801042` | `58.07369898658958` | `64.47551972049962` | `606.674378621392` | pass, `cached_tokens=0` |
| 3 | `64.50624088047778` | `57.81324164687423` | `64.10160591180035` | `609.2428020201623` | pass, `cached_tokens=0` |

Result JSONs (ignored by Git, tracked here by path):

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-reconfirm4gpu-gpu0-mtp3-cg8-20260704T054644Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-reconfirm4gpu-gpu1-mtp3-cg8-20260704T054644Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-reconfirm4gpu-gpu2-mtp3-cg8-20260704T054644Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-reconfirm4gpu-gpu3-mtp3-cg8-20260704T054644Z.json
```

Run directories:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-reconfirm4gpu-gpu0-mtp3-cg8-20260704T054644Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-reconfirm4gpu-gpu1-mtp3-cg8-20260704T054644Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-reconfirm4gpu-gpu2-mtp3-cg8-20260704T054644Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-reconfirm4gpu-gpu3-mtp3-cg8-20260704T054644Z
```

## Interpretation

The `66.389 tok/s` support row did **not** reproduce. Same-window four-GPU
reconfirmation landed at:

- mean of medians: `64.46146199993416 tok/s`;
- stdev of medians: `0.3397392064191827 tok/s`;
- range: `0.7681974736790929 tok/s`;
- range as percent of mean: `1.191715871538687%`.

Decision: no LocalMaxxing update. The approved `65.27648650325429 tok/s` packet
remains the best valid headline result for this model/quant/runtime. Treat
future Qwen27 deltas under roughly `1-1.5%` as inconclusive unless a same-window
or crossover batch agrees.
