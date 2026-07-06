# 2026-07-06 - Native prefix-base extra Mamba block is partial only

## Context

This follows `2026-07-06-native-prefix-base-state-invalid.md`. The earlier
prefix-base GDN state contract looked internally correct in the standalone
native checker, but the real endpoint still allocated only four Mamba/GDN state
columns for MTP3. A prefix-base layout needs one base/running-state column plus
one column per verifier row, so the endpoint must expose five columns for this
configuration.

## Source change

Patch snapshot:

`patches/qwen36-27b-autoround-int4-b70/qwen27-native-prefix-base-extra-block-partial-20260706.patch`

Later no-win source deltas for the count-correction and force-single recovery
attempts are preserved at:

`patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-native-prefix-base-count-and-reject-recovery-no-win-20260706.patch`

The patch gates one extra speculative Mamba state block behind
`VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1` when speculative decode is active
and `mamba_cache_mode != all`.

This is not promoted as a production patch yet. It is preserved because it
solves a real allocator/table-width blocker for the native prefix-base lane.

## Static and synthetic checks

Standalone checker:

```bash
cd /home/steve/llm-optimizations
source /home/steve/.venvs/vllm-xpu/bin/activate
PYTHONPATH=/home/steve/src/vllm python scripts/check-gdn-native-spec-prefix.py \
  --device xpu:1 --spec-len 4 --prefix-base-state \
  --json-out data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-spec-prefix-base-extra-block-20260706T125001Z.json
```

Result: `passed: true`.

Static compile:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  /home/steve/src/vllm/vllm/model_executor/layers/mamba/abstract.py
```

Result: pass.

## Endpoint metadata traces

First attempt, with an earlier align-only guard, was inert because the live
Qwen27 recipe uses `mamba_cache_mode=none`. It still exposed only four columns
and hit the same old device-lost path:

`data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-prefixbase-extra-block-metatrace-20260706T125149Z/metadata.jsonl`

After changing the guard to `mamba_cache_mode != all`, endpoint smoke passed and
the metadata trace proved the allocator/table width was fixed:

`data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-prefixbase-extra-block-metatrace-20260706T125427Z/metadata.jsonl`

Key fields from the passing smoke trace:

```json
{
  "block_table_tensor": {"shape": [1, 5], "head": [1, 2, 3, 4, 5]},
  "spec_state_cols": 5,
  "num_spec_decode_tokens": 4,
  "max_query_len": 4
}
```

The smoke response was correct and `cached_tokens=0`:

`data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-prefixbase-extra-block-metatrace-20260706T125427Z/smoke.json`

## Full candidate: async graph path

Label:
`qwen27-draftint4-native-prefixbase-extrablock-20260706T125635Z`

Important identity:

- model: `webhie/Qwen3.6-27B-int4-AutoRound` revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70 GPU, TP1, MTP3, strict fresh realistic suite;
- target runtime INT8 LM-head with BF16 scales;
- draft runtime INT4 LM-head, group size 128, BF16 scales;
- XPU graph `PIECEWISE`, `max_cudagraph_capture_size=8`;
- `VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`.

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-extrablock-20260706T125635Z-candidate-summary-20260706T125635Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-extrablock-20260706T125635Z-realistic128-chat-tokenids-qwensuite-20260706T125635Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-draftint4-native-prefixbase-extrablock-20260706T125635Z-repeat64-ctx1024-20260706T125635Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-native-prefixbase-extrablock-20260706T125635Z-20260706T125635Z`.

Result:

- strict fresh validity: pass, each prompt once, `cached_tokens=0`;
- median tokens 1-100 after TTFT: `70.15392515866824 tok/s`;
- p10: `63.74587743843879`;
- mean: `69.7345343635239`;
- median TTFT: `625.9184629889205 ms`;
- smoke: pass;
- exact quality cases: pass;
- long-context quality: pass;
- baseline-match checks: pass;
- repeat64: fail.

