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

## All-scope draft training screen: tiny gain, still no endpoint

The next bounded test selectively reopened train scope by training the whole
one-layer Ex0bit draft (`--train-scope all`, embedding still frozen in the
trainer) instead of only `fc` + `lm_head`. It used the v4 corpus and heldout
split above, four B70s, four epochs, and low learning rates to avoid an
unbounded overfit run.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T212451Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-all-scope-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | init | scope | lr | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---|---|---:|---:|---:|---:|---:|
| `continue-all-r3-lr2e-6-decay1` | v4 best | all | `2e-6` | **`1.0707972582972582`** | `56.14%` | `52.77%` | `51.13%` |
| `continue-all-r3-lr1e-6-decay1` | v4 best | all | `1e-6` | `1.0630411255411256` | `56.03%` | `52.50%` | `50.74%` |
| `original-all-r3-lr2e-6-decay1` | original Ex0bit | all | `2e-6` | `0.3504689754689755` | `27.05%` | `24.85%` | `16.70%` |
| `original-all-r3-lr1e-6-decay1` | original Ex0bit | all | `1e-6` | `0.30104617604617606` | `24.48%` | `19.92%` | `14.06%` |

Interpretation:

- Continuing from the v4 best checkpoint and unfreezing the draft layer gives
  only a tiny improvement (`1.0593` -> `1.0708` mean accepted).
- Starting all-scope training from original Ex0bit with low LR underfits badly
  in four epochs.
- This closes simple all-scope unfreezing as an endpoint trigger. It may still
  be useful after a better objective, but by itself it does not move the lane
  toward the `1.5-2.0` minimum.
- Next credible move is objective-level: train for accepted-prefix survival or
  row selection more directly, rather than more low-LR full-scope sweeps.

## Late-step weighted rollout: current best diagnostic EAGLE result

The next objective-level screen kept the useful `fc-lm-head` train scope and
tested later-step loss upweighting at the working `2e-5` LR. This directly
targets the accepted-prefix survival problem without endpoint work.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T215224Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-late-weight-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | init | scope | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `continue-r3-lr2e-5-decay1p25` | v4 best | fc+lm | `2e-5` | `1.25` | **`1.0922619047619047`** | `56.50%` | `53.32%` | `53.17%` |
| `continue-r3-lr1e-5-decay1p25` | v4 best | fc+lm | `1e-5` | `1.25` | `1.0550595238095237` | `55.61%` | `52.36%` | `51.14%` |
| `original-r3-lr2e-5-decay1p25` | original Ex0bit | fc+lm | `2e-5` | `1.25` | `1.0400883838383839` | `54.68%` | `52.28%` | `51.70%` |
| `original-r3-lr2e-5-decay1p5` | original Ex0bit | fc+lm | `2e-5` | `1.5` | `1.0185786435786435` | `53.45%` | `52.01%` | `52.46%` |

Interpretation:

- This is the current best offline EAGLE/DFlash diagnostic checkpoint:
  `1.0923` mean accepted, up from v4 equal-step `1.0593` and all-scope
  `1.0708`.
- The gain is in later conditional steps, not just first-token exact
  (`step-3 conditional 53.17%`, the best seen so far in this lane).
- Still **not endpoint-worthy**. It remains below the `1.5-2.0` minimum and
  below current MTP3 accepted depth, so do not wire it into vLLM or submit any
  LocalMaxxing result from it.
- Next continuation candidate:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T215224Z/continue-r3-lr2e-5-decay1p25/checkpoint`.
  If continuing, keep testing objective variants around decay `1.25`; simple
  decay `1.5` from original traded first-token accuracy away and did not win.

## Late-continuation from the weighted checkpoint: still climbing slowly

Continued from the previous best late-weight checkpoint and tightened around
decay `1.1-1.5`.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T220622Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-late-continuation-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|---:|---:|
| `cont2-r3-lr2e-5-decay1p1` | `2e-5` | `1.1` | **`1.1073232323232323`** | `56.96%` | `53.75%` | `53.65%` |
| `cont2-r3-lr2e-5-decay1p25` | `2e-5` | `1.25` | `1.104301948051948` | `56.71%` | `53.79%` | `53.89%` |
| `cont2-r3-lr2e-5-decay1p5` | `2e-5` | `1.5` | `1.100604256854257` | `56.37%` | `53.70%` | `54.49%` |
| `cont2-r3-lr1e-5-decay1p25` | `1e-5` | `1.25` | `1.0928932178932178` | `56.51%` | `53.45%` | `53.14%` |

Interpretation:

- Current best diagnostic checkpoint is now
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T220622Z/cont2-r3-lr2e-5-decay1p1/checkpoint`.
- The lane is still improving, but only slowly: `1.0923` -> `1.1073`.
- Stronger late weighting improves later conditional exact but trades away
  some step-1 exact; mean accepted favored the lighter `1.1` weighting.
