# Qwen27 32K Long-Context MBT Screen

Date: 2026-07-04

Status: **closed service-lane no-win**.

## Purpose

Screen `MAX_NUM_BATCHED_TOKENS` for the current 32K no-parser service lane to
see whether prompt processing / TTFT improves without changing model quality or
the short-context decode recipe.

This is not a short-decode headline result and not a LocalMaxxing candidate.
Completed rows used the fixed deterministic long-context suite, each prompt
once, `cached_tokens=0`, and exact JSON retrieval validation.

## Shared Identity

- Model: `webhie/Qwen3.6-27B-int4-AutoRound`
- Recipe: runtime INT8 LM-head with BF16 scales, MTP3/cg8
- `MAX_MODEL_LEN=32768`
- `QWEN36_27B_REASONING_PARSER=`
- `MAX_TARGET_PROMPT_TOKENS=12288`
- `LONG_MAX_TOKENS=128`
- Suite: `repro/qwen36-27b-autoround-int4-b70/long-context-suite-v1.json`
- Stamp: `20260704T104712Z`

## Results

| MBT | Gate | TTFT median | Approx prefill median | Decode after TTFT median | Wall median | Decision |
|---:|---|---:|---:|---:|---:|---|
| `2048` | pass, `cached_tokens=0`, quality pass | `22.330s` | `176.01 tok/s` | `58.93 tok/s` | `2.68 tok/s` | slower |
| `4096` | pass, `cached_tokens=0`, quality pass | `15.948s` | `207.91 tok/s` | `57.34 tok/s` | `4.65 tok/s` | best completed |
| `8192` | no complete gate | n/a | n/a | n/a | n/a | stalled/negative |

The `8192` arm completed five streamed POSTs, then was still blocked waiting on
the final long request after the `2048` and `4096` arms had completed. It was
interrupted to avoid leaving a stale service process. Treat it as a negative
for this service ladder, not as a valid quality or speed row.

## Decision

Keep `MAX_NUM_BATCHED_TOKENS=4096` for the current 32K no-parser service lane.
Do not switch to `2048` or `8192` for this recipe.

If a future production service change adopts or modifies this setting, rerun
the short strict decode suite afterward to prove the 1-100 after-TTFT decode
record path did not regress.

Compact summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-longctx-mbt-screen-20260704T104712Z-summary.json
```