Repeat64 distribution:

- `62/64` `blue, green, red, yellow`;
- `2/64` `blue, green, red` at repeat indices `21` and `52`.

This is the fastest strict fresh candidate seen in this native prefix-base lane,
but it is not valid and must not be submitted to LocalMaxxing.

## Full candidate: no-async diagnostic

Label:
`qwen27-draftint4-native-prefixbase-extrablock-noasync-20260706T130209Z`

Same recipe as above, plus `VLLM_EXTRA_ARGS=--no-async-scheduling`.

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-extrablock-noasync-20260706T130209Z-candidate-summary-20260706T130209Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-prefixbase-extrablock-noasync-20260706T130209Z-realistic128-chat-tokenids-qwensuite-20260706T130209Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-draftint4-native-prefixbase-extrablock-noasync-20260706T130209Z-repeat64-ctx1024-20260706T130209Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-native-prefixbase-extrablock-noasync-20260706T130209Z-20260706T130209Z`.

Result:

- strict fresh validity: pass, each prompt once, `cached_tokens=0`;
- median tokens 1-100 after TTFT: `65.22720118804193 tok/s`;
- p10: `58.335724100825054`;
- mean: `65.31848360218619`;
- exact copy-phrase quality: fail;
- repeat64: fail.

Repeat64 distribution:

- `49/64` `blue, green, red, yellow`;
- `13/64` `blue, green, red`;
- `2/64` long wrong color continuations.

No-async is slower and less stable. Do not pursue it for this lane.

## Interpretation

The extra Mamba state block fixes the concrete endpoint allocator/block-table
width problem. That is real progress versus v3, where the endpoint clamped to
four columns and device-lost.

The remaining failure is narrower: repeat instability around accepted-prefix /
replacement / bonus handling. The dominant invalid output is an early stop after
`blue, green, red`, not the broad multi-output chaos from the earlier prefix-base
runs. That suggests the next useful work is a targeted trace or transaction fix
around accepted counts, replacement rows, bonus-token accounting, and GDN state
commit/rollback, not more allocator/source-column sweeps.

LocalMaxxing status: no submission. The speed path is promising, but quality is
not valid.

## Follow-up trace: repeat failure is target-state drift, not formatting

Trace label:
`qwen27-prefixbase-extrablock-repeattrace-20260706T131422Z`

Artifacts:

- compact summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-prefixbase-extrablock-repeattrace-20260706T131422Z/summary.json`;
- selected request digest:
  `data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-prefixbase-extrablock-repeattrace-20260706T131422Z/repeat-request-digest.json`;
- COW/spec trace directory:
  `data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-prefixbase-extrablock-repeattrace-20260706T131422Z/`;