- This is still below endpoint threshold. Continue objective research only if
  chasing this lane further; do not submit or endpoint-integrate yet.

## Third late-continuation: current best, still below endpoint threshold

Continued from the previous best (`cont2-r3-lr2e-5-decay1p1`) and repeated the
focused decay/LR screen.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T221610Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-late-continuation2-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|---:|---:|
| `cont2-r3-lr2e-5-decay1p1` | `2e-5` | `1.1` | **`1.1205357142857142`** | `57.26%` | `54.11%` | `54.31%` |
| `cont2-r3-lr2e-5-decay1p25` | `2e-5` | `1.25` | `1.1167027417027418` | `57.03%` | `54.04%` | `54.51%` |
| `cont2-r3-lr2e-5-decay1p5` | `2e-5` | `1.5` | `1.1103896103896105` | `56.66%` | `53.96%` | `54.76%` |
| `cont2-r3-lr1e-5-decay1p25` | `1e-5` | `1.25` | `1.107593795093795` | `56.91%` | `53.75%` | `53.91%` |

Interpretation:

- Current best diagnostic checkpoint:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T221610Z/cont2-r3-lr2e-5-decay1p1/checkpoint`.
- The lane continues to climb slowly: `1.1073` -> `1.1205`.
- The lighter `1.1` late weighting remains best on mean accepted. Heavier
  weighting improves step-3 conditional exact but loses enough step-1/step-2
  mass to reduce the mean.
- Still below endpoint threshold and current MTP3 depth. Continue only as
  training research unless another objective/data change produces a much
  larger jump.

## Fourth late-continuation: smaller gain, plateau warning

Continued from the third-pass best checkpoint and repeated the same focused
screen once more.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T222601Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-late-continuation3-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|---:|---:|
| `cont2-r3-lr2e-5-decay1p1` | `2e-5` | `1.1` | **`1.1271645021645023`** | `57.47%` | `54.38%` | `54.32%` |
| `cont2-r3-lr2e-5-decay1p25` | `2e-5` | `1.25` | `1.1240530303030303` | `57.24%` | `54.31%` | `54.71%` |
| `cont2-r3-lr1e-5-decay1p25` | `1e-5` | `1.25` | `1.120806277056277` | `57.28%` | `54.08%` | `54.34%` |
| `cont2-r3-lr2e-5-decay1p5` | `2e-5` | `1.5` | `1.1207611832611832` | `57.03%` | `54.18%` | `55.06%` |

Interpretation:

- Current best diagnostic checkpoint:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T222601Z/cont2-r3-lr2e-5-decay1p1/checkpoint`.
- The continuation curve is flattening: `1.0923` -> `1.1073` -> `1.1205`
  -> `1.1272`. More identical continuation is unlikely to jump to the
  `1.5-2.0` endpoint threshold.
- If continuing this lane, change objective shape next: train rollout-5 from
  this checkpoint, enlarge data again, or add a more direct accepted-prefix /
  survival objective. Do not keep repeating the same rollout-3 continuation
  indefinitely.

## Rollout-5 continuation: deeper objective gives the largest recent jump

Continued from the rollout-3 plateau checkpoint and switched the training
objective to five autoregressive draft steps.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T223638Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-deep-continuation-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond | full-5 accepts |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cont-r5-lr2e-5-decay1` | `2e-5` | `1.0` | **`1.1766323953823954`** | `56.48%` | `53.54%` | `55.39%` | `1107` |
| `cont-r5-lr2e-5-decay1p1` | `2e-5` | `1.1` | `1.1691919191919191` | `56.08%` | `53.36%` | `55.48%` | `1128` |
| `cont-r5-lr2e-5-decay1p25` | `2e-5` | `1.25` | `1.1548520923520924` | `55.57%` | `53.01%` | `55.14%` | `1135` |
| `cont-r5-lr1e-5-decay1` | `1e-5` | `1.0` | `1.1343344155844155` | `56.70%` | `53.60%` | `54.86%` | `552` |

Interpretation:

- Current best diagnostic checkpoint:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T223638Z/cont-r5-lr2e-5-decay1/checkpoint`.
- This is the strongest recent move: `1.1272` -> `1.1766` mean accepted.
- The win comes from deeper full accepts, not step-1 exact. First-token exact
  is lower than the rollout-3 plateau, but the histogram has many more `5`
  accepts (`1107` vs `314` in the prior best).
