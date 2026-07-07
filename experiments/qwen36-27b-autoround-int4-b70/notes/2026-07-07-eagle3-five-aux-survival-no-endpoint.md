# 2026-07-07: EAGLE3 five-aux survival screen no-endpoint

## Classification

Diagnostic stronger-drafter training only. This is not an endpoint benchmark,
not a quality run, and not a LocalMaxxing submission.

## Corpus

Collected a new DFlash/Hipfire-style five-aux corpus from the concrete-context
v6b suite:

```text
run root: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v7-5aux-v6b-4gpu-20260707T095940Z
suite: experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v6b-suite.json
aux layers: 1,16,31,46,61
prompts: 384
usable rows: 61,307
aux rows saved: 61,307
aux bad files: 0
continuity breaks: 0
```

Tracked compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-aux-v7-5aux-corpus-summary-20260707.json
```

## Training screen

Starting checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260707T010510Z/surv-r5-lr2e-5-hard-rank0p1/checkpoint
```

Expanded with:

```text
AUX_COUNT=5
AUX_SOURCE_TARGET_SLOTS=0,2,4
```

Four-GPU survival-objective screen:

```text
run root: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v7-5aux-survival-4gpu-20260707T101117Z
```

Same-heldout expanded-source baseline:

```text
mean accepted: 0.8726213855217715
starts: 14,767
step1 exact: 0.5069411525699195
step2 conditional exact: 0.42612877371092706
```

Best trained variant:

```text
label: surv-r5-lr2e-5-hard-rank0p1
mean accepted: 1.0815331482359314
starts: 14,767
step1 exact: 0.5673461095686327
step2 conditional exact: 0.4904511816662688
step3 conditional exact: 0.46337308347529815
histogram: {0:6389, 1:4269, 2:2205, 3:904, 4:420, 5:580}
```

Tracked compact summaries:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v7-5aux-source-expanded-baseline-20260707.json
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v7-5aux-survival-summary-20260707.json
```

## Interpretation

The new five-aux data is mechanically clean, and training improves the expanded
source checkpoint (`0.873 -> 1.082` mean accepted), but it is **not** an
endpoint candidate:

- below the prior v6b all-scope / hidden-distill diagnostics around `1.10`;
- far below the `1.5-2.0` offline acceptance threshold for endpoint work;
- far below the accepted-depth needed for `>100 tok/s` on Qwen27.

## Decision

Close this first five-aux survival screen as no-endpoint. The tooling remains
useful for future stronger-drafter attempts, but do not endpoint-wire this
checkpoint and do not submit it to LocalMaxxing.

The next accepted-depth experiment would need a real mechanism change, not just
more epochs of the same `fc-lm-head` five-aux survival objective. Plausible
directions:

1. train with a larger/non-compressed draft vocab or a stronger target-matched
   LM head;
2. add candidate-tree/reranker infrastructure that can exploit the documented
   top-k oracle headroom;
3. revisit DFlash architecture itself instead of treating Ex0bit EAGLE3 as the
   only draft body.
