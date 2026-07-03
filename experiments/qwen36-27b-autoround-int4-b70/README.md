# Qwen3.6 27B INT4 AutoRound vLLM/XPU Lab

This experiment lane tracks bring-up and optimization for:

- Model: `Intel/Qwen3.6-27B-int4-AutoRound`
- Base model: `Qwen/Qwen3.6-27B`
- Quantization: AutoRound INT4, `bits=4`, `group_size=128`, symmetric,
  `packing_format=auto_round:auto_gptq`
- Runtime target: vLLM on Intel XPU / Level Zero
- Hardware target: Intel Arc Pro B70 32 GB, one replica per GPU first

## Immediate Goal

The initial TP1 single-B70 OpenAI-compatible endpoint works, and the lane now
has a strict fresh-response baseline. The current task is to beat that baseline
without changing model identity or using warmed/cache/history effects.

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

Current strict baseline:

- config: Intel checkpoint, TP1, one B70, XPU graph on, `qwen3_next_mtp`,
  `num_speculative_tokens=3`, `max_cudagraph_capture_size=8`,
  `max_num_batched_tokens=1024`;
- gate: Qwen realistic suite, chat mode, 12 unique prompts, each prompt once,
  `cached_tokens=0` every row, `return_token_ids=true`;
- result: median `47.624 tok/s` for generated tokens 1-100 after TTFT,
  p10 `43.998`, mean `48.403`;
- evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-realistic128-chat-tokenids-qwensuite-20260703T034112Z.json`.

Synthetic search reference:

- config: MTP5/cg16;
- p512/o512 synthetic `vllm-random`: `81.773 tok/s`;
- evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-specmetrics-p512o512-r3-20260703T031846Z.json`;
- status: diagnostic only. It loses under the realistic chat gate.

Next milestone:

1. Use four independent TP1 replicas for parallel candidate screening.
2. Keep synthetic `vllm-random` metrics diagnostic-only.
3. Rerun the Qwen realistic suite with `--return-token-ids` before promoting
   any change.
4. Investigate GDN/spec accepted-state postprocess and verifier overhead as
   the likely next performance levers.

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

## Local Storage

The pinned Intel snapshot currently lives on the internal NVMe HF cache:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--Intel--Qwen3.6-27B-int4-AutoRound/snapshots/abc86de19eb1ebbf6a7df4582341325c22ddcb7d
```

An external 4 TB USB drive is mounted at `/mnt/usb-models` for overflow model
variants and archived artifacts. Keep active hot-path benchmarks on the
internal NVMe when practical; use `/mnt/usb-models/llm-cache/hf` or
`/mnt/usb-models/models` for additional variants if internal space becomes a
constraint. Do not commit model weights or generated cache contents.

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
