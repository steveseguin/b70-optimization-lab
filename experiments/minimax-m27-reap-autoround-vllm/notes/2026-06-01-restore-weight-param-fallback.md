# 2026-06-01 Restore-Weight Param Fallback

Goal: explain the restore-weight all-NUL failure and test whether a small
source patch can make restore-weight quality-safe again without losing decode
rate.

## Finding

Finite tracing narrowed the all-NUL restore-weight failure to MiniMax layer 61
QK normalization:

- layer 61 input and `qkv` were finite
- Q/K variance before and after TP allreduce was finite
- `q_after_qk_norm` was finite
- `k_after_qk_norm` contained NaNs and infinities
- attention output, final hidden, sampled hidden, and logits became all-NaN

Artifacts:

- layer-boundary trace:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/restore1-qk0-layer-boundary-trace-20260601T130915Z.jsonl`
- layer 61 attention trace:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/restore1-qk0-layer61-attn-trace-20260601T131343Z.jsonl`
- layer 61 QK-norm trace:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/restore1-qk0-layer61-qknorm-trace-20260601T131616Z.jsonl`

Interpretation: the bad tensor was not caused by attention, logits, sampling, or
OpenAI serialization. K variance was finite, so the likely failing input was the
cached clean XPU weight clone selected by restore-weight mode.

## Patch Tested

Archived patch:

`experiments/minimax-m27-reap-autoround-vllm/patches/vllm-minimax-qk-restore-prefer-param-experiment.patch`

Behavior change:

- default compiled/captured restore-weight QK norm to the live parameter
- for token counts below the CPU check threshold, use the live parameter
- when the live parameter is sane on CPU, use the live parameter
- only use the CPU clean copy to repair a corrupt parameter, then return the
  repaired live parameter

## Results

The patch fixed the failing restore-weight OpenAI quality path.

Restore-weight, qk-helper off:

- cache root:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-restore1-paramweight-fix-ml2048-20260601T131942Z`
- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-paramweightfix-qk0-graph-ml2048-20260601T132305Z.json`
- quality result: passed
- endpoint benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-restore1-paramweightfix-qk0-graph-ml2048-p512n1536-r2-20260601T132432Z.json`
- corrected output tok/s: `82.22418078631115`
- total tok/s: `107.23328748397239`
- warmed direct benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T133722Z.json`
- warmed direct total tok/s: `106.86224461653275`
- warmed direct output-equivalent tok/s: about `80.15`

Restore-weight, qk-helper on:

- cache root:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-restore1-paramweight-fix-qk1-ml2048-20260601T132622Z`
- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-paramweightfix-qk1-graph-ml2048-20260601T132945Z.json`
- quality result: passed
- endpoint benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-restore1-paramweightfix-qk1-graph-ml2048-p512n1536-r2-20260601T133115Z.json`
- corrected output tok/s: `81.94737970396619`
- total tok/s: `106.87729075534929`

## Decision

Do not promote this patch for speed. It is useful correctness evidence and a
possible future restore-weight repair, but the new source hash compiles to the
same low-80s endpoint band and about `80` output-equivalent tok/s direct. The
live vLLM source should be restored to the pre-experiment behavior before the
next speed pass.

Next likely speed target remains recovering or recreating the old
`f728d2c0cf`-class graph behavior without relying on stale AOT payloads.