- Still below endpoint threshold (`1.5-2.0` minimum), so do not endpoint-test
  or submit. But rollout-5 is now the preferred training objective for the next
  EAGLE/DFlash continuation.

## Second rollout-5 continuation: still improves accepted depth

Continued from the first rollout-5 best checkpoint and repeated the rollout-5
screen.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T224851Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-deep-continuation2-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond | full-5 accepts |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cont-r5-lr2e-5-decay1` | `2e-5` | `1.0` | **`1.189033189033189`** | `56.59%` | `53.61%` | `55.63%` | `1215` |
| `cont-r5-lr2e-5-decay1p1` | `2e-5` | `1.1` | `1.1798791486291487` | `56.20%` | `53.43%` | `55.56%` | `1216` |
| `cont-r5-lr1e-5-decay1` | `1e-5` | `1.0` | `1.1769029581529582` | `56.49%` | `53.48%` | `55.31%` | `1118` |
| `cont-r5-lr2e-5-decay1p25` | `2e-5` | `1.25` | `1.1690566378066378` | `55.72%` | `53.27%` | `55.44%` | `1224` |

Interpretation:

- Current best diagnostic checkpoint:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T224851Z/cont-r5-lr2e-5-decay1/checkpoint`.
- Rollout-5 is still improving mean accepted: `1.1766` -> `1.1890`.
- As before, mean accepted improves through more full-5 accepts while
  first-token exact stays below the rollout-3 plateau.
- Still below endpoint threshold. Continue rollout-5 training only while it
  keeps improving; otherwise the next real jump likely requires more data or a
  stronger architecture/objective.

## Third rollout-5 continuation: marginal improvement, diminishing returns

Continued again from the second rollout-5 best checkpoint.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T230122Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-deep-continuation3-v4-summary-20260706.json
```

Heldout shard `3`, all `22,176` starts:

| variant | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond | full-5 accepts |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cont-r5-lr2e-5-decay1` | `2e-5` | `1.0` | **`1.1957070707070707`** | `56.68%` | `53.61%` | `55.79%` | `1267` |
| `cont-r5-lr1e-5-decay1` | `1e-5` | `1.0` | `1.1899350649350648` | `56.66%` | `53.59%` | `55.51%` | `1216` |
| `cont-r5-lr2e-5-decay1p1` | `2e-5` | `1.1` | `1.187905844155844` | `56.37%` | `53.46%` | `55.71%` | `1270` |
| `cont-r5-lr2e-5-decay1p25` | `2e-5` | `1.25` | `1.1775793650793651` | `55.92%` | `53.42%` | `55.47%` | `1266` |

Interpretation:

- Current best diagnostic checkpoint:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T230122Z/cont-r5-lr2e-5-decay1/checkpoint`.
- The rollout-5 curve is now clearly diminishing: `1.1766` -> `1.1890`
  -> `1.1957`.
- Repeating rollout-5 can still add a little accepted depth, but it is unlikely
  to reach the `1.5-2.0` threshold by itself. The next larger move should be
  more/broader target-owned data, a more explicit survival objective, or a
  stronger drafter architecture.

## V5 target-owned corpus collected

Generated `eagle-chat-corpus-v5-suite.json` by expanding the non-final
training suite to `16` domains, `12` tasks, and `6` variants per pair
(`1152` prompts). Collected aux-hidden data across all four B70s with the same
aux layers `1,31,60`.

Corpus root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v2-chat-4gpu-20260706T231458Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-aux-v5-corpus-summary-20260706.json
```

Collection result:

- `1152` prompts, `184,320` usable rows;
- all `184,320` aux rows saved;
- `0` continuity breaks, `0` aux bad files;
- shard families:
  - shard 0: database-operations, incident-response, performance-debug, security-review;
  - shard 1: api-design, capacity-planning, code-review, quality-gates;
  - shard 2: architecture-tradeoff, long-context, release-planning, support-escalation;
  - shard 3: cost-optimization, data-pipeline, edge-deployment, incident-postmortem.

Next training run should use shard 0-2 for training and shard 3 as a heldout
domain split, starting from the current best rollout-5 checkpoint.

