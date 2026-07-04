# 2026-07-04 - Webhie BF16-scale runner repro support

## Classification

Strict fresh-response support row for the existing Qwen27 record recipe. This
is not a new recipe, not a new record, and not a LocalMaxxing update.

## Purpose

After adding `scripts/run-vllm-candidate.sh`, run the known best
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head (BF16 scales)` recipe
through the new wrapper to verify:

- the wrapper starts and cleans up the vLLM/XPU server correctly;
- the fixed Qwen realistic suite still passes as a fresh-response gate;
- the current dirty vLLM source can still reproduce the record family within
  expected variance.

Quality was not rerun here (`RUN_QUALITY=0`) because this was a wrapper/repro
smoke for an already quality-gated recipe. New source/config/checkpoint
promotions should run quality before any claim.

## Command

```bash
LABEL=qwen27-webhie-bf16scale-runner-repro \
GPU_INDEX=0 PORT=19420 \
RUN_QUALITY=0 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh \
  > /tmp/qwen27-webhie-runner-repro.out 2>&1
```

## Result

- strict realistic gate: passed;
- `cached_tokens=0`: `12/12`;
- smoke: passed;
- median generated-token throughput, tokens 1-100 after TTFT:
  `64.84180902803895 tok/s`;
- p10: `57.54005638228911`;
- mean: `63.400293020578154`;
- median TTFT: `629.4242680305615 ms`.

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-runner-repro-candidate-summary-20260704T124725Z.json`;
- strict bench:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-runner-repro-realistic128-chat-tokenids-qwensuite-20260704T124725Z.json`;
- smoke:
  `data/qwen36-27b-autoround-int4-b70-baselines/smoke-qwen27-webhie-bf16scale-runner-repro-20260704T124725Z.json`;
- raw run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-webhie-bf16scale-runner-repro-20260704T124725Z`.

## Decision

The result is a valid support row for the existing record family but does not
beat the submitted `65.27648650325429 tok/s` row and is inside the documented
same-window variance band. Do not submit to LocalMaxxing.

The new candidate wrapper is usable for future strict screens. The next
non-cheating optimization action remains either:

1. screen a materially different target checkpoint/quantization as its own
   strict quality-gated result; or
2. return to deeper source work around the dense LM-head producer / verifier
   path.
