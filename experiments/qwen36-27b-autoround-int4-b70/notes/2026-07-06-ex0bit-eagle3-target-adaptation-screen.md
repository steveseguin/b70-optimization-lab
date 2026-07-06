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

## Next action

Collect a larger EAGLE3 aux corpus with the same no-spec target-owned method
and train `fc-lm-head` first:

1. use all 4 B70s;
2. keep a strict heldout split by prompt family/shard;
3. evaluate rollout before endpoint work;
4. stop if heldout accepted depth does not move toward at least `1.5-2.0`;
5. only consider endpoint integration if offline acceptance approaches or beats
   current MTP3 accepted depth.
