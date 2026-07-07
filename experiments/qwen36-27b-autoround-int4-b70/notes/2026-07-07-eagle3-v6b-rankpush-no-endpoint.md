# 2026-07-07: EAGLE3 v6b top-k rank-push no endpoint

## Classification

Diagnostic only. No endpoint throughput claim, no quality claim, and no
LocalMaxxing submission.

## Why

The wide top-k oracle showed the best v6b all-scope EAGLE draft contains enough
target-token signal in the top-64/top-128 list to cross `100 tok/s` under an
impossible same-cost magic extractor. The next cheapest implementation question
was whether training could promote those near-miss candidates into rank 1.

## Tooling Added

`scripts/train-qwen27-ex0bit-eagle3-adapter.py` now has a default-off listwise
top-k rank-promotion loss:

```text
--rollout-topk-rank-loss-weight
--rollout-topk-rank-k
--rollout-topk-rank-margin
```

It supplements rollout CE / survival loss by penalizing the strongest
non-target logits in a top-k set, rather than only the single max wrong logit.

Repro runner:

```text
experiments/qwen36-27b-autoround-int4-b70/scripts/run-ex0bit-eagle3-v6b-rankpush-4gpu.sh
```

## Run Identity

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-rankpush-4gpu-20260707T103859Z
```

Start checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-allscope-20260707T075425Z/all-r5-lr3e-6-decay0p25/checkpoint
```

Heldout dataset:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z/shard-3/dataset
```

Compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v6b-rankpush-summary-20260707.json
```

## Results

Baseline: v6b all-scope `1.1014610941216445` heldout mean accepted.

| label | mean accepted | step1 | step2 conditional | step3 conditional |
| --- | ---: | ---: | ---: | ---: |
| `rankpush-k64-w0p25-m0-lr1e-5-d0p25` | `1.1050628610261637` | `0.581311586816174` | `0.5004676174888941` | `0.45363232889511795` |
| `rankpush-k128-w0p5-m0-lr5e-6-d0p25` | `1.1031600407747197` | `0.581243628950051` | `0.49853852449432945` | `0.45426829268292684` |
| `rankpush-k64-w0p5-m0-lr5e-6-d0p25` | `1.1018008834522597` | `0.5807679238871899` | `0.4984788205008191` | `0.45328638497652585` |
| `rankpush-k64-w1-m0p1-lr3e-6-d0p5` | `1.1004417261297996` | `0.5802242609582059` | `0.49754040758959944` | `0.4548022598870056` |

Best lift: `1.10146 -> 1.10506`, only `+0.00360` accepted tokens.

## Decision

No endpoint speed run. No LocalMaxxing submission.

The new loss is mechanically useful and may be reused, but this screen closes
simple listwise rank-promotion from the v6b all-scope checkpoint as a practical
route. The wide top-k oracle says the signal exists; this objective does not
extract it.

Next EAGLE/DFlash work needs a stronger architecture or data-generation change
that moves target tokens into rank 1 directly, not more small loss-weight
sweeps around this checkpoint.
