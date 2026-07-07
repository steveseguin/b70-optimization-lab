# 2026-07-07: ReplaySSM stage+decode fusion pre-gate

## Classification

Diagnostic microbench only. This is not an endpoint benchmark, not a quality
run, and not a LocalMaxxing submission.

## Why

The explorer-suggested second target-body lane was fusing the native
ReplaySSM GDN verifier core:

```text
gdn_replayssm_stage_conv
gdn_replayssm_spec_decode
```

The idea was to remove one launch and avoid writing/reading intermediate
`q/k/v/a/b` tensors across 48 GDN layers.

## Artifact

Reusable script:

```text
scripts/bench-qwen27-replayssm-stage-decode.py
```

Result:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-stage-decode-microbench-20260707T102541Z.json
```

Shape:

```text
rows=1
spec_len=4
cache_len=8
num_k_heads=16
num_v_heads=48
head_k_dim=128
head_v_dim=128
conv_dim=10240
dtype=bf16
state_dtype=bf16
```

This matches the current single-session MTP3/cache8 ReplaySSM verifier shape
well enough for a pre-gate.

## Result

| op | mean ms/layer |
|---|---:|
| `stage_conv` | `0.0230` |
| `spec_decode` | `0.0388` |
| `stage_then_decode` | `0.0454` |

The directly measured paired cost is about `0.045 ms/layer`, or `~2.18 ms`
across 48 GDN layers. A fused kernel could save only some fraction of that,
not all of it.

## Decision

Do not prioritize a fused stage+decode kernel as the main `>100 tok/s` route.
It may be useful later as ReplaySSM polish, but the upper bound is too small:

- current Qwen27 step-cost budget needs about `12.787 ms/step` saved to reach
  `100 tok/s` at current accepted depth;
- stage+decode fusion can plausibly save at most low-single-digit ms, and
  likely less than `1 ms` after keeping the required recurrent math;
- prior stage profiling already showed the whole ReplaySSM-vs-record delta is
  only about `4 ms/step`, enough to recover toward the current record family
  but not enough for a new `>100 tok/s` record.

Keep the script as a future pre-gate. Future `>100 tok/s` work still needs
accepted-depth improvement beyond MTP3 or a much larger target/verifier forward
cost reduction.
