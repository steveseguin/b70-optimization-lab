# Qwen27 zero-preserving gated stacked refinement: no win

Date: 2026-07-10

Status: valid offline acceptance experiment; full stacked-refinement family
closed before endpoint integration. This is not a throughput or quality result
and is not eligible for LocalMaxxing.

## Question

The direct cloned refinement layer reduced visible tokens/step before training
because it was not an identity transformation after the frozen MTP final norm.
This follow-up wrapped the same 372M-parameter nonlinear causal refinement in a
learned scalar or per-channel gate:

```text
output = base + gate * (refined - base)
```

A zero gate exactly preserves the frozen base tensor in the synthetic parity
test and preserved heldout acceptance in the real XPU smoke. Four B70s then
screened zero/near-zero initialization and all-step/conditional losses for
1,024 optimizer steps each.

## Result

| candidate | base | before | after | delta versus matching base |
| --- | ---: | ---: | ---: | ---: |
| vector `0`, all-step, `lr=2e-5` | `2.217532` | `2.217938` | `2.234984` | `+0.017451` |
| vector `0.01`, all-step, `lr=1e-5` | `2.217938` | `2.215909` | `2.233766` | `+0.015828` |
| vector `0`, conditional, `lr=2e-5` | `2.217938` | `2.217532` | `2.230925` | `+0.012987` |
| scalar `0`, all-step, `lr=2e-5` | `2.217938` | `2.217532` | **`2.241883`** | **`+0.023945`** |

The best gain is about `1.08%` in this offline evaluator and remains far below
the fixed `3.3` endpoint-trial gate. The winning scalar gate ended at only
`-0.0078125`; vector gates also remained small (absolute extrema about
`0.008`). The optimizer learned that only a tiny interpolation is useful.

Do not endpoint-integrate, continue training, or claim throughput from these
rows. The direct replacement and zero-preserving gated forms jointly close the
full stacked-refinement family for this checkpoint/dataset.

## Artifacts

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-stacked-refinement/mtp5-gated-pre-gate-4gpu-20260710T011712Z
```

Checksums:

```text
1476be3d90e75e54e55ae64b3052eda17fd37087ddbc379aaae558bbe7c84c0c  matrix-summary.json
fb8e460e76e81211dab426b684b527817490d360128e746cede68692cf6ab295  scalar-zero-all-lr2e-5/stacked_mtp_refinement.safetensors
0459bea48327858536aa35d5c7f74281a2c462630bfe005dde5546ab176aecaf  scalar-zero-all-lr2e-5/training_summary.json
```

Tracked compact summary and reproduction:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-stacked-refinement-gated-pregate-20260710.json
scripts/train-qwen27-stacked-mtp-refinement.py
experiments/qwen36-27b-autoround-int4-b70/scripts/run-stacked-refinement-gated-pre-gate-4gpu.sh
```

## Next action

Acceptance-only adaptation is now exhausted across FC, position FC, low-rank
position adapters, direct full refinement, and gated full refinement. Return to
the other side of the 100 tok/s equation: reduce the expensive target verifier
body using aggregate region timing, then combine a real multi-millisecond body
win with the existing target-verified MTP3 acceptance.