## V5 rollout-5 training: larger data is a real unlock

Before training on v5, evaluated the previous v4-trained best checkpoint on
the v5 heldout shard (`cost-optimization`, `data-pipeline`, `edge-deployment`,
`incident-postmortem`):

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v5-heldout-baseline-20260706T234418Z
```

Repo baseline summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v5-heldout-baseline-summary-20260706.json
```

Baseline on v5 heldout: `1.2001713564213565` mean accepted over `44,352`
starts (`56.92%` step-1 exact, `53.19%` step-2 conditional, `55.56%`
step-3 conditional, `2647` full-5 accepts).

Then trained on v5 shards 0-2 and evaluated on shard 3:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T234959Z
```

Repo training summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v5-deep-continuation-summary-20260707.json
```

Heldout shard `3`, all `44,352` starts:

| variant | lr | decay | mean accepted | step-1 exact | step-2 cond | step-3 cond | full-5 accepts |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cont-r5-lr2e-5-decay1` | `2e-5` | `1.0` | **`1.2866838023088023`** | `59.02%` | `55.32%` | `57.29%` | `3056` |
| `cont-r5-lr2e-5-decay1p1` | `2e-5` | `1.1` | `1.2760416666666667` | `58.58%` | `55.01%` | `57.46%` | `3075` |
| `cont-r5-lr2e-5-decay1p25` | `2e-5` | `1.25` | `1.2556592712842713` | `57.84%` | `54.52%` | `57.34%` | `3074` |
| `cont-r5-lr1e-5-decay1` | `1e-5` | `1.0` | `1.2259424603174602` | `57.81%` | `53.50%` | `56.13%` | `2724` |

Interpretation:

- Current best diagnostic checkpoint:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T234959Z/cont-r5-lr2e-5-decay1/checkpoint`.
- V5 data produced the largest recent jump: v5 heldout baseline `1.2002`
  -> trained `1.2867`; previous v4 heldout best was `1.1957`.
- This confirms the EAGLE/DFlash lane was meaningfully data-limited, not only
  objective-limited.
- Still below the `1.5-2.0` endpoint threshold. Continue with v5 rollout-5
  training and/or build v6 data; do not endpoint-integrate or submit yet.

## V5 continuation rerun: disk-full interruption, then narrow retry

Attempted one more v5 rollout-5 continuation from the `1.2867` checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260707T001320Z
```

Repo partial-run summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v5-deep-continuation-partial-diskfull-summary-20260707.json
```

Outcome:

- `cont-r5-lr1e-5-decay1` completed and reached `1.287608225108225`
  mean accepted over `44,352` starts (`59.04%` step-1 exact, `55.28%`
  step-2 conditional, `57.42%` step-3 conditional, histogram
  `0=18166,1=11711,2=6164,3=3233,4=2020,5=3058`).
- The three `lr=2e-5` variants trained to completion but failed while
  serializing `model.safetensors` with `No space left on device`; their
  partial corrupt checkpoint files were removed and the logs were preserved.
- This is **not** a promotable result and not a headline throughput result.
  It is a diagnostic continuation screen plus an operational failure record.

Operational fix:

- Root was full because `/mnt/fast-ai` is on the root filesystem.
- Cleared transient `/tmp/icpx-*`, `/tmp/torchinductor_steve`, and
  `/tmp/vllm-xpu-*` build scratch.
- Offloaded the old vLLM graph/cache experiment tree from
  `/mnt/fast-ai/vllm-cache-exp` to:

```text
/mnt/usb-models/offloaded/llm-optimizations/vllm-cache-exp-20260707
```

  The USB archive is about `91G`; the local cache directory is intentionally
  left as an empty/regenerable directory for future runs.

Harness hardening:

- `scripts/train-qwen27-ex0bit-eagle3-adapter.py` now writes
  `model.safetensors` atomically via a temporary file and `os.replace`, so
  future failed exports do not leave plausible-looking broken checkpoints.
- `run-ex0bit-eagle3-rollout-train-v3-4gpu.sh` now supports
  `ONLY_LABELS=...` to rerun selected variants without repeating a full
  four-variant sweep.

Immediate retry:

```bash
CORPUS=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v2-chat-4gpu-20260706T231458Z \
CONTINUE_DRAFT=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260706T234959Z/cont-r5-lr2e-5-decay1/checkpoint \
SWEEP=deep-continuation ONLY_LABELS=cont-r5-lr2e-5-decay1 \
EPOCHS=6 BATCH_SIZE=64 EVAL_EVERY=1000 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-ex0bit-eagle3-rollout-train-v3-4gpu.sh
```

