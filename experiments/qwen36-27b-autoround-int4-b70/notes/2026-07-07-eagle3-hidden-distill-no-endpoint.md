# 2026-07-07: EAGLE3 hidden-state distillation no-endpoint screen

## Classification

Diagnostic only. No endpoint throughput claim, no quality claim, and no
LocalMaxxing submission.

## Objective

The best v6b all-scope EAGLE3 draft was still only
`1.1014610941216445` heldout mean accepted. This screen tested whether adding
target-hidden trajectory distillation to the rollout objective could make the
draft's internal hidden trajectory more target-like and improve accepted depth.

The key question was not "does training loss move"; it was whether heldout
mean accepted moves enough to justify endpoint work. The practical threshold is
still `1.5-2.0` accepted draft tokens before spending vLLM/XPU endpoint and
kernel time on a new external-draft path.

## Tooling change

`scripts/train-qwen27-ex0bit-eagle3-adapter.py` now supports optional hidden
distillation:

```text
--hidden-loss-weight FLOAT
--hidden-loss-type cosine|mse
```

When `--hidden-loss-weight > 0`, the trainer requires `hidden_state` in the
`qwen36_eagle_sequence_v2` samples and appends the next target hidden row to
row/window datasets. During rollout training it adds a cosine or MSE loss
between the predicted draft hidden row and the corresponding next target
`hidden_state` row, in addition to token CE / survival / rank losses.

The exported checkpoint format is unchanged.

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/qwen27-eagle3-hidden-distill-training-experiment-20260707.patch
```

## Run identity

Raw root:

```text
/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-hidden-distill-v6b-20260707T091438Z
```

Dataset:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z
```

Start checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-allscope-20260707T075425Z/all-r5-lr3e-6-decay0p25/checkpoint
```

Target model:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e
```

Compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-hidden-distill-screen-20260707.json
```

Common settings:

- four B70 replicas in parallel, one variant per GPU;
- training shards `0,1,2`, heldout shard `3`;
- `rollout_steps=5`, hard survival objective, `dead_loss_floor=0.05`,
  `rank_loss_weight=0.10`;
- dtype `bfloat16`;
- final evaluator: full heldout shard, `max_steps=5`, `topk=5`,
  `max_starts=0`.

## Results

Baseline reference: v6b all-scope best `1.1014610941216445` mean accepted.

| label | scope | lr | hidden weight | decay | mean accepted | delta vs baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `hdist-all-r5-lr1e-6-w0p02-decay0p5` | all | `1e-6` | `0.02` | `0.5` | `1.1023445463812436` | `+0.0008834522595991096` |
| `hdist-fc-r5-lr3e-6-w0p02-decay1` | fc-lm-head | `3e-6` | `0.02` | `1.0` | `1.1015290519877676` | `+0.00006795786612316267` |
| `hdist-fc-r5-lr3e-6-w0p05-decay1` | fc-lm-head | `3e-6` | `0.05` | `1.0` | `1.1014610941216445` | `0.0` |
| `hdist-all-r5-lr1e-6-w0p05-decay0p5` | all | `1e-6` | `0.05` | `0.5` | `1.1011892626571527` | `-0.00027183146449177055` |

Best histogram:

```text
0=6174, 1=4285, 2=2317, 3=970, 4=453, 5=516
```

## Decision

Close hidden-state distillation as a no-endpoint lane for this EAGLE3 draft.
The mechanism is implemented and reusable, but the measured lift is effectively
zero and far below the endpoint threshold. Do not spend strict endpoint runs,
LocalMaxxing submissions, or vLLM integration work on these checkpoints.

This also reinforces the broader conclusion from the recent EAGLE screens:
small objective changes on the current Ex0bit-derived one-layer draft are not
enough. Future drafter work needs a materially stronger architecture or a new
training signal that changes top-1 accepted depth, not another small
continuation/auxiliary-loss sweep.
