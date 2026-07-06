# 2026-07-06 - Native prefix-base exact-state rescreen is no-win

## Context

This follows `2026-07-06-native-prefix-base-extra-block-partial.md` and
`2026-07-06-native-prefix-target-tail-recovery-no-win.md`.

The July 5 native serial / prefill replay flag screen was run before the July 6
extra Mamba/GDN state block fix. That made the old result partially stale: the
endpoint had only four state columns then, while prefix-base needs base column +
one column per verifier row. After the extra block fix, the fast native
prefix-base endpoint exposed five columns and reached `70.15392515866824 tok/s`
on the strict fresh suite, but failed repeat64 with intermittent
`blue, green, red` truncation.

This screen refreshed the exact native-state replay modes against the fixed
five-column prefix-base layout.

## Important invariant

A side audit of the native GDN/XPU hooks confirmed the real boundary:

- prefix-base state columns, accepted-state promotion, device-side row copies,
  indexed native decode, and ReplaySSM pending commit hooks already exist;
- the target-owned replacement/bonus token is sampled from verifier logits after
  the forward, and its projected `qkvz/ba` input row is not available inside the
  same captured verifier forward;
- therefore a same-forward GDN/DeltaNet transaction cannot exactly process the
  sampled target-owned tail unless a future design provides that projected tail
  row or branches/regenerates the target tail.

This explains why count-only fixes were insufficient and why scheduler-level
rewind of already visible target-owned tokens corrupts request/KV/GDN
alignment.

## Screens

All screens used:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`, revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70, TP1, MTP3, strict fresh Qwen realistic suite;
- each prompt once, `cached_tokens=0`, `return_token_ids=true`;
- target runtime INT8 LM-head BF16 scales;
- draft runtime INT4 LM-head BF16 scales, group size 128;
- XPU graph `PIECEWISE`, `max_cudagraph_capture_size=8`;
- `VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1`;
- repeat16 quality screen with baseline parity against the current ReplaySSM
  draft-INT4 record family.

### exactnative-offset

Label:
`qwen27-prefixbase-extrablock-exactnative-offset-screen-20260706T144845Z`

Extra flags:

```text
VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_SEQUENCE=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_OUTPUT_DECODE_STATE=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_REPLAY_EXACT_SERIAL_STATE=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_EXACT_REPLAY_NATIVE_DECODE=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_EXACT_STATE_OFFSET_PLUS_ONE=1
VLLM_XPU_GDN_SPEC_STATE_OFFSET_PLUS_ONE=1
VLLM_XPU_GDN_SPEC_PROMOTE_RUNNING_OFFSET_PLUS_ONE=1
```

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-extrablock-exactnative-offset-screen-20260706T144845Z-candidate-summary-20260706T144845Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-extrablock-exactnative-offset-screen-20260706T144845Z-realistic128-chat-tokenids-qwensuite-20260706T144845Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-prefixbase-extrablock-exactnative-offset-screen-20260706T144845Z-repeat16-ctx1024-20260706T144845Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-extrablock-exactnative-offset-screen-20260706T144845Z-20260706T144845Z`.

Result:

- strict fresh validity passed, cached tokens all zero;
- median tokens 1-100 after TTFT: `4.899642611042285 tok/s`;
- p10: `3.9507999022373914`, mean: `5.404365037635524`;
- repeat16 stable, but `json_schema` failed and baseline parity failed.

Decision: invalid and far too slow.

### exactnative-writeout

Label:
`qwen27-prefixbase-extrablock-exactnative-writeout-screen-20260706T144937Z`

Same as `exactnative-offset`, plus:

