# Qwen27 direct stacked MTP refinement: no win

Date: 2026-07-10

Status: valid offline acceptance experiment; direct replacement form closed
before endpoint integration. This is not a throughput or quality result and is
not eligible for LocalMaxxing.

## Question

Post-output position FCs and low-rank adapters plateaued below the fixed `3.3`
visible-token endpoint-trial gate. This experiment made a larger architectural
change: clone the intrinsic MTP attention/MLP layer into a new 372M-parameter
causal refinement layer, apply it after the frozen MTP output sequence, and
train against target-owned trajectories.

The four B70s screened full/all-step, full/conditional-prefix,
attention-only, and MLP-only scopes concurrently. Each row used 1,024 optimizer
steps, up to 8,192 unique training starts, a separate ordered 16-sample
holdout, endpoint-style INT4-dequant draft LM-head weights, and no cache,
history, repeated-response, or endpoint throughput measurement.

## Result

| candidate | frozen base visible tok/step | cloned before training | after 1,024 steps |
| --- | ---: | ---: | ---: |
| full, all-step, `lr=2e-6` | `2.217532` | `1.697646` | `1.836851` |
| full, conditional-prefix, `lr=2e-6` | `2.217532` | `1.698052` | `1.836445` |
| attention-only, all-step, `lr=5e-6` | `2.217938` | `1.698052` | `1.863231` |
| MLP-only, all-step, `lr=5e-6` | `2.217938` | `1.698052` | **`1.866477`** |

All rows remained below the frozen base, never approached `3.3`, and therefore
do not justify runtime/KV-cache integration or an unseen-corpus endpoint gate.
More epochs on this direct replacement are not warranted.

## Interpretation

The cloned layer is not an identity transformation when inserted after the
already final-normalized intrinsic MTP output. It immediately destroys about
`0.52` visible tokens/step, and 1,024 steps recover only a fraction of that
loss. This closes the **direct replacement** form, not every nonlinear
refinement architecture.

The bounded zero-preserving successor has now been tested and also closed. It
peaked at only `2.241883` visible tokens/step versus a `2.217938` base. See
`2026-07-10-gated-stacked-refinement-no-win.md`. No full-refinement runtime work
is justified.

## Artifacts

Large artifacts remain outside Git:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-stacked-refinement/mtp5-pre-gate-4gpu-20260710T004929Z
```

Checksums:

```text
6a5ac56778758845b8847abc42b581bc52a1682b6977a44f4542c2b9ff448a86  matrix-summary.json
66297401a6a94f8741fff27c9dca4d83242216259cf411767fa32760747606a4  mlp-all-lr5e-6/stacked_mtp_refinement.safetensors
d37613011cfafe9f8a6561f80d0edaca59c0ef82925541ffd200b4f5759ee116  mlp-all-lr5e-6/training_summary.json
```

Tracked compact summary and reproduction:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-stacked-refinement-direct-pregate-20260710.json
scripts/train-qwen27-stacked-mtp-refinement.py
experiments/qwen36-27b-autoround-int4-b70/scripts/run-stacked-refinement-pre-gate-4gpu.sh
```