- raw run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-extrablock-repeattrace-20260706T131422Z`.

Repeat result: `77/80` correct `blue, green, red, yellow`; `3/80` bad
`blue, green, red`. Bad repeat indices were `3`, `34`, and `65`; all had
`cached_tokens=0`.

The bad rows are diagnostic. The verifier trace shows the final color step
itself changes target argmax:

- correct row: draft `[11, 2438, 11]`, target `[11, 2438, 11]`, output
  `[11, 2438, 11, 13358]` -> `, red, yellow`;
- bad row: draft `[11, 2438, 248046]`, target `[11, 2438, 248044]`, output
  `[11, 2438, 248044]` -> `, red, EOS`.

So this is not a tokenizer/normalization issue or a post-sampling formatting
artifact. The target verifier is seeing a different recurrent state/context
before the `red` row and chooses EOS where the correct state chooses comma /
yellow. The immediately preceding green row is a partial reject: draft
`[11, 3565, 11]`, target `[11, 5983, 11]`, output `[11, 5983]`,
`prefix_accepted=1`. That points at accepted-prefix / replacement / bonus
state transaction handling after partial reject.

Important negative detail: the COW trace still reports placeholder
`scheduled_spec_ids=[-1, -1, -1]`, but the verifier trace has concrete draft
IDs. Any recovery that depends on scheduler-visible concrete scheduled IDs can
miss Qwen's intrinsic MTP proposals. Recovery should key off verifier output /
accepted counts / replacement mask semantics, not only stored scheduled IDs.

Next credible test: combine this extra-state-block patch with the older
suppressed-replacement accepted-prefix replay path that was previously closed
before the allocator width fix existed:

```bash
VLLM_XPU_SPEC_DECODE_SUPPRESS_REPLACEMENT=1
VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT=1
VLLM_XPU_SPEC_DECODE_NO_PREEMPT_SUPPRESSED_REPLACEMENT=1
VLLM_XPU_SPEC_DECODE_REPLAY_SUPPRESSED_REPLACEMENT_ACCEPTED=1
VLLM_XPU_SPEC_DECODE_EAGER_REPLACEMENT_RECOVERY=1
VLLM_XPU_SPEC_DECODE_EAGER_ALL_RECOVERY_STEPS=1
VLLM_XPU_SPEC_DECODE_SKIP_REPLAYED_MAMBA_POSTPROCESS=1
```

Expected interpretation:

- if quality passes above the `67.519` record, this becomes a real candidate
  needing variance confirmation;
- if quality passes but speed falls below the record, it closes this Python /
  scheduler-level transaction path as correctness-only overhead;
- if quality still fails, the needed fix is a native graph-safe
  accepted-prefix GDN/DeltaNet transaction rather than more wrapper flags.

## Accepted-prefix replay candidate: still invalid and slower

Run timestamp: `20260706T132058Z`.

Important caveat: the runner ignored the positional label and used its default
`qwen27-candidate`; identify this run by timestamp and identity file.

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-candidate-candidate-summary-20260706T132058Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-candidate-realistic128-chat-tokenids-qwensuite-20260706T132058Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-candidate-repeat64-ctx1024-20260706T132058Z.json`;
- identity:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-candidate-20260706T132058Z/identity.env`;
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-candidate-20260706T132058Z/server.stdout.log`.

Flags confirmed active in `identity.env`:

```text
gdn_native_spec_prefix_base_state=1
spec_suppress_replacement=1
spec_recover_suppressed_replacement=1
spec_no_preempt_suppressed_replacement=1
spec_replay_suppressed_replacement_accepted=1
spec_eager_replacement_recovery=1
spec_eager_all_recovery_steps=1
spec_skip_replayed_mamba_postprocess=1
lm_head_int8=1
draft_lm_head_int4=1
```

Result:

- strict fresh gate: pass, `cached_tokens=0` on all 12 prompts;
- median tokens 1-100 after TTFT: `65.38651871407903 tok/s`;
- p10: `59.46921132349165`;
- mean: `65.09343500490444`;
- TTFT median: `605.639121029526 ms`;
- exact cases: pass;
- long context: pass;
- baseline match: pass;
- repeat64: fail.

Repeat64 distribution:

- `62/64` `blue, green, red, yellow`;
- `2/64` `blue, green, red` at repeat indices `21` and `52`.

Conclusion: accepted-prefix replay through the existing Python/scheduler
recovery path does not fix the native prefix-base truncation and is below the
current `67.519` strict record. Do not repeat this exact flag combination. The
remaining credible direction is a source-level native transaction for
partial-reject accepted-prefix state, or a stronger drafter/branch-regenerate
path that avoids this recurrent-state boundary.

## Accepted-prefix replay with placeholder suppression kept: worse / invalid

The previous run did not set
`VLLM_XPU_SPEC_DECODE_KEEP_PLACEHOLDER_REPLACEMENT_SUPPRESSION=1`, so
`_xpu_clear_placeholder_only_replacement_suppression()` likely disabled the
replacement recovery path for Qwen intrinsic-MTP placeholder rows. A follow-up
kept placeholder suppression enabled.

