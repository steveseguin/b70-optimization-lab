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
has a strict fresh-response BF16-LM-head baseline plus a faster quality-gated
runtime INT8-LM-head variant. Current optimization work must beat the `62.628`
tok/s INT8-head row or improve service/max-context behavior without using
warmed/cache/history effects.

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

Current strict best:

- config: Intel checkpoint, TP1, one B70, XPU graph on, `qwen3_next_mtp`,
  `num_speculative_tokens=3`, `max_cudagraph_capture_size=8`,
  `max_num_batched_tokens=1024`;
- env delta: `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` and
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- gate: Qwen realistic suite, chat mode, 12 unique prompts, each prompt once,
  `cached_tokens=0` every row, `return_token_ids=true`;
- conservative result: median `53.522 tok/s` for generated tokens 1-100 after
  TTFT, p10 `48.406`, mean `53.986`;
- evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json`;
- compact packet:
  `results/qwen36-27b-autoround-int4-b70/promote-source-noacceptedpost-20260703.json`.

Current fastest quality-gated variant:

- label: `AutoRound W4A16 + runtime INT8 LM-head`;
- config: same promote-source MTP3/cg8 recipe plus
  `VLLM_XPU_LM_HEAD_INT8=1`;
- strict fresh median: `62.628 tok/s`, p10 `58.104`, mean `62.998`,
  `cached_tokens=0`;
- repeat: `62.276 tok/s` on GPU3;
- same-window BF16-LM-head control: `53.332 tok/s`;
- full quality gate passed against the BF16-LM-head baseline, including
  1K long-context needle;
- evidence:
  `results/qwen36-27b-autoround-int4-b70/int8-lmhead-20260703.json`;
- patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-quality-pass-20260703.patch`.

Service-oriented INT8-head variant:

- config: same recipe plus `VLLM_XPU_LM_HEAD_INT8_SCOPE=target`;
- strict fresh median: `61.898 tok/s`, p10 `57.494`, mean `62.432`;
- full quality gate passed against the BF16-LM-head baseline;
- interpretation: target verifier LM-head dominates the speedup; draft-only
  INT8 was essentially BF16 control. Use all-head INT8 for the submitted
  max-throughput row, and prefer target-only first for service/max-context work
  because it avoids the extra MTP INT8 LM-head copy;
- note:
  `notes/2026-07-03-int8-lmhead-scope-attribution.md`;
- patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-scope-target-quality-pass-20260703.patch`.

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
4. Investigate LM-head/verifier cost with a real mechanism. Recent no-win
   screens closed output-buffer reuse, bonus-token argmax plumbing, draft-only
   row-count shortcuts, and Python/chunked INT8 top-1. The remaining credible
   lane is a fused LM-head top-1 / candidate-vs-max verifier path that avoids
   materializing `[rows, vocab]` logits and avoids multiple oneDNN GEMM calls.
   The INT8 LM-head path is the fastest quality-gated practical lane, but it
   changes runtime LM-head precision. A same-quantization win still needs exact
   BF16 top-1/candidate-bound work or a cleaner verifier design.
5. Do not keep config-sweeping the current INT8 lane without a new mechanism:
   MTP depth remains k=3, capture size remains cg8, and target-only attribution
   shows the target verifier LM-head is the real bottleneck.

## Folder Map

- `configs/`: reusable env files.
- `scripts/`: downloader, launcher, smoke, and future benchmark helpers.
- `notes/`: chronological run notes.
- `patches/`: patch snapshots for successful and failed source attempts.
- `results/`: compact experiment summaries.
- `quality/`: quality gates and prompt suites as they mature.
- `localmaxxing/`: queued payloads and response copies after valid records.

## Current Research Frontier

The plain MTP3/cg8 strict baseline is about `47.6-48.5 tok/s` on the Qwen
realistic suite. The current promote-source/no-accepted-postprocess result is
`53.5-54.9 tok/s` under the same strict fresh gate. A fast invalid flag,
`VLLM_XPU_GDN_NONSPEC_POSTPROCESS_FULL_ACCEPT=0`, reached `51.273 tok/s` on the
strict suite and `74.877 tok/s` synthetically, but failed 1024-token needle
recall. Tracing explains the lift: the valid path copies large GDN/Mamba state
from the accepted speculative slot back to the running slot after verification.

Current trace summary:
`data/qwen36-27b-autoround-int4-b70-baselines/mamba-copy-trace-summary-mtp3-cg8-p512o128-20260703T042542Z.json`.

The current valid env-only win appears to preserve the accepted-state transition
by reading from the accepted speculative slot as the running source, then
disabling the now-redundant accepted-state postprocess copy. Later timing moved
the current frontier away from that copy path: full LM-head/logits work now
dominates. Bad candidates already closed: blind copy skips, skipping
full-accept state, changing the Triton memcpy block size, exact argmax plumbing
that still computes full logits, draft local-argmax plumbing that still
computes full logits, FP8 LM-head (quality fail), INT8 MTP k2/k4/k5,
INT8 cg4/cg16/cg32, draft-only INT8 LM-head, output-buffer reuse, bonus-token
argmax fast-path, chunked INT8 top-1 argmax-only verification, compressed/full
EAGLE3 (device-loss or too slow), and DFlash (no-win locally).

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
