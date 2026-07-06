# 2026-07-06 - Suppressed-Replacement Recovery Diagnostic

## Context

This is a continuation of the Qwen3.6 27B INT4 AutoRound draft-INT4 lane. The
current valid headline remains:

- `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head (BF16 scales)`
- MTP3 / capture size 8 / one B70 / strict fresh Qwen suite
- median `65.27648650325429 tok/s`
- LocalMaxxing id `cmr5iu3gk00bfq901nidgcana`

The fast target-INT8 + draft-INT4 family can exceed that speed, but prior runs
failed repeat quality (`blue, green, red` vs `blue, green, red, yellow`). Trace
work showed the failure occurs at partial-reject / replacement boundaries: the
target replacement token is target-owned output and is not processed as input in
the packed verifier row, so trusting the packed GDN/DeltaNet state after a
partial reject is not exact.

## Run: suppress replacement, no-preempt eager replacement recovery

Label:

```text
qwen27-draftint4-suppressreplacement-nopreempt-eager-20260706b
```

Command shape:

```bash
VLLM_XPU_LM_HEAD_INT8=1
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
VLLM_XPU_DRAFT_LM_HEAD_INT4=1
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16
VLLM_XPU_SPEC_DECODE_SUPPRESS_REPLACEMENT=1
VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT=1
VLLM_XPU_SPEC_DECODE_NO_PREEMPT_SUPPRESSED_REPLACEMENT=1
VLLM_XPU_SPEC_DECODE_EAGER_REPLACEMENT_RECOVERY=1
VLLM_XPU_SPEC_DECODE_FILTER_SUPPRESSED_BONUS_NEXT_INPUT=0
QWEN36_27B_ENABLE_XPU_GRAPH=1
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
QWEN36_27B_ENABLE_MTP=1
NUM_SPECULATIVE_TOKENS=3
QUALITY_REPEAT_RUNS=64
QUALITY_SKIP_LONG_CONTEXT=1
```

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-suppressreplacement-nopreempt-eager-20260706b-candidate-summary-20260706T032017Z.json`
- strict fresh bench:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-suppressreplacement-nopreempt-eager-20260706b-realistic128-chat-tokenids-qwensuite-20260706T032017Z.json`
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-draftint4-suppressreplacement-nopreempt-eager-20260706b-repeat64-ctx1024-20260706T032017Z.json`
- raw run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-suppressreplacement-nopreempt-eager-20260706b-20260706T032017Z`

Strict fresh gate:

- passed, `cached_tokens=0` on `12/12` prompts
- median tokens 1-100 after TTFT: `66.28430032516718 tok/s`
- p10: `59.95575539051979 tok/s`
- mean: `66.6649766292084 tok/s`
- TTFT median: `490.114810410887 ms`

Quality:

- exact short cases passed
- baseline comparison passed
- repeat64 failed
- repeat distribution:
  - `55/64`: `blue, green, red, yellow`
  - `8/64`: `blue, green, red`
  - `1/64`: `blue, green, red, yellow, yellow, ...`

## Interpretation

This run is **invalid / not promotable**. It proves that suppressing the target
replacement and replaying only a one-token eager replacement path can keep speed
above the current record, but it still trusts the packed accepted-prefix GDN
state. That is not exact at the rejected boundary, so the repeat canary still
finds truncated or runaway color outputs.

The next diagnostic should replay the accepted prefix as well:

```bash
VLLM_XPU_SPEC_DECODE_REPLAY_SUPPRESSED_REPLACEMENT_ACCEPTED=1
VLLM_XPU_SPEC_DECODE_EAGER_ALL_RECOVERY_STEPS=1
VLLM_XPU_SPEC_DECODE_SKIP_REPLAYED_MAMBA_POSTPROCESS=1
```

Expected outcomes:

- If quality passes but speed falls below `65.276`, the exact transaction cost
  explains why ReplaySSM/align remains close but below the record.
- If quality passes and speed stays above `65.276`, it is a credible candidate
  that needs full strict validation and variance confirmation.
- If it still fails, the scheduler-level recovery path is insufficient and the
  next real work is a native graph-safe accepted-prefix GDN/DeltaNet tape or a
  stronger drafter / branch-regenerate design, not more wrapper flag sweeps.

## Repro hygiene note

The candidate runner previously did not record the suppressed-replacement env
flags in `identity.env`. The runner has been updated to include the recovery
and restore flags so later run identities are complete.
