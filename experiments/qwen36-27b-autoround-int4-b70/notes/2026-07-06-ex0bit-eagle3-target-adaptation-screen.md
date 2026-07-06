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

## Multi-step rollout objective screen

Implemented `--rollout-steps` in:

```text
scripts/train-qwen27-ex0bit-eagle3-adapter.py
```

This keeps the original row-wise teacher-forced objective when
`--rollout-steps=1`, but for `>1` it starts from target aux hidden state at
step 1, then feeds the draft's own predicted hidden states plus teacher token
IDs for later steps. This directly targets the observed failure mode: good-ish
step-1 exact with poor consecutive acceptance.

Reusable four-GPU runner:

```text
experiments/qwen36-27b-autoround-int4-b70/scripts/run-ex0bit-eagle3-rollout-train-v3-4gpu.sh
```

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T202134Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706.json
```

Screened four variants on the same heldout shard (`14,784` starts):

| variant | init | rollout | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|---:|---:|
| `original-r3-lr1e-5-decay1` | Ex0bit original | 3 | `0.6693046536796536` | `43.19%` | `38.09%` | `33.31%` |
| `v3full-r3-lr3e-6-decay1` | v3 one-step adapted | 3 | `0.6228354978354979` | `48.02%` | `24.61%` | `17.80%` |
| `v3full-r3-lr3e-6-decay1p5` | v3 one-step adapted | 3 | `0.6227002164502164` | `47.97%` | `24.62%` | `18.16%` |
| `v3full-r5-lr2e-6-decay1` | v3 one-step adapted | 5 | `0.6141774891774892` | `48.55%` | `22.16%` | `16.97%` |

Interpretation:

- The rollout objective is mechanically correct and improves consecutive-token
  behavior when trained from original Ex0bit (`0.600` -> `0.669` mean accepted,
  with much stronger step-2/step-3 conditional exact).
- Starting from the one-step-adapted checkpoint preserves better first-token
  exact but does not improve rollout depth; it appears biased toward step-1 CE
  rather than stable recurrence.
- Even the best `0.669` remains far below current MTP3 accepted depth, so it is
  still **not endpoint-worthy** and not a LocalMaxxing/result candidate.

Next screen, if continuing this lane: train from original Ex0bit with rollout
objective only, sweeping LR/epochs/late-step weighting, because that was the
only variant that improved conditional step-2/step-3 behavior. Do not spend
endpoint/kernel work until mean accepted moves into the `1.5-2.0` range at
minimum, and ideally approaches current MTP3 depth.

## Original-init rollout sweep: lane is reopened, not endpoint-ready

The recommended follow-up was run with `SWEEP=original-rollout EPOCHS=10`.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T203023Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-rollouttrain-original-sweep-20260706.json
```

Heldout shard `3`, all `14,784` starts:

| variant | rollout | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|---:|---:|---:|
| `original-r3-lr2e-5-decay1` | 3 | `2e-5` | `1.0` | **`0.973146645021645`** | `52.81%` | `50.04%` | `49.40%` |
| `original-r3-lr1e-5-decay1p5` | 3 | `1e-5` | `1.5` | `0.6321699134199135` | `40.49%` | `38.01%` | `35.82%` |
| `original-r5-lr1e-5-decay1` | 5 | `1e-5` | `1.0` | `0.6291937229437229` | `40.79%` | `36.07%` | `33.66%` |
| `original-r3-lr5e-6-decay1` | 3 | `5e-6` | `1.0` | `0.4318858225108225` | `32.37%` | `27.18%` | `19.52%` |

Interpretation:

- This is the first Ex0bit EAGLE3/DFlash adaptation result that materially
  trains consecutive acceptance. Step-2/step-3 conditional exact near `50%`
  means the earlier "rollout collapses after token 1" failure is no longer
  absolute.
- It is still diagnostic only. `0.973` accepted draft tokens/start is below the
  rough endpoint threshold (`1.5-2.0` minimum) and below current MTP3 accepted
  depth, so do not spend endpoint/kernel integration yet.