The retry run root is expected to be:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260707T004308Z
```

Retry result:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v5-continuation4-summary-20260707.json
```

- `cont-r5-lr2e-5-decay1` completed after the disk cleanup and atomic export
  patch;
- mean accepted improved to **`1.3147772366522366`** over `44,352` starts;
- step-1 exact `59.54%`, step-2 conditional `55.91%`, step-3 conditional
  `58.01%`;
- histogram: `0=17946, 1=11642, 2=6199, 3=3252, 4=2048, 5=3265`;
- checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260707T004308Z/cont-r5-lr2e-5-decay1/checkpoint
```

The wrapper process exited nonzero only because the shell script was edited
while that already-running instance later reached the summary block. The
training, atomic export, heldout evaluator, and `summary.json` all completed.
This is still diagnostic-only and below the `1.5-2.0` endpoint trigger, but it
is the new best offline EAGLE/DFlash checkpoint for the next survival-objective
screen.

## Next objective patch: accepted-prefix survival gating

The next code-level objective change targets an objective/evaluator mismatch:
the trainer previously optimized CE for every rollout step even after an
earlier step would have failed, while the offline accepted-prefix evaluator
stops at the first mismatch. That spends gradient on dead prefixes that cannot
increase accepted depth.

Implemented in `scripts/train-qwen27-ex0bit-eagle3-adapter.py`:

- `--rollout-survival-mode=hard`: primary CE is computed only for prefixes
  still alive under greedy accepted-prefix semantics;
- `--rollout-dead-loss-floor`: optional small CE weight for dead prefixes to
  avoid starving late-step calibration entirely;
- `--rollout-rank-loss-weight` and `--rollout-rank-margin`: optional live
  argmax-margin loss that pushes the target logit above the strongest
  non-target logit. This targets the observed top-5/top-1 gap.

Implemented in
`experiments/qwen36-27b-autoround-int4-b70/scripts/run-ex0bit-eagle3-rollout-train-v3-4gpu.sh`:

- `SWEEP=survival-objective` with four 4-GPU variants:
  - hard survival, no floor;
  - hard survival with `0.05` dead-prefix floor;
  - hard survival plus `0.05` rank loss;
  - hard survival plus `0.1` rank loss;
- `ONLY_LABELS=...` can narrow reruns to a single variant.

Validation rule: this is still offline diagnostic work only. Do not endpoint
integrate or submit anything unless a locked heldout run reaches at least the
`1.5-2.0` mean-accepted trigger and does not regress on the current v5
heldout. The current endpoint headline remains the strict fresh
`68.236 tok/s` ReplaySSM result, not any offline EAGLE score.

Survival-objective result:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260707T010510Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v5-survival-objective-summary-20260707.json
```

Heldout shard `3`, all `44,352` starts:

| variant | survival | floor | rank weight | mean accepted | step-1 exact | step-2 cond | step-3 cond | full-5 accepts |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `surv-r5-lr2e-5-hard-rank0p1` | hard | `0.05` | `0.1` | **`1.340886544011544`** | `59.92%` | `56.26%` | `58.50%` | `3602` |
| `surv-r5-lr2e-5-hard-rank0p05` | hard | `0.05` | `0.05` | `1.3400297619047619` | `59.87%` | `56.29%` | `58.48%` | `3604` |
| `surv-r5-lr2e-5-hard-floor0` | hard | `0.0` | `0.0` | `1.3386093073593073` | `59.84%` | `56.20%` | `58.53%` | `3590` |
| `surv-r5-lr2e-5-hard-floor0p05` | hard | `0.05` | `0.0` | `1.3386093073593073` | `59.83%` | `56.26%` | `58.50%` | `3589` |

Interpretation:

- accepted-prefix survival gating is a real positive signal:
  `1.3147772366522366` -> `1.340886544011544`;
- rank loss helps slightly, but only by about `0.0023` mean accepted versus
  hard survival without rank, so it is not a standalone unlock;
- still below the `1.5-2.0` endpoint threshold. Do not wire this into vLLM or
  submit anything. The best checkpoint is:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-20260707T010510Z/surv-r5-lr2e-5-hard-rank0p1/checkpoint