Label:
`qwen27-prefixbase-extrablock-replayaccepted-keepph-20260706T132738Z`

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-extrablock-replayaccepted-keepph-20260706T132738Z-candidate-summary-20260706T132738Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-extrablock-replayaccepted-keepph-20260706T132738Z-realistic128-chat-tokenids-qwensuite-20260706T132738Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-prefixbase-extrablock-replayaccepted-keepph-20260706T132738Z-repeat64-ctx1024-20260706T132738Z.json`;
- identity:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-extrablock-replayaccepted-keepph-20260706T132738Z-20260706T132738Z/identity.env`.

Result:

- strict fresh gate: pass, `cached_tokens=0` on all 12 prompts;
- median tokens 1-100 after TTFT: `22.664442961874933 tok/s`;
- p10: `18.19387303673967`;
- mean: `21.44248602132261`;
- exact short cases: pass;
- long context: pass;
- baseline match: fail;
- repeat64: fail hard.

Repeat64 distribution:

- `49/64` `blue, green, red, green orange, orange, red, red,`;
- `8/64` `blue, green, red, green orange, red, red, yellow`;
- plus several other wrong continuations / loops.

Conclusion: keeping placeholder replacement suppression makes the old
scheduler replay path actually run, but it is far too slow and corrupts the
state/output badly. This definitively closes the existing
suppressed-replacement replay machinery for this native prefix-base lane.

Follow-up audit found the cleaner bug: `_update_states_after_model_execute`
uses `(output_token_ids != -1).sum(dim=1)` as both the scheduler-visible output
count and the GDN/Mamba state promotion count. For rows with a target-owned
tail, those are different. Example:

- partial reject output `[comma, green]` has visible count `2`, but accepted
  draft-prefix count `1`;
- full accept output `[draft1, draft2, draft3, bonus]` has visible count `4`,
  but accepted draft-prefix count `3`.

With prefix-base native GDN state, feeding the visible count can promote the
state column that corresponds to processing an unaccepted draft token rather
than the target-owned replacement/bonus. That matches the trace where the next
target verifier row chooses EOS after `red`. Next patch should keep raw visible
counts for scheduler accounting, but feed GDN/Mamba a separate accepted
draft-prefix count for native prefix-base spec rows.

## Source patch v1: subtract target-owned tail for every spec row is too broad

Patch idea:
`VLLM_XPU_GDN_NATIVE_SPEC_DRAFT_PREFIX_STATE_COUNTS=1` converts every native
prefix-base speculative row from visible output count to accepted draft-prefix
count (`visible_count - 1`, clamped to `[0, k]`) before writing
`self.num_accepted_tokens.gpu`.

Label:
`qwen27-prefixbase-draftprefixcounts-20260706T133610Z`

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-draftprefixcounts-20260706T133610Z-candidate-summary-20260706T133610Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-draftprefixcounts-20260706T133610Z-realistic128-chat-tokenids-qwensuite-20260706T133610Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-prefixbase-draftprefixcounts-20260706T133610Z-repeat64-ctx1024-20260706T133610Z.json`;
- identity:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-draftprefixcounts-20260706T133610Z-20260706T133610Z/identity.env`.

Result:

- strict fresh gate: pass, `cached_tokens=0` on all 12 prompts;
- median tokens 1-100 after TTFT: `65.72116414955374 tok/s`;
- p10: `58.25646277555236`;
- mean: `66.29141109774865`;
- exact `copy_phrase`: fail (`satin`);
- repeat64: fail.

Repeat64 distribution:

- `54/64` `blue, green, red, yellow`;
- `8/64` `blue, green, red`;
- `2/64` runaway color continuations.

