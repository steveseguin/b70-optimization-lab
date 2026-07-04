# 2026-07-04 - EAGLE v2 stronger offline screen, no endpoint candidate

## Classification

Diagnostic-only EAGLE v2 offline acceptance screen. This is not an endpoint
throughput result, not a strict fresh-response result, and not a LocalMaxxing
candidate.

## Why this was run

The current Qwen27 record remains the strict fresh
`webhie/Qwen3.6-27B-int4-AutoRound` runtime INT8 LM-head BF16-scale recipe at
`65.27648650325429 tok/s`. Prior compact EAGLE v2 work was weak
(`0.201-0.616` mean accepted), but the user asked to continue optimization and
we still had one bounded, materially different EAGLE question worth closing:
does a stronger residual/two-layer draft trained on the healthy v2 chat corpus
move held-out acceptance near the threshold that would justify endpoint work?

It did not.

## Reproduction

Script:

```bash
experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle-v2-stronger-offline-screen.sh
```

Successful run:

```bash
experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle-v2-stronger-offline-screen.sh \
  > /tmp/qwen27-eagle-v2-stronger-offline.out 2>&1
```

Artifacts:

- compact summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-v2-stronger-offline-20260704T122300Z-summary.json`;
- raw run root:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle-v2-stronger-offline-20260704T122300Z`;
- v2 corpus root:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260704T102338Z`;
- v2 calibration dataset:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-calib-20260704T101119Z/dataset`.

The large draft checkpoints and raw logs remain under `/mnt/fast-ai`; Git
tracks only the reusable script, this note, and the compact JSON summary.

## GPU isolation lesson

For per-GPU XPU training/eval on this host, use `ZE_AFFINITY_MASK=N` and leave
`ONEAPI_DEVICE_SELECTOR` unset. The first attempted run used both
`ZE_AFFINITY_MASK=N` and `ONEAPI_DEVICE_SELECTOR=level_zero:N`, which made
`torch.xpu` report zero devices for GPUs `1-3`. The final script intentionally
unsets `ONEAPI_DEVICE_SELECTOR` inside each variant subprocess.

## Results

Endpoint-candidate policy for this diagnostic was intentionally conservative:
held-out mean accepted must reach at least `2.0` and step-3 conditional exact
rate must reach at least `0.65` before spending endpoint validation time.

| Variant | Eval split | Mean accepted | Step1 exact | Step2 conditional | Step3 conditional | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `v2-shards012-r3-layer2-residual-e6-lr2e5-max160` | heldout shard 3 | `0.6953125` | `0.3974609375` | `0.48894348894348894` | `0.5326633165829145` | best, but no endpoint |
| `v2-shards012-r3-e8-lr2e5-i8192-max160-tok01` | heldout shard 3 | `0.62158203125` | `0.36962890625` | `0.4464993394980185` | `0.5266272189349113` | no endpoint |
| `v2-shards012-r3-e8-lr1e5-i12288-max160-tok02` | heldout shard 3 | `0.5810546875` | `0.3515625` | `0.4361111111111111` | `0.4968152866242038` | no endpoint |
| `v2-all96-r3-e8-lr2e5-i8192-max160-calib` | separate calibration | `0.44091796875` | `0.3037109375` | `0.32315112540192925` | `0.39800995024875624` | no endpoint |

Best variant histogram:

```text
accepted=0: 1234
accepted=1: 416
accepted=2: 186
accepted=3: 212
```

Best variant family split:

- `long-context`: `0.6394230769230769` mean accepted over `1248` starts;
- `support-escalation`: `0.7825` mean accepted over `800` starts.

## Interpretation

The stronger residual/two-layer draft improved the best held-out compact v2
number from the prior `0.616` to `0.6953125`, but that is still far below the
old offline `2.1016` draft that itself failed endpoint quality/speed and far
below the `2.0` endpoint-candidate threshold.

The all-96-to-separate-calibration result is even weaker at `0.44091796875`,
which means the draft is not merely underfit to heldout shard `3`; it still does
not generalize well enough for serving.

## Decision

No endpoint test. No LocalMaxxing submission. Current EAGLE v2 remains closed
until a materially stronger data/training/init approach appears. The next
credible Qwen27 speed work should return to source/runtime mechanisms around
LM-head call reduction, accepted-token improvement, or deeper drafter metadata,
not another EAGLE endpoint/config sweep.