```

Next higher-upside move: collect and train on the broader v6 chat-style corpus,
starting from the survival-objective best checkpoint. Repeating more v5
continuation may add small gains, but the curve is still too far from the
endpoint trigger.

## V6 data preset prepared while survival sweep runs

Added a `chat-v6` preset to
`experiments/qwen36-27b-autoround-int4-b70/scripts/make-eagle-chat-corpus-suite.py`
and generated:

```text
experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v6-suite.json
```

Purpose: if the survival-objective sweep does not clear the offline threshold,
the next higher-upside lever is broader target-owned data rather than more
same-distribution v5 continuation. V5 was mostly ops/business/infra prompts;
v6 adds broader fresh chat-style coverage: code debugging, SQL/data analysis,
config/devops, API integration, product support, personal planning, document
editing, quantitative planning, compliance/security advice, general technical
QA, dependency upgrades, testing strategy, observability/log diagnosis, shell
automation, migration support, and customer debugging.

Validation of the generated suite:

- `1152` prompts;
- `16` families x `12` tasks x `6` variants;
- `288` prompts per shard;
- shard split keeps whole families together, avoiding row-level leakage:
  - shard 0: `api-client-integration`, `code-debugging`, `config-devops`,
    `sql-data-analysis`;
  - shard 1: `document-editing`, `personal-productivity`,
    `product-support`, `quantitative-planning`;
  - shard 2: `compliance-security-advice`, `dependency-upgrade`,
    `general-technical-qa`, `testing-strategy`;
  - shard 3 heldout/audit-style: `customer-debugging`, `migration-support`,
    `observability-logs`, `shell-automation`.

Suggested collection command after GPUs are free:

```bash
SUITE=experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v6-suite.json \
SHARD_PROMPTS=288 OUTPUT_TOKENS=160 EAGLE3_AUX_LAYERS=1,31,60 \
RUN_ROOT=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-$(date -u +%Y%m%dT%H%M%SZ) \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle3-aux-corpus-v2-4gpu.sh
```

QC gate before training: require all shards to finish, zero continuity breaks,
zero aux bad files, and all available aux rows saved. The theoretical max is
`1152 * 160 = 184320` rows, but some prompts can terminate early and should be
recorded honestly rather than padded. This remains diagnostic draft-training
data only; do not use it as a promotion benchmark or LocalMaxxing throughput
claim.

## V6 corpus collected

Collected with the command above:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z
```

Repo compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-aux-v6-corpus-summary-20260707.json
```

QC outcome:

- `total_prompts=1152` attempted across four one-B70 replicas;
- `total_rows=179650` usable aux rows, `total_aux_rows_saved=179650`;
- `total_continuity_breaks=0`;
- `total_aux_bad_files=0`;
- `total_samples=1151`, not `1152`, because shard 1 prompt
  `quantitative-planning-summarize-context-terse` produced only five tokens
  (`No context provided.`) and yielded no useful sample tensor;
- shard 3 remains the heldout/audit split:
  `customer-debugging`, `migration-support`, `observability-logs`,
  `shell-automation`.

This is good enough for the next diagnostic training step: evaluate the current
v5-survival best checkpoint on the v6 heldout shard, then train from that
checkpoint on v6 shards 0-2 and evaluate on shard 3. Do not promote any offline
accepted-depth result as endpoint throughput.

## V5-survival checkpoint on V6 heldout

Baseline evaluation of the best v5 survival checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6-heldout-baseline-20260707T020043Z/surv-best-on-v6-heldout-summary.json
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v5-survival-on-v6-heldout-summary-20260707.json
```

Result on v6 shard 3 (`42342` starts, all `288` heldout samples):

- mean accepted: **`0.8866846157479571`**;
- histogram: `0=20970`, `1=12142`, `2=5239`, `3=2064`, `4=903`, `5=1024`;
- family means: customer-debugging `0.8665`, migration-support `0.9167`,
  observability-logs `0.9324`, shell-automation `0.8367`;
- `valid_headline_throughput=false`.

Interpretation: the v5 survival checkpoint does not generalize to the broader
v6 heldout distribution. This is a useful baseline, not a regression in the
endpoint recipe. The next training run should start from the v5-survival best,
train on v6 shards 0-2, and try to beat `0.8867` on shard 3; only if offline
mean accepted approaches at least `1.5-2.0` should endpoint/kernel integration
restart.

## V6 survival-objective training sweep

