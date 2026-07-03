# Qwen3.6 27B INT4 AutoRound vLLM/XPU Lab

This experiment lane tracks bring-up and optimization for:

- Model: `Intel/Qwen3.6-27B-int4-AutoRound`
- Base model: `Qwen/Qwen3.6-27B`
- Quantization: AutoRound INT4, `bits=4`, `group_size=128`, symmetric,
  `packing_format=auto_round:auto_gptq`
- Runtime target: vLLM on Intel XPU / Level Zero
- Hardware target: Intel Arc Pro B70 32 GB, one replica per GPU first

## Immediate Goal

The initial TP1 single-B70 OpenAI-compatible endpoint now works. The next goal
is to turn the working endpoint into measured no-spec/MTP fresh-response
baselines, then optimize.

Completed first milestone:

1. Downloaded/pinned revision `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`.
2. Served one TP1 replica at `max_model_len=2048`.
3. Passed the OpenAI smoke with thinking disabled.
4. Observed healthy MTP2 acceptance (`105/108` accepted draft tokens after
   manual probes plus smoke).

Current evidence:

- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/servers/tp1-gpu0-port19410-20260703T012317Z.log`;
- smoke JSON:
  `data/qwen36-27b-autoround-openai-smoke-20260703T013020Z.json`.

Next milestone:

1. Run no-spec TP1 baseline.
2. Run MTP1/2/3/4 TP1 sweeps with acceptance metrics.
3. Test XPU graph only with correctness gates.
4. Scale to four independent TP1 replicas for parallel optimization.

## Folder Map

- `configs/`: reusable env files.
- `scripts/`: downloader, launcher, smoke, and future benchmark helpers.
- `notes/`: chronological run notes.
- `patches/`: patch snapshots for successful and failed source attempts.
- `results/`: compact experiment summaries.
- `quality/`: quality gates and prompt suites as they mature.
- `localmaxxing/`: queued payloads and response copies after valid records.

## Current Entry Points

```bash
cd /home/steve/llm-optimizations

experiments/qwen36-27b-autoround-int4-b70/scripts/download-model.sh

GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh

BASE_URL=http://127.0.0.1:19410/v1 MODEL=qwen36-27b-int4-autoround \
  experiments/qwen36-27b-autoround-int4-b70/scripts/smoke-openai.sh
```

## External References

- Hugging Face:
  https://huggingface.co/Intel/Qwen3.6-27B-int4-AutoRound
- Base model: https://huggingface.co/Qwen/Qwen3.6-27B
- AutoRound: https://github.com/intel/auto-round
- vLLM Qwen3.6 recipe: https://recipes.vllm.ai/Qwen/Qwen3.6-27B
- vLLM Intel quant docs:
  https://docs.vllm.ai/en/stable/features/quantization/inc/
- LocalMaxxing model index: https://www.localmaxxing.com/en/models
- Local vLLM source: `/home/steve/src/vllm`