- The useful recipe is specific: original Ex0bit init, rollout-3 objective,
  `lr=2e-5`, equal step weights, 10 epochs. Lower LR underfits; late-step
  weighting at `1e-5` underfits; rollout-5 at `1e-5` underfits.

Next screen: narrow around `lr=2e-5` and continuation training from this best
checkpoint. Stop endpoint work until offline accepted depth moves materially
past `1.0` and approaches `1.5-2.0`.

## Continuation rollout sweep: small gain, likely data/objective bottleneck

Ran continuation from the best checkpoint above using
`SWEEP=continuation-rollout EPOCHS=6`.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T204204Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-rollouttrain-continuation-sweep-20260706.json
```

Heldout shard `3`, all `14,784` starts:

| variant | rollout | lr | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|---:|---:|
| `cont-r3-lr2e-5-decay1` | 3 | `2e-5` | **`1.0142045454545454`** | `54.06%` | `50.89%` | `51.07%` |
| `cont-r3-lr1e-5-decay1` | 3 | `1e-5` | `0.9760551948051948` | `52.88%` | `50.13%` | `49.63%` |
| `cont-r3-lr5e-6-decay1` | 3 | `5e-6` | `0.9749729437229437` | `52.85%` | `50.19%` | `49.45%` |
| `cont-r5-lr5e-6-decay1` | 5 | `5e-6` | `0.9683441558441559` | `52.29%` | `49.62%` | `49.71%` |

Interpretation:

- Continuation training does improve the best `0.973` result to `1.014`, but
  the improvement is small.
- The best continuation has train exact `83.38%` vs heldout exact `54.68%`,
  indicating the current `288`-prompt training split is becoming overfit.
- Endpoint integration is still premature. The draft remains below the
  `1.5-2.0` minimum offline threshold and below current MTP3 accepted depth.

Next credible move is a larger/more diverse target-owned corpus and/or a loss
that rewards accepted-prefix survival more directly. More continuation epochs
on this same split are unlikely to be the main unlock.

## V4 larger corpus rollout sweep: modest improvement, still below endpoint threshold

The next screen expanded the target-owned corpus from `384` prompts / `61,440`
rows to `576` prompts / `92,160` rows, using the same aux-layer dump path
(`VLLM_XPU_EAGLE_DATA_DUMP_AUX_LAYERS=1,31,60`). The corpus is broader and
balanced across `12` families, with `0` continuity breaks and all aux rows
present.

Corpus root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v2-chat-4gpu-20260706T205107Z-v4
```

Training/eval root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T210606Z
```

Repo summaries:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-aux-v4-corpus-summary-20260706.json
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-rollouttrain-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | rollout | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|---:|---:|---:|
| `original-r3-lr2e-5-decay1` | 3 | `2e-5` | `1.0` | **`1.0592532467532467`** | `55.98%` | `52.39%` | `50.55%` |
| `original-r3-lr1e-5-decay1p5` | 3 | `1e-5` | `1.5` | `0.6679743867243867` | `41.93%` | `39.24%` | `37.71%` |
| `original-r5-lr1e-5-decay1` | 5 | `1e-5` | `1.0` | `0.6601731601731602` | `42.04%` | `36.99%` | `35.11%` |
| `original-r3-lr5e-6-decay1` | 3 | `5e-6` | `1.0` | `0.4390782828282828` | `32.86%` | `27.58%` | `18.76%` |

Interpretation:

- Larger/more diverse data helped, but only modestly: best heldout mean
  accepted moved from `1.014` to `1.059`.
- The best recipe remains stable: original Ex0bit init, rollout-3,
  `lr=2e-5`, equal step weights. Lower LR, rollout-5 at `1e-5`, and simple
  late-step weighting remain underfit.
- This is **not endpoint-worthy**. The drafter is still below the `1.5-2.0`
  minimum offline threshold and far below the accepted depth needed for a
  realistic `>100 tok/s` endpoint.
- The next useful attempt should change the objective or train more of the
  draft, not merely add a few more epochs. Candidate directions:
  survival-weighted rollout loss at the working `2e-5` LR, a larger v5 corpus
  with more output styles, or selectively unfreezing the draft layer once the
  fc/lm-head plateau is confirmed.