Training run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6-survival-train-20260707T020651Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v6-survival-train-summary-20260707.json
```

Setup:

- initialized every variant from the v5 survival best checkpoint
  `surv-r5-lr2e-5-hard-rank0p1`;
- trained on v6 shards 0-2;
- evaluated on v6 shard 3 (`42342` starts);
- `rollout_steps=5`, `lr=2e-5`, `epochs=6`, `batch_size=64`;
- four-GPU sweep over hard survival floor/rank-loss variants.

Results:

| variant | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|
| `surv-r5-lr2e-5-hard-rank0p1` | **`1.0069670776061594`** | `53.78%` | `47.28%` | `47.27%` |
| `surv-r5-lr2e-5-hard-floor0` | `1.0061168579660857` | `53.78%` | `47.21%` | `47.32%` |
| `surv-r5-lr2e-5-hard-rank0p05` | `1.0061168579660857` | `53.73%` | `47.27%` | `47.34%` |
| `surv-r5-lr2e-5-hard-floor0p05` | `1.005172169477115` | `53.70%` | `47.32%` | `47.21%` |

Interpretation:

- v6 training improved heldout mean accepted from `0.8866846157479571` to
  `1.0069670776061594`, so broader target-owned data helps;
- the gain is real but still far below the `1.5-2.0` threshold needed before
  endpoint/kernel integration makes sense;
- rank loss is slightly positive again but tiny (`+0.00085` over `floor0`);
- the limiting factor is still step-1 exact and multi-step survival, not
  endpoint wiring.

Next credible offline moves:

1. continue from the v6 best checkpoint with a smaller LR (`5e-6` / `1e-5`)
   and/or longer run to test whether this is still climbing or plateauing;
2. try a stronger objective focused directly on step-1 exact plus survivor
   carry (`rollout_steps=3`, higher first-step weight) because current step-1
   exact is only `~53.8%`;
3. fix the v6 data prompt families that often answer "no context provided" by
   embedding concrete snippets/tables/logs, then recollect a smaller v6b
   corpus if data quality looks like the bottleneck.

Do not submit these results to LocalMaxxing and do not describe them as
throughput. They are offline acceptance diagnostics only.

## V6 continuation / first-step-emphasis sweep

Training run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6-continuation-20260707T023130Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v6-continuation-summary-20260707.json
```

Setup: initialized from the prior v6 best checkpoint
`surv-r5-lr2e-5-hard-rank0p1`, trained on v6 shards 0-2, evaluated on shard 3,
and screened lower LR plus `rollout_loss_decay < 1` variants. This sweep used
the tracked wrapper case `SWEEP=v6-continuation`.

Results:

| variant | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|
| `v6cont-r5-lr1e-5-decay0p5-rank0p1` | **`1.0401492607812575`** | `55.14%` | `48.21%` | `47.24%` |
| `v6cont-r5-lr1e-5-decay0p75-rank0p1` | `1.0270889424212366` | `54.46%` | `48.00%` | `47.53%` |
| `v6cont-r5-lr1e-5-decay1-rank0p1` | `1.0134618109678333` | `53.93%` | `47.55%` | `47.56%` |
| `v6cont-r5-lr5e-6-decay1-rank0p1` | `1.0072268669406264` | `53.79%` | `47.31%` | `47.35%` |

Interpretation:

- first-step emphasis is the useful lever: `decay=0.5` moved v6 heldout mean
  accepted `1.0069670776061594 -> 1.0401492607812575`;
- simply lowering LR with equal step weight is flat (`1.0072-1.0135`);
- step-1 exact improved to `55.14%`, but downstream conditional exact remains
  around `47-48%`, so this is not close to endpoint threshold yet;
- still offline-only, `valid_headline_throughput=false`.

Next credible offline move: continue from `v6cont-r5-lr1e-5-decay0p5-rank0p1`
and screen stronger first-step emphasis / shorter rollout objectives
(`decay=0.25`, `rollout_steps=3`) against one equal-weight control. If the mean
accepted curve stays below roughly `1.1`, switch to data quality (v6b concrete
snippet/log/table prompts) or a wider train scope rather than endpoint work.

## V6 step-focus sweep

