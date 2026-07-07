# 2026-07-07: EAGLE3 v6b all-scope continuation no-endpoint screen

## Classification

Diagnostic only. No endpoint throughput run, no quality claim, and no
LocalMaxxing submission.

## Objective

The v6b concrete-context corpus and step-focus training improved the Ex0bit
EAGLE3/DFlash-style drafter only to `1.0597349643221203` heldout mean accepted
tokens. This screen tested whether unfreezing the full draft from those best
v6b checkpoints could move acceptance toward the `1.5-2.0` minimum needed
before endpoint or Intel-kernel integration work.

## Run identity

Raw root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-allscope-20260707T075425Z
```

Dataset:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z
```

Target model:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e
```

Common training setup:

- train shards: `0`, `1`, `2`; heldout shard: `3`;
- `--train-scope all`;
- `--epochs 4`;
- `--batch-size 16`;
- `--rollout-survival-mode hard`;
- `--rollout-dead-loss-floor 0.05`;
- `--rollout-rank-loss-weight 0.1`;
- device/dtype: `xpu` / `bfloat16`;
- final oracle: full heldout `scripts/evaluate-qwen27-ex0bit-eagle3-offline.py`
  with `--max-steps 5`.

Compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v6b-allscope-summary-20260707.json
```

## Results

| label | start checkpoint | train rollout | lr | heldout exact | heldout mean accepted | histogram |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `all-r3-lr1e-6-decay0p25` | v6b step-focus r3 | 3 | `1e-6` | `0.580662` | `1.0665307509344206` | `0=6301,1=4317,2=2302,3=899,4=404,5=492` |
| `all-r3-lr3e-6-decay0p25` | v6b step-focus r3 | 3 | `3e-6` | `0.589495` | `1.1013931362555216` | `0=6171,1=4284,2=2326,3=977,4=445,5=512` |
| `all-r5-lr1e-6-decay0p25` | v6b step-focus r5 | 5 | `1e-6` | `0.581198` | `1.0689772341148487` | `0=6295,1=4315,2=2307,3=887,4=415,5=496` |
| `all-r5-lr3e-6-decay0p25` | v6b step-focus r5 | 5 | `3e-6` | `0.589227` | `1.1014610941216445` | `0=6175,1=4287,2=2317,3=972,4=449,5=515` |

Best run: `all-r5-lr3e-6-decay0p25`, mean accepted
`1.1014610941216445`.

## Decision

Close this as **no endpoint**.

The best all-scope continuation improved the v6b step-focus line by only about
`+0.042` accepted tokens, remains below the older v5 survival best
`1.340886544011544`, and remains well below the `1.5-2.0` minimum threshold
for an endpoint speed run. It also shows that simple full-draft unfreezing is
not the unlock for Qwen27 DFlash/EAGLE3 acceptance.

## What this means

Do not repeat v6b all-scope continuation from the same r3/r5 step-focus
checkpoints. The next credible drafter work needs a mechanism change rather
than more LR/epoch sweeps:

- stronger target-owned corpus with less prompt/output distribution mismatch;
- a block-diffusion objective closer to the real DFlash block fill, not only
  autoregressive rollout windows;
- endpoint-trace-driven training examples from actual strict-suite MTP reject
  surfaces;
- or a different draft architecture/source that can clear the offline
  acceptance threshold before backend work.

The external Hipfire/DFlash MQ4 numbers remain useful as a design reference,
but not as a B70/Qwen27 performance claim. Hipfire's own model card reports
typical `tau` around `4-5` for code prompts and much lower prose acceptance,
which is why this fixed realistic-suite acceptance oracle remains the gate.