Conclusion: converting all spec rows to draft-prefix counts is too broad and
breaks full-accept/bonus behavior. The likely refinement is to correct only
replacement / partial-reject rows (`visible_count <= num_draft_tokens`, same
condition as `_xpu_spec_decode_replacement_mask`) and leave full-accept+bonus
rows on the existing visible-count convention.

## Source patch v2: replacement-only state-count correction still invalid

Patch idea:
`VLLM_XPU_GDN_NATIVE_SPEC_REPLACEMENT_PREFIX_STATE_COUNTS=1` corrects only
replacement / partial-reject rows. If `visible_count <= k`, it writes
`visible_count - 1` to `num_accepted_tokens`; full-accept+bonus rows keep the
existing visible-count convention.

Label:
`qwen27-prefixbase-replprefixcounts-20260706T134111Z`

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-replprefixcounts-20260706T134111Z-candidate-summary-20260706T134111Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-replprefixcounts-20260706T134111Z-realistic128-chat-tokenids-qwensuite-20260706T134111Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-prefixbase-replprefixcounts-20260706T134111Z-repeat64-ctx1024-20260706T134111Z.json`;
- identity:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-replprefixcounts-20260706T134111Z-20260706T134111Z/identity.env`.

Result:

- strict fresh gate: pass, `cached_tokens=0` on all 12 prompts;
- median tokens 1-100 after TTFT: `65.75012212297545 tok/s`;
- p10: `58.17254789889372`;
- mean: `66.10374511140058`;
- exact `copy_phrase`: fail (`satin`);
- repeat64: fail.

Repeat64 distribution matched v1:

- `54/64` `blue, green, red, yellow`;
- `8/64` `blue, green, red`;
- `2/64` runaway color continuations.

Conclusion: state-count correction alone is not sufficient. The native
prefix-base transaction likely also needs to process the target-owned
replacement/bonus as the next ordinary input before the next packed verifier
row, or move that replacement update into a native graph-safe GDN/DeltaNet
transaction. Do not repeat simple count-only variants.

## Source patch v3: force single-token recovery after draft reject is no-win

Patch idea:
`VLLM_XPU_SPEC_DECODE_FORCE_SINGLE_AFTER_DRAFT_REJECT=1` adds a default-off
scheduler hook for the normal verifier path: after any partial reject
(`num_rejected > 0`, non-draft-only), clear next-step spec decode and force the
next one-token recovery step. The run also set
`VLLM_XPU_SPEC_DECODE_EAGER_DRAFT_REJECT_RECOVERY=1` so that recovery token
does not immediately use a captured graph.

Label:
`qwen27-prefixbase-forcesingle-reject-20260706T134711Z`

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-forcesingle-reject-20260706T134711Z-candidate-summary-20260706T134711Z.json`;
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-forcesingle-reject-20260706T134711Z-realistic128-chat-tokenids-qwensuite-20260706T134711Z.json`;
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-prefixbase-forcesingle-reject-20260706T134711Z-repeat64-ctx1024-20260706T134711Z.json`;
- identity:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-forcesingle-reject-20260706T134711Z-20260706T134711Z/identity.env`.

Result:

- strict fresh gate: pass, `cached_tokens=0` on all 12 prompts;
- median tokens 1-100 after TTFT: `42.79316359139658 tok/s`;
- p10: `36.92551844913753`;
- mean: `44.78083983642381`;
- exact `copy_phrase`: fail (`satin`);
- repeat64: fail hard.

Repeat64 distribution:

- `38/64` correct `blue, green, red, yellow`;
- many wrong continuations / loops, including extra colors and repetitions;
- only `2/64` were the original truncated `blue, green, red` signature.

Conclusion: forcing ordinary recovery after every partial reject is too slow
and still not exact. This closes the cheap wrapper/scheduler recovery attempts
for the native prefix-base lane. Remaining credible work is no longer a flag
sweep: it needs a native graph-safe accepted-prefix/replacement GDN transaction
or a different drafter/branch-regenerate path that avoids this target-owned
replacement boundary.