Training run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6-stepfocus-20260707T025529Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v6-stepfocus-summary-20260707.json
```

Setup: initialized from the v6 continuation best checkpoint
`v6cont-r5-lr1e-5-decay0p5-rank0p1`, trained on v6 shards 0-2, evaluated on
v6 heldout shard 3 (`42342` starts), and screened shorter rollout / stronger
first-token emphasis variants with the tracked wrapper case
`SWEEP=v6-stepfocus`.

Results:

| variant | rollout steps | decay | lr | mean accepted | step-1 exact | step-2 cond | step-3 cond |
|---|---:|---:|---:|---:|---:|---:|---:|
| `v6sf-r3-lr1e-5-decay0p25-rank0p1` | 3 | 0.25 | `1e-5` | **`1.0493835907609466`** | `55.80%` | `48.29%` | `46.94%` |
| `v6sf-r3-lr1e-5-decay0p5-rank0p1` | 3 | 0.50 | `1e-5` | `1.0482027301497332` | `55.56%` | `48.40%` | `47.40%` |
| `v6sf-r5-lr1e-5-decay0p25-rank0p1` | 5 | 0.25 | `1e-5` | `1.047588682631902` | `55.73%` | `48.27%` | `46.85%` |
| `v6sf-r5-lr5e-6-decay0p5-rank0p1` | 5 | 0.50 | `5e-6` | `1.0402437296301545` | `55.13%` | `48.22%` | `47.29%` |

Interpretation:

- shorter rollout / stronger first-token weighting gives only a small lift over
  the previous v6 continuation best (`1.0401492607812575 -> 1.0493835907609466`);
- the probe exact rate improved during training (`~56.7%`), but full rollout
  survival did not move enough: conditional step-2 remains around `48%` and
  conditional step-3 around `47%`;
- this closes another same-corpus training sweep as diagnostic-only. It is
  useful evidence that the v6 lane is learning, but not an endpoint trigger and
  not a LocalMaxxing result.

Next move: stop spending full 4-GPU sweeps on this exact v6 corpus/objective
family unless there is a new mechanism. The higher-value follow-up is v6b data
quality: rebuild a smaller target-owned corpus with concrete snippets, tables,
logs, and code fragments embedded directly in prompts so the model cannot
answer "No context provided", then evaluate whether better data lifts step-1
and multi-step survival. If data quality does not move mean accepted toward
`1.5-2.0`, return to verifier/LM-head or graph-safe state-transaction work.

## V6b concrete-context corpus

The v6b follow-up keeps the broader chat-style direction but fixes the observed
v6 data-quality issue where some prompts requested pasted context without
including enough concrete material. The generator now has a tracked
`chat-v6b` preset in
`experiments/qwen36-27b-autoround-int4-b70/scripts/make-eagle-chat-corpus-suite.py`,
and the generated suite is:

```text
experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v6b-suite.json
```

Suite shape:

- `384` prompts total;
- `12` concrete-context families;
- `8` task types;
- `4` variants per domain/task pair;
- every prompt includes an explicit `Context:` block with logs, SQL tables,
  YAML/systemd config, stack traces, benchmark tables, customer tickets,
  code snippets, capacity sheets, API/webhook payloads, release notes, or test
  failure artifacts.

Collection run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z
```

Repo summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-aux-v6b-corpus-summary-20260707.json
```

Collection result:

- total prompts: `384`;
- usable rows: `61268`;
- samples saved / with metadata: `384 / 384`;
- aux rows available/saved: `61268 / 61268`;
- aux layers: `1,31,60`;
- continuity breaks: `0`;
- aux bad files: `0`;
- shard family split:
  - shard 0: `incident-log-triage`, `sql-analytics-table`, `yaml-systemd-config`;
  - shard 1: `benchmark-variance-table`, `customer-ticket-debug`, `python-stacktrace`;
  - shard 2: `capacity-sheet`, `code-review-worker`, `security-audit-snippet`;
  - shard 3: `api-payload-webhook`, `release-note-draft`, `test-failure-report`.

Heldout baseline on v6b shard 3:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v6sf-best-on-v6b-heldout-summary-20260707.json
```

The best v6 step-focus checkpoint
`v6sf-r3-lr1e-5-decay0p25-rank0p1` scored `1.036561331974176` mean accepted
on v6b shard 3 (`14715` starts):

| family | mean accepted |
|---|---:|
| `api-payload-webhook` | `1.0996347402597402` |
| `release-note-draft` | `1.0080263428689031` |
| `test-failure-report` | `1.0016233766233766` |

Per-step exact:

- step 1: `56.05%`;
- step 2 conditional: `47.84%`;
- step 3 conditional: `43.74%`;
- step 4 conditional: `49.83%`;
- step 5 conditional: `55.00%`.

Interpretation: v6b is clean but not easier out of the box. A bounded v6b
training screen is worth running because the data no longer has the v6
"missing context" defect, but the bar for endpoint work is unchanged:
offline mean accepted needs to approach at least `1.5-2.0`.
