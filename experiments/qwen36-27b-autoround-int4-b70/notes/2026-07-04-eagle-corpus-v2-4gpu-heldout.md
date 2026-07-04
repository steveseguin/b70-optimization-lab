# Qwen27 EAGLE Corpus V2 Four-GPU Heldout Screen

Date: 2026-07-04

Status: **closed diagnostic-only, not an endpoint candidate**.

## Purpose

Test whether the new chat-style EAGLE corpus/eval v2 path can scale cleanly
across all four B70 GPUs and whether a compact local EAGLE1 draft trained on
three shards generalizes well enough on held-out prompt families to justify an
endpoint benchmark.

This is not a LocalMaxxing or headline throughput result. The run is a
diagnostic drafter-quality screen only.

## Collection

Runner:

```bash
experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle-chat-corpus-v2-4gpu.sh
```

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260704T102338Z
```

The runner launched four independent TP1 vLLM/XPU replicas and collected one
suite shard per GPU from:

```text
experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v2-suite.json
```

Summary:

- `96` chat prompts total, `24` per shard.
- `15360` hidden rows total.
- `96` dataset samples saved.
- `96/96` samples retained prompt metadata.
- `0` continuity breaks.
- Shard 0 families: `database-operations`, `incident-response`,
  `security-review`.
- Shard 1 families: `api-design`, `capacity-planning`,
  `performance-debug`.
- Shard 2 families: `code-review`, `quality-gates`, `release-planning`.
- Shard 3 heldout families: `architecture-tradeoff`, `long-context`,
  `support-escalation`.

This validates the corpus v2 metadata and four-GPU collection plumbing.

## Training Screen

Draft output:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260704T102338Z/draft-v2-heldout-e4-r3-lr3e5-tok01
```

Training split:

- train: shards `0`, `1`, `2` (`72` samples);
- heldout eval: shard `3` (`24` samples).

Configuration:

- epochs: `4`;
- batch size: `1`;
- lr: `3e-5`;
- max len: `128`;
- rollout steps: `3`;
- token loss weight: `0.1`;
- compact shape: hidden `5120`, intermediate `4096`, attention heads `16`,
  KV heads `2`, head dim `128`;
- device: `xpu:0`;
- train/export dtype: `bfloat16`.

Final train metric:

```json
{
  "epoch": 4,
  "step": 288,
  "loss": 1.2338991165161133,
  "feature_loss": 0.828125,
  "token_loss": 4.057741165161133,
  "top1": 0.20967741310596466,
  "top3": 0.3629032075405121
}
```

## Heldout Offline Eval

Eval file:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260704T102338Z/eval-heldout-e4-r3-lr3e5-tok01.json
```

Result:

- starts: `1024`;
- max steps: `3`;
- mean accepted: `0.4892578125`;
- acceptance histogram: `{0: 707, 1: 189, 2: 72, 3: 56}`;
- step 1 exact/top3: `0.3096` / `0.4072`;
- step 2 conditional exact/top3: `0.4038` / `0.5300`;
- step 3 conditional exact/top3: `0.4375` / `0.6016`;
- heldout long-context family: `0.4631` mean accepted over `624` starts;
- heldout support-escalation family: `0.5300` mean accepted over `400`
  starts.

## Interpretation

The corpus path is healthy, but the draft is not useful enough for endpoint
testing. `0.489` heldout mean accepted is far below the earlier local EAGLE1
offline draft (`2.1016` mean accepted on calibration starts), and that stronger
offline draft still failed endpoint quality and throughput badly. Running this
weaker v2 draft through the OpenAI endpoint would waste time.

Do not submit this run to LocalMaxxing and do not treat it as a speed result.

## Next Action

Do not repeat endpoint sweeps for this compact draft. Future EAGLE work needs a
materially stronger drafter before endpoint validation, such as:

- more diverse and larger chat corpus;
- stronger initialization from a previous working draft if compatible;
- longer training with heldout-family checkpoints;
- richer draft architecture only if it still fits the one-B70 service target;
- a heldout threshold substantially closer to, and preferably above, the prior
  `2.1016` offline mean accepted before any endpoint run.

Compact tracked summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-corpus-v2-4gpu-heldout-20260704T102338Z-summary.json
```
