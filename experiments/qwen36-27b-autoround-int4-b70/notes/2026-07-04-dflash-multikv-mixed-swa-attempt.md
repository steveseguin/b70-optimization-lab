# 2026-07-04 - DFlash mixed-SWA multi-KV attempt

Status: **startup fixed, endpoint still no-win / unsafe**.

Goal: unblock `z-lab/Qwen3.6-27B-DFlash` mixed full/sliding attention for
Qwen3.6 27B by replacing the single-KV-group DFlash assumption with per-KV-group
draft metadata and slot mappings.

Current record to beat remains the webhie/BF16-scale INT8-LM-head MTP3/cg8
strict fresh result:

```text
65.27648650325429 tok/s
LocalMaxxing cmr5iu3gk00bfq901nidgcana
```

## Patch

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-dflash-multikv-mixed-swa-attempt-20260704.patch
```

The patch includes the earlier preserved DFlash layer-type support plus new
multi-KV-group plumbing:

- `DFlashQwen3Attention` accepts per-layer sliding-window config via
  `VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=mixed`;
- `DFlashProposer.initialize_attn_backend()` no longer uses the generic
  single-KV assertion for DFlash, and instead builds draft `AttentionGroup`s
  over the actual draft KV cache groups;
- the runner attaches per-group `CommonAttentionMetadata` to the legacy drafter
  metadata object for DFlash only;
- DFlash computes context and future-query slot mappings per draft KV group;
- DFlash forward-context slot mappings are now per draft layer, so query KV
  writes no longer use the primary group mapping for all layers;
- `DFlashQwen3Model.precompute_and_store_context_kv()` accepts either one slot
  mapping or `{kv_cache_gid: slot_mapping}` and writes each draft layer with its
  own group mapping.

Validation before runtime:

```text
python3 -m py_compile vllm/v1/spec_decode/dflash.py \
  vllm/model_executor/models/qwen3_dflash.py \
  vllm/v1/worker/gpu_model_runner.py

ruff check vllm/v1/spec_decode/dflash.py \
  vllm/model_executor/models/qwen3_dflash.py
```

Both passed. Full `gpu_model_runner.py` ruff is still noisy from older local
dirty-stack diagnostics, so only the touched DFlash files were style-cleaned.

## Startup Smoke

Command shape:

```bash
GPU_INDEX=1 PORT=19411 \
QWEN36_27B_ENABLE_MTP=0 \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=mixed \
NUM_SPECULATIVE_TOKENS=8 \
GPU_MEMORY_UTILIZATION=0.90 \
MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=1024 MAX_NUM_SEQS=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
VLLM_EXTRA_ARGS='--speculative-config {"method":"dflash","model":"/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash","num_speculative_tokens":8}' \
experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh
```

Run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-dflash-mixed-multikv-startup-smoke-20260704T113030Z
```

Outcome: **READY**. The old assertion is gone.

Key log line:

```text
Initialized DFlash draft attention over KV groups [64, 65, 66, 67, 68]
Graph capturing finished in 2 secs, took 2.53 GiB
```

This is a real architectural milestone: mixed SWA DFlash now initializes and
captures graphs instead of failing immediately with:

```text
AssertionError: All drafting layers should belong to the same kv cache group
```

## Strict Graph Result

Run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-dflash-mixed-multikv-queryslots-k8-cg8-realistic128-chat-tokenids-qwensuite-20260704T113539Z
```

Outcome: **invalid / device lost** during the strict fresh Qwen suite.

The server got through readiness and into streaming generation, then failed on
the second realistic prompt:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
gpu_model_runner.py:_prepare_inputs
self.num_accepted_tokens_event.synchronize()
```

The same signature occurred before and after fixing DFlash forward-context
query slot mappings, so the remaining graph failure is not just the obvious
primary-group query-slot bug.

No LocalMaxxing submission; no result JSON was produced.

## Eager / No-Async Isolation

Run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-dflash-mixed-multikv-eager-noasync-k8-diagnostic-20260704T113817Z
```

Command delta:

```text
QWEN36_27B_ENABLE_XPU_GRAPH=0
COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'
VLLM_EXTRA_ARGS='--no-async-scheduling --speculative-config ...dflash...'
```

Outcome: did not immediately device-lose, but was stopped manually because it
was obviously noncompetitive:

```text
Mean acceptance length: 1.12-1.24
Avg draft acceptance rate: 1.6% -> 3.0% -> 2.2%
generation throughput snapshots: 4.6, 8.2, 12.8 tok/s
```

That is far below the current `65.276 tok/s` strict record and even below the
plain MTP/control families. There is no reason to spend a full strict run on
this configuration.

## Decision

The multi-KV patch is useful as preserved research plumbing, but mixed DFlash
is **not** the next Qwen27 record lane:

- graph mode: initializes but hits `UR_RESULT_ERROR_DEVICE_LOST` during the
  strict suite;
- eager/no-async: avoids immediate device-loss but acceptance is only about
  `2-3%`, making throughput single-digit/low-teens;
- the draft model itself is not accepting enough tokens on these realistic
  prompts, so even a graph stability fix is unlikely to beat MTP3 unless draft
  quality changes materially.

Do not promote or submit any DFlash mixed-SWA result. Future DFlash work should
only continue if one of these changes:

1. a stronger/retuned DFlash drafter appears;
2. graph device-loss is fixed upstream and a quick k-sweep shows materially
   higher acceptance on the fixed realistic suite;
3. the goal is upstream correctness/plumbing, not the Qwen27 throughput record.

Next Qwen27 optimization should move away from DFlash config/runtime sweeps and
back to target-matched drafter quality, true fused/top-ID LM-head producer work,
or a new model lane.
