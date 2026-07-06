# 2026-07-06: Ex0bit EAGLE3 target-adaptation screen

## Classification

Diagnostic only. No endpoint run, no throughput claim, no LocalMaxxing
submission.

## Objective

After the off-the-shelf Ex0bit EAGLE3/DFlash checkpoints showed unusably low
offline acceptance on the target-owned Qwen27 AutoRound aux corpus, test whether
small target-matched adaptation can move accepted depth enough to justify a
larger EAGLE3/DFlash training lane.

## New artifact

`scripts/train-qwen27-ex0bit-eagle3-adapter.py`

The trainer loads the same Ex0bit-format checkpoint as the offline evaluator,
consumes `qwen36_eagle_sequence_v2` aux samples, maps target labels through
`d2t` for compressed checkpoints, supports `lm-head`, `fc-lm-head`, and `all`
training scopes, and exports a vLLM-loadable Ex0bit-style `model.safetensors`
plus `training_meta.json`.

## Baseline

Original compressed Ex0bit on the same shard-3 heldout window:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-headadapt-screen-20260706T194845Z/original-heldout-samewindow-summary.json
```

- starts: `2048`
- mean accepted: `0.2890625`
- step-1 exact: `24.414%`
- histogram: `0=1548`, `1=417`, `2=74`, `3=9`

All-corpus original compressed reference:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-offline-eval-all-20260706T194103Z/compressed-all-summary.json
```

- starts: `14784`
- mean accepted: `0.289908`

## Screens

### 1. LM-head only, 4,096 train rows

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-headadapt-screen-20260706T194845Z
```

Training:

- scope: `lm-head`
- train rows: `4096` from shards 0-2
- heldout rows: `2048` from shard 3
- epochs: `2`
- lr: `2e-5`

Result:

- teacher-forced heldout exact: `27.78%`
- rollout heldout mean accepted: `0.31640625`

Conclusion: real but too small; head calibration alone is not enough.

### 2. FC + LM-head, 4,096 train rows

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-fcheadadapt-screen-20260706T195019Z
```

Training:

- scope: `fc-lm-head`
- train rows: `4096`
- heldout rows: `2048`
- epochs: `2`
- lr: `1e-5`

Result:

- teacher-forced heldout exact: `36.43%`
- rollout heldout mean accepted: `0.4208984375`

Conclusion: adapting the aux projection matters.

### 3. FC + LM-head, full 72-prompt train split

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-fcheadadapt-fulltrain-20260706T195135Z
```

Training:

- scope: `fc-lm-head`
- train rows: `11448` from shards 0-2
- heldout rows: `3816` from shard 3
- epochs: `6`
- lr: `1e-5`

Result:

- teacher-forced train exact: `56.86%`
- teacher-forced heldout exact: `44.95%`
- heldout rollout starts: `3696`
- heldout rollout mean accepted: `0.5392316`
- rollout histogram: `0=2064`, `1=1321`, `2=265`, `3=42`, `4=4`, `5=0`
- step-1 exact: `44.16%`
- step-2 conditional exact: `19.06%`

Conclusion: target-matched adaptation is learning, but accepted depth remains
far below current MTP3 and far below the `tau >= 4.5` level needed to justify
the DFlash/Hipfire-style endpoint/kernel path.

### 4. All parameters, 4,096 train rows

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-alladapt-screen-20260706T195339Z
```

Training:

- scope: `all`
- train rows: `4096`
- heldout rows: `2048`
- epochs: `2`
- lr: `5e-6`

Result:

- teacher-forced heldout exact: `36.58%`
- rollout heldout mean accepted: `0.435546875`

Conclusion: full-body training on a small subset was slower and weaker than the
larger `fc-lm-head` run. The next scale-up should prioritize more target-owned
data and projection/head adaptation before spending on all-parameter training.

## Decision

Do not endpoint-test these adapted drafts yet.

Best adaptation so far (`fc-lm-head`, 72-prompt train split) improved heldout
rollout from `0.289` to `0.539`, which is a useful research signal but nowhere
near a record path. The DFlash/EAGLE3 route remains open only as a target-
matched training project, not as a direct Ex0bit import.

## Larger-corpus follow-up completed

The proposed scale-up was run immediately after the first screen.

Corpus:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v2-chat-4gpu-20260706T195742Z
```

- 4 B70 shards, one no-spec target replica per GPU.
- 384 prompts total, 96 prompts per shard.
- 61,440 generated rows total.
- Aux layers: `1,31,60`.
- All aux rows present; `continuity_breaks=0`.
- Train split: shards `0-2` (`288` prompts, `45,792` rows).
- Heldout split: shard `3` (`96` prompts, `15,264` rows).

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-fcheadadapt-v3full-20260706T200821Z
```

Training:

- scope: `fc-lm-head`;
- epochs: `6`;
- lr: `1e-5`;
- batch size: `64`;
- train covered rows: `44,510`;
- heldout covered rows: `15,052`.

Teacher-forced result:

- train exact: `58.80%`;
- heldout exact: `49.25%`;
- heldout loss: `2.345`.

Rollout result:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-fcheadadapt-v3full-20260706T200821Z/heldout-rollout-all-summary.json
```

- heldout starts: `14,784`;
- mean accepted: `0.6003787878787878`;
- histogram: `0=7591`, `1=5747`, `2=1227`, `3=202`, `4=16`, `5=1`;
- step-1 exact: `48.65%`;
- step-1 top-5: `75.57%`;
- step-2 conditional exact: `20.10%`;
- step-3 conditional exact: `15.15%`;
- family means: `architecture-tradeoff=0.559`, `long-context=0.613`,
  `support-escalation=0.629`.

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v3full-rollout-summary-20260706.json
```

## Updated decision

Still do **not** endpoint-test or kernel-optimize this adapted draft.

The larger corpus improved the line from direct Ex0bit (`0.289`) and the first
small adaptation (`0.539`) to `0.600` mean accepted, and the one-step
teacher-forced signal is now real (`~49%` heldout exact). But the rollout still
collapses after the first token: step-2 conditional exact is only `20.10%`.
That is far below current target-verified MTP3 depth and nowhere near the
`tau >= 4.5` region needed to justify Hipfire/DFlash-style endpoint work for
this model.

The next credible EAGLE/DFlash effort is **not** endpoint integration. It is a
new training objective: multi-step rollout / accepted-prefix training that
directly optimizes consecutive accepted tokens, plus a larger target-owned
corpus if needed. Without that, more endpoint plumbing would only create a slow
and low-acceptance speculative path.
