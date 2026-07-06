# 2026-07-06: Replacement Mask Plumbing And Margin Recovery No-Win

## Summary

This lane tested whether the fast target-INT8 + draft-INT4 Qwen27 path could be
made quality-correct by suppressing target-owned replacement tokens from packed
spec-decode rows, then replaying or recomputing the affected tail normally.

Conclusion: the fast `66-67 tok/s` rows were mostly inert because the
replacement-suppression mask was not reaching the scheduler. Once the mask was
actually active, exact scheduler-level recovery passed quality only at
`~34-49 tok/s`, well below the current strict record of `65.276 tok/s`.
Replacement-margin gating was not enough to recover performance while keeping
quality.

Do not promote or submit these rows. The useful result is diagnostic: Python /
scheduler-level active recovery is too expensive. The next credible path is a
native graph-safe GDN/DeltaNet accepted-prefix transaction, not more margin or
placeholder-mask flag sweeps.

## Context

Current valid record for this lane:

- model/runtime label: `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8
  LM-head (BF16 scales)`;
- one Intel Arc Pro B70, TP1, vLLM/XPU, MTP3/cg8;
- strict fresh Qwen realistic suite, 12 unique prompts, each prompt once,
  `cached_tokens=0`, `return_token_ids=true`;
- headline: `65.27648650325429 tok/s` median for generated tokens 1-100 after
  TTFT;
- LocalMaxxing: `cmr5iu3gk00bfq901nidgcana`;
- packet: `results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json`.

The draft-INT4 family was attractive because several rows reached `66-72 tok/s`
diagnostically, but repeat quality consistently failed with the color-order
signature (`blue, green, red` / `blue, green, red, yellow`).

## Source Findings

The run loop found two mask plumbing issues:

1. `RejectionSampler.forward_from_top_token_ids()` did not populate
   `xpu_suppressed_replacement_mask`, so local-argmax / top-token-ID verify
   paths never told the scheduler to recover replacement rows.
2. `_xpu_clear_placeholder_only_replacement_suppression()` cleared replacement
   masks for placeholder-only scheduled spec rows. That was intended for
   DFlash-style internally owned draft proposals, but Qwen MTP also schedules
   placeholder spec IDs (`[-1, -1, -1]`), so it erased the Qwen recovery mask.

A default-off override was added for diagnostics:

```text
VLLM_XPU_SPEC_DECODE_KEEP_PLACEHOLDER_REPLACEMENT_SUPPRESSION=1
```

After that override, the scheduler received active suppression masks. Full
accepted-prefix replay became extremely slow and still failed quality. Tail
rollback / replacement recompute was quality-clean, but too slow to beat the
record.

## Results

All rows used the fixed realistic fresh-response suite for throughput, with
`cached_tokens=0` on every request. Quality status is from the candidate
runner's repeat/exact suite. These are diagnostic rows, not submissions.

| label | tok/s | p10 | mean | quality | interpretation |
|---|---:|---:|---:|---|---|
| `qwen27-webhie-bf16scale-control-samewindow-20260706c` | 63.890 | 56.574 | 63.262 | pass | same-window control; below record, likely variance/contention |
| `qwen27-draftint4-suppressreplacement-nopreempt-eager-20260706b` | 66.284 | 59.956 | 66.665 | fail | fast but invalid; mask later proved mostly inert |
| `qwen27-draftint4-replayaccepted-eagerall-skippost-20260706` | 66.015 | 59.998 | 65.457 | fail | accepted-prefix replay did not receive replacement suppression |
| `qwen27-draftint4-replayaccepted-eagerall-postprocess-20260706` | 66.219 | 59.798 | 65.150 | fail | same |
| `qwen27-draftint4-suppressreplacement-preempt-resume-20260706` | 66.136 | 59.933 | 65.399 | fail | same |
| `qwen27-draftint4-replayaccepted-eagerall-plusreplacement-skippost-20260706` | 67.618 | 61.006 | 66.770 | fail | recovery counter included replacement, but mask was still absent |
| `qwen27-draftint4-replayaccepted-eagerall-plusreplacement-postprocess-20260706` | 67.510 | 60.895 | 66.838 | fail | same |
| `qwen27-draftint4-topidsmask-replayaccepted-skippost-20260706` | 65.953 | 59.811 | 66.057 | fail | top-token path mask created; placeholder clear still erased it |
| `qwen27-draftint4-topidsmask-replayaccepted-postprocess-20260706` | 67.457 | 60.978 | 66.623 | fail | same; fastest invalid row in this family |
| `qwen27-draftint4-keepplaceholder-replayaccepted-skippost-20260706` | 20.756 | 14.557 | 25.822 | fail | mask active; full accepted-prefix replay too slow and still invalid |
| `qwen27-draftint4-keepplaceholder-replayaccepted-postprocess-20260706` | 24.828 | 14.205 | 27.351 | fail | mask active; full accepted-prefix replay too slow and still invalid |
| `qwen27-draftint4-keepplaceholder-tailrollback-eagerreplacement-20260706` | 33.967 | 24.257 | 36.908 | pass | mask active; quality clean but far below record |
| `qwen27-draftint4-keepplaceholder-tailrollback-compiledreplacement-20260706` | 46.887 | 33.016 | 48.036 | pass | mask active; quality clean but far below record |
| `qwen27-draftint4-margin05-tailrollback-20260706` | 49.751 | 44.807 | 51.507 | fail | margin gate insufficient |
| `qwen27-draftint4-margin1-tailrollback-20260706` | 46.276 | 43.391 | 51.184 | fail | margin gate insufficient |
| `qwen27-draftint4-margin2-tailrollback-20260706` | 51.302 | 40.454 | 52.407 | fail | margin gate insufficient |
| `qwen27-draftint4-margin4-tailrollback-20260706` | 48.768 | 40.352 | 50.096 | pass | quality clean but far below record |

Representative compact summaries:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-suppressreplacement-nopreempt-eager-20260706b-candidate-summary-20260706T032017Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-topidsmask-replayaccepted-postprocess-20260706-candidate-summary-20260706T034518Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-keepplaceholder-tailrollback-compiledreplacement-20260706-candidate-summary-20260706T035928Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-margin4-tailrollback-20260706-candidate-summary-20260706T040459Z.json`

Raw run directories are under:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/
```

## Patch Artifact

Focused source snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replacement-mask-plumbing-margin-no-win-20260706.patch
```

That patch captures the diagnostic code hooks only:

- top-token-ID replacement mask propagation;
- placeholder replacement-suppression override;
- eager replacement recovery counter including the target-owned replacement;
- k>1 replacement-margin gate.

The active vLLM worktree had other experiment edits, so the patch is intentionally
focused rather than a full `git diff`.

## Decision

Closed as no-win for promotion. Active replacement recovery is either invalid
when the mask does not reach the scheduler, or too slow when it does.

Recommended next implementation lane:

1. Preserve the current `65.276 tok/s` webhie/BF16-scale INT8-LM-head recipe as
   the valid baseline.
2. Stop running scheduler-level margin/replay sweeps for replacement rows.
3. Build a native exact accepted-prefix GDN/DeltaNet state transaction, with
   GPU-side state commit/rollback that does not replay visible tokens through
   Python scheduling.
4. Reuse `scripts/check-gdn-spec-recurrent-exact.py` and
   `scripts/check-gdn-native-spec-prefix.py` as parity contracts before endpoint
   validation.

