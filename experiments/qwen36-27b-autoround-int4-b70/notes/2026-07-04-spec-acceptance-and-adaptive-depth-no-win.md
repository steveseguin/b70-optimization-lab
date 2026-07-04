# Qwen27 Spec Acceptance Trace + Adaptive Depth No-Win

Date: 2026-07-04

## Context

Current strict valid record family remains `webhie/Qwen3.6-27B-int4-AutoRound`
with runtime INT8 LM-head and BF16 scales, MTP3, XPU graph `cg8`, one B70,
strict fresh Qwen realistic suite, `cached_tokens=0` on every request.

The compact full-vocab INT8 LM-head top-1 kernel was closed as exact but slower
than dense oneDNN + argmax. The next question was whether accepted tokens per
target verifier step could be improved or whether low-acceptance prompts were
paying too much for fixed MTP3 depth.

## Baseline Trace

Strict trace run:

- result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-specaccept-trace-20260704T032236Z-20260704T032236Z.json`
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-specaccept-trace-summary-20260704T032236Z.md`
- raw trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-specaccept-trace-20260704T032236Z/spec-trace.jsonl`

Result: valid, strict gate passed, `cached_tokens=0`, median
`64.6350629953815 tok/s`.

Acceptance summary:

- draft steps: `565`
- draft tokens: `1695`
- accepted draft tokens: `974`
- acceptance fraction: `0.5746312684365782`
- mean acceptance length including target: `2.723893805309735`
- emitted tokens per step: `2.697345132743363`
- full-accept rate: `0.3805309734513274`
- accepted histogram: `{0: 122, 1: 127, 2: 101, 3: 215}`
- per-position acceptance: `{0: 0.784070796460177, 1: 0.5592920353982301, 2: 0.3805309734513274}`

Interpretation: throughput strongly tracks emitted tokens per verifier step.
The slowest prompt, `performance-hypotheses`, had only `2.098` mean acceptance
length and `0.180` full-accept rate. That makes accepted-token efficiency a
real bottleneck, but it does not by itself justify shortening MTP depth.

## Adaptive Depth Patch

Patch snapshot:

- `patches/qwen36-27b-autoround-int4-b70/vllm-scheduler-adaptive-spec-depth-no-win-20260704.patch`

What it did:

- added default-off scheduler env flag
  `VLLM_XPU_SPEC_DECODE_ADAPTIVE_DEPTH=1`;
- truncated scheduled verifier draft tokens per request based on recent
  acceptance;
- exposed `VLLM_XPU_SPEC_DECODE_ADAPTIVE_MIN_DEPTH` and
  `VLLM_XPU_SPEC_DECODE_ADAPTIVE_LOW_ACCEPT`;
- added scheduler trace fields for adaptive depth before/after.

The patch preserved target verification semantics and strict validity, but it
was reverted from the active vLLM source after testing because it was a
throughput loss.

## Results

Aggressive policy: `min_depth=1`, `low_accept=1`

- result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-adaptdepth-k3min1-low1-20260704T033026Z-20260704T033026Z.json`
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-adaptdepth-k3min1-low1-20260704T033026Z-20260704T033026Z-acceptance-summary.md`
- raw trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-adaptdepth-k3min1-low1-20260704T033026Z/spec-trace.jsonl`
- strict gate: passed, `cached_tokens=0`
- median: `45.74766924644579 tok/s`
- draft steps: `819`
- emitted tokens per step: `1.8608058608058609`

Same-window comparison:

| run | policy | median tok/s | draft steps | emitted tokens/step | result |
| --- | --- | ---: | ---: | ---: | --- |
| `baseline-samewindow` | fixed MTP3 | `65.98560955205167` | `552` | `2.766304347826087` | valid support, not promoted because within known variance |
| `adaptdepth-k3min2-low0` | shorten only after total rejection, never below 2 | `61.51400286581054` | `627` | `2.43859649122807` | no-win |
| `adaptdepth-k3min2-low1` | shorten after <=1 accepted, never below 2 | `60.91294719531955` | `631` | `2.421553090332805` | no-win |

Same-window artifacts:

- baseline result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-baseline-samewindow-20260704T033352Z-20260704T033352Z.json`
- baseline summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-baseline-samewindow-20260704T033352Z-20260704T033352Z-acceptance-summary.md`
- `min2/low0` result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-adaptdepth-k3min2-low0-20260704T033352Z-20260704T033352Z.json`
- `min2/low0` summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-adaptdepth-k3min2-low0-20260704T033352Z-20260704T033352Z-acceptance-summary.md`
- `min2/low1` result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-adaptdepth-k3min2-low1-20260704T033352Z-20260704T033352Z.json`
- `min2/low1` summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-adaptdepth-k3min2-low1-20260704T033352Z-20260704T033352Z-acceptance-summary.md`

## Conclusion

Adaptive verifier-depth truncation is closed as a no-win. It improves apparent
acceptance fraction in some policies, but it lowers emitted tokens per verifier
step and increases total verifier steps, which dominates throughput.

Do not resume this scheduler-only adaptive-depth lane unless the proposer is
also made dynamically depth-aware or the target verifier row cost changes
substantially. With the current pipeline, fixed MTP3 is better.

Next credible lanes:

1. reduce LM-head/logits call count or rows without reducing accepted
   tokens/step;
2. improve draft quality / accepted tokens per target step while preserving
   exact target verification;
3. investigate whether the proposer can stop generating wasted draft tokens
   dynamically, but only if the target verifier also avoids the extra rows and
   same-window strict validation shows an actual throughput gain.