```text
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_EXACT_REPLAY_WRITE_OUTPUTS=1
```

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-extrablock-exactnative-writeout-screen-20260706T144937Z-candidate-summary-20260706T144937Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-extrablock-exactnative-writeout-screen-20260706T144937Z-realistic128-chat-tokenids-qwensuite-20260706T144937Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-prefixbase-extrablock-exactnative-writeout-screen-20260706T144937Z-repeat16-ctx1024-20260706T144937Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-extrablock-exactnative-writeout-screen-20260706T144937Z-20260706T144937Z`.

Result:

- strict fresh validity passed, cached tokens all zero;
- median tokens 1-100 after TTFT: `4.629096227023183 tok/s`;
- p10: `3.9543961914489247`, mean: `5.308837283630807`;
- repeat16 stable, but `json_schema` failed and baseline parity failed.

Decision: invalid and far too slow.

### prefill-columns-prefixes

Label:
`qwen27-prefixbase-extrablock-prefill-columns-screen-20260706T145019Z`

Extra flags:

```text
VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_SEQUENCE=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_OUTPUT_DECODE_STATE=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_OUTPUT_REPLAY_COLUMNS=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_OUTPUT_REPLAY_PREFIXES=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_BACKUP_STATE_COLUMN=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_PREPROMOTE=1
VLLM_XPU_GDN_SPEC_STATE_OFFSET_PLUS_ONE=1
VLLM_XPU_GDN_SPEC_PROMOTE_RUNNING_OFFSET_PLUS_ONE=1
```

Run dir:
`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-extrablock-prefill-columns-screen-20260706T145019Z-20260706T145019Z`

Result:

- aborted during the strict suite;
- server metrics showed acceptance collapsed to zero:
  `Mean acceptance length: 1.00`, `Accepted: 0`, `Drafted: 60`,
  per-position acceptance `0.000, 0.000, 0.000`;
- generation throughput was about `2.0 tok/s`;
- the benchmark client was interrupted, so there is no valid benchmark summary.

Decision: aborted no-win. This refreshed the older
`prefill-columns-prefixes` conclusion under the fixed prefix-base state layout:
state-column rebuild remains unusable.

### replaypartial

Label:
`qwen27-prefixbase-extrablock-replaypartial-screen-20260706T145103Z`

Extra flags:

```text
VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_SEQUENCE=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_OUTPUT_DECODE_STATE=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_REPLAY_PARTIAL_PREFIX=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_BACKUP_STATE_COLUMN=1
VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_PREPROMOTE=1
VLLM_XPU_GDN_SPEC_STATE_OFFSET_PLUS_ONE=1
VLLM_XPU_GDN_SPEC_PROMOTE_RUNNING_OFFSET_PLUS_ONE=1
```

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-extrablock-replaypartial-screen-20260706T145103Z-candidate-summary-20260706T145103Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-extrablock-replaypartial-screen-20260706T145103Z-realistic128-chat-tokenids-qwensuite-20260706T145103Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-prefixbase-extrablock-replaypartial-screen-20260706T145103Z-repeat16-ctx1024-20260706T145103Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-extrablock-replaypartial-screen-20260706T145103Z-20260706T145103Z`.

Result:

- strict fresh validity passed, cached tokens all zero;
- median tokens 1-100 after TTFT: `6.322542822578319 tok/s`;
- p10: `4.595976427751276`, mean: `6.083784941366886`;
- exact quality and repeat16 passed, but baseline parity failed and the speed is
  unusable.

Decision: correctness-diagnostic only, not a speed path.

## Conclusion

The stale July 5 native exact-state replay flags are still no-win after the
July 6 prefix-base extra-block fix. They do not rescue the fast `70 tok/s`
native prefix-base lane, and the modes that improve local state correctness
collapse throughput into single digits.

Do not continue native serial / prefill replay flag roulette. The useful
technical conclusion is narrower:

- exact prefix-state selection can be made stable, but it is too slow when
  rebuilt with current Python/native replay loops;
- exact target-owned tail state cannot be committed inside the same verifier
  forward because the sampled tail token has no projected input row yet;
- future fast-and-correct work needs a design that either provides/branches the
  target tail projection, uses a stronger drafter that avoids the reject tail
  boundary more often, or implements a real fixed-buffer GDN/DeltaNet tape that
  can replay only the needed accepted prefix at low cost.

LocalMaxxing: no submission. No result here is valid and above the current
`68.23626314761921 tok/s` quality-gated record.
