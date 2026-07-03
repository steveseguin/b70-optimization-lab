# 2026-07-03 - Draft-Only Row-Count Screen Collapsed

## Goal

Screen whether `VLLM_XPU_SPEC_DECODE_DRAFT_ONLY=1` can reduce verifier
LM-head rows from `k+1` to `k` under the current Qwen3.6 27B INT4 AutoRound
runtime INT8-LM-head recipe.

This was not intended as a promoted result unless it later passed strict
fresh-response throughput and quality/baseline-match gates. The concern is
that draft-only mode omits the normal target-owned replacement/bonus emission
and relies on later target verification/recompute.

## Command

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-int8lmhead-draftonly-mtp3-cg8-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_SPEC_DECODE_DRAFT_ONLY=1 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Run directory:

`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-int8lmhead-draftonly-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T161411Z/`

## Result

Interrupted as a collapsed diagnostic before completion. It is **not** a valid
benchmark row.

Observed server metrics while still on early suite requests:

```text
Avg generation throughput: ~1.3 tok/s, then ~4.6 tok/s
Mean acceptance length: ~2.6-2.8
Prefix cache hit rate: 0.0%
```

This repeats the known draft-only failure mode from the earlier
`draft-only + local argmax` screen: removing bonus/replacement emission from
the pipeline does not yield a useful decode-rate improvement and can severely
stall the request stream.

## Decision

Closed no-win. Do not promote, submit, or rerun without a new code design.

The next viable route remains true compact/fused LM-head top-1 for exact greedy
verification, preserving target replacement and target-owned bonus semantics.
