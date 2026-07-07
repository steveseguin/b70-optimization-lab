# Qwen27 Intrinsic MTP5 Adaptation Screen: Offline Lift, No Endpoint Candidate

Date: 2026-07-07

Model: `webhie/Qwen3.6-27B-int4-AutoRound`

Purpose: test whether training the checkpoint's intrinsic Qwen MTP adapter for
`num_speculative_tokens=5` produces enough accepted draft tokens to justify a
cache16/MTP5 endpoint run. This is diagnostic only: no throughput claim and no
LocalMaxxing submission.

## Setup

Tooling:

- `scripts/train-qwen27-intrinsic-mtp-adapter.py`
- `scripts/evaluate-qwen27-intrinsic-mtp-offline.py`

Data:

- V6 broad chat-style target-hidden corpus:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z`
- training shards: `shard-0`, `shard-1`, `shard-2`
- heldout shard: `shard-3`

Common command shape:

```bash
cd /home/steve/llm-optimizations
ZE_AFFINITY_MASK=<gpu> \
python3 scripts/train-qwen27-intrinsic-mtp-adapter.py \
  --model-dir /mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
  --dataset-dirs \
    /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z/shard-0/dataset \
    /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z/shard-1/dataset \
    /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z/shard-2/dataset \
    /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z/shard-3/dataset \
  --heldout-samples 288 \
  --max-steps 5 \
  --train-starts 16384 \
  --heldout-starts 8192 \
  --batch-size 4 \
  --epochs 1 \
  --scope <fc|fc-norms> \
  --lr <lr> \
  --seed 27 \
  --draft-lm-head int4-dequant \
  --draft-lm-head-group-size 128 \
  --draft-lm-head-scale-dtype bf16 \
  --out-dir experiments/qwen36-27b-autoround-int4-b70/diagnostics/<run-id>
```

The exported `model_extra_tensors.safetensors` files are intentionally ignored
by Git (`*.safetensors`). Track `training_summary.json` only.

## Results

Heldout metric is mean accepted draft tokens under endpoint-style INT4-dequant
draft LM-head, `max_steps=5`, `8192` heldout starts.

| Run | Scope | LR | Before | After | Visible tokens/step | Full-5 accepts | Conditional exact after |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `qwen27-intrinsic-mtp5-int4-v6-fc-lr1e5-16k-e1-20260707` | `fc` | `1e-5` | `1.374268` | `1.682129` | `2.682129` | `641` | `[0.7385, 0.6221, 0.5667, 0.5588, 0.5378]` |
| `qwen27-intrinsic-mtp5-int4-v6-fc-lr2e5-16k-e1-20260707` | `fc` | `2e-5` | `1.374634` | `1.780396` | `2.780396` | `805` | `[0.7531, 0.6396, 0.5824, 0.5949, 0.5889]` |
| `qwen27-intrinsic-mtp5-int4-v6-fc-lr3e5-16k-e1-20260707` | `fc` | `3e-5` | `1.375000` | `1.778809` | `2.778809` | `788` | `[0.7552, 0.6420, 0.5760, 0.5844, 0.5894]` |
| `qwen27-intrinsic-mtp5-int4-v6-fcnorms-lr2e5-16k-e1-20260707` | `fc-norms` | `2e-5` | `1.374390` | `1.781982` | `2.781982` | `804` | `[0.7533, 0.6399, 0.5850, 0.5905, 0.5894]` |

Best offline candidate:

- `qwen27-intrinsic-mtp5-int4-v6-fcnorms-lr2e5-16k-e1-20260707`
- mean accepted draft tokens: `1.781982421875`
- visible tokens per verifier step: `2.781982421875`
- full-5 accepts: `804 / 8192`

## Interpretation

The offline lift is real, but it is not strong enough for an endpoint MTP5
candidate:

- current endpoint MTP3 branch trace already measured about `1.6727` accepted
  draft tokens / `2.6727` visible tokens per verifier step;
- the best MTP5 offline heldout is only about `+0.11` accepted draft tokens
  above that current endpoint trace;
- prior config-only MTP4/MTP5 cache16 endpoint work lost badly because cache16
  and deeper speculative scheduling add compile/runtime overhead;
- the previous direct MTP3 trained candidate looked stronger offline but
  transferred worse on the fixed realistic endpoint suite (`1.5773` accepted
  draft prefix vs current `1.6727`).

Because of that transfer risk and the small margin, do not spend a strict
endpoint speed run on these MTP5 candidates. They are useful as evidence that
simple intrinsic-MTP `fc` / `fc-norms` tuning can improve offline acceptance,
but not enough to reach the >100 tok/s goal.

## Decision

Closed as no endpoint candidate.

Next credible speed work should not be more intrinsic-MTP FC-only training. Use
one of:

1. a stronger drafter architecture / DFlash-style acceptance oracle that proves
   high accepted-prefix length on the fixed realistic suite before endpoint
   work;
2. a producer-integrated LM-head shortcut that avoids materializing full vocab
   logits for draft/verifier rows;
3. deeper graph-safe GDN/DeltaNet transaction work if it enables higher
   accepted tokens per target step without correctness failures.

