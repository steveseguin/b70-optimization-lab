# Qwen27 position adapter converged below endpoint gate

Date: 2026-07-10

Status: valid offline acceptance experiment; closed before endpoint testing.
This is not a throughput or quality result and is not eligible for
LocalMaxxing.

## Question

The best five-position FC candidate transferred to an unseen corpus at
`2.773804` visible tokens per verifier step. This follow-up added one
depth-specific low-rank residual adapter after the shared MTP layer and asked
whether substantially more predictor capacity could clear the predeclared
`3.3` visible-token endpoint gate.

Four adapter ranks trained concurrently on the four B70 GPUs over `65,536`
unique starts. The best rank-512 row was then continued for another epoch at
four learning rates. Training used target-owned trajectories and an
endpoint-style INT4-dequant draft LM head; no throughput benchmark, prompt
cache, response history, or warmed continuation is involved.

## First matrix

| rank | learning rate | training-heldout visible tok/step | unseen v6b visible tok/step |
| ---: | ---: | ---: | ---: |
| 64 | `2e-4` | `2.820435` | `2.794189` |
| 128 | `1.4e-4` | `2.825317` | `2.800049` |
| 256 | `1e-4` | `2.838379` | **`2.810669`** |
| 512 | `7e-5` | **`2.846191`** | `2.807617` |

The rank sweep improved training-heldout depth, but unseen transfer plateaued
around `2.81`. Rank 256, not rank 512, was the best unseen row.

## Rank-512 continuation

The continuation resumed the exact exported rank-512 adapters rather than
reinitializing them. All rows used another `65,536` starts and `8,192`
heldout starts.

| learning rate | before visible tok/step | after visible tok/step | outcome |
| ---: | ---: | ---: | --- |
| `7e-5` | `2.845825` | **`2.857300`** | small gain |
| `1.4e-4` | `2.845337` | `2.840698` | regression |
| `2.8e-4` | `2.845703` | `2.813843` | regression |
| `5.6e-4` | `2.845581` | `2.778320` | regression |

The best extra epoch added only `0.011475` visible tokens/step on its
training-heldout split. Higher learning rates degraded both first-step and
deeper conditional exactness. This is convergence evidence, not a reason for
another epoch.

## Artifacts

Large artifacts remain outside Git:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-position-adapter/mtp5-4gpu-20260709T232540Z
/mnt/usb-models/llm-optimization-artifacts/qwen27-position-adapter/mtp5-rank512-continuation-20260710T235330Z
```

Checksums for the continuation winner and summary:

```text
4a8bd2880d827a5aebe4a67fdc8f0c5cb4561b038a1ab165c5f9ec538c5a2514  rank512-resume-lr7e-5/model_extra_tensors.safetensors
b4d67c6955a7fe6a6c46c2fe43a4fc05eedf40ccdb748e47af91c82468ca85a0  rank512-resume-lr7e-5/training_summary.json
84055aac10ec8ca0cb12331e8495de7231c46ac7cb5f6ac376d6ea929fd57123  matrix-summary.json
```

Tracked compact summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-position-adapter-rank-matrix-20260709.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-position-adapter-unseen-v6b-20260709.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-position-adapter-rank512-continuation-20260710.json
```

Reproduction:

```text
experiments/qwen36-27b-autoround-int4-b70/scripts/run-position-adapter-mtp5-training-4gpu.sh
experiments/qwen36-27b-autoround-int4-b70/scripts/run-position-adapter-eval-4gpu.sh
experiments/qwen36-27b-autoround-int4-b70/scripts/run-position-adapter-continuation-4gpu.sh
scripts/train-qwen27-intrinsic-mtp-adapter.py
```

## Decision

Close post-final-norm position adapters without an endpoint run. The best
unseen result (`2.810669`) and best continued training-heldout result
(`2.857300`) are both below the `3.3` trial gate and far below the roughly
`5.1-5.2` visible tokens/step required to reach 100 tok/s at the historical
MTP5 step cost.

The next learned predictor must change architecture rather than add more
capacity at the same output seam. The active successor is a full
target-conditioned MTP refinement layer, pre-gated offline before runtime
integration. In parallel, profile the current graph-replayed endpoint with
Level Zero `unitrace` so any target-body SYCL work attacks measured device
kernels rather than eager-reference timings.
