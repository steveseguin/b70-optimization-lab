# 2026-07-07: intrinsic MTP deep-scope screen no-endpoint

## Classification

Offline diagnostic intrinsic-MTP accepted-depth screen only. This is not an
endpoint throughput result, not a quality run, and not a LocalMaxxing
submission.

## Question

Earlier intrinsic-MTP tuning of only `mtp.fc.weight` and nearby norms improved
offline accepted-depth, but did not transfer to the strict fresh endpoint. This
screen tested whether much larger trainable slices of the checkpoint's own MTP
block could materially raise accepted draft depth before spending endpoint
engineering time.

The key gate is accepted draft tokens per verifier step. At the current Qwen27
step cost, `>100 tok/s` needs roughly `4+` visible tokens per target step
(`3+` accepted draft tokens), and the `125 tok/s` class needs about `5` visible
tokens per step.

## Setup

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/intrinsic-mtp-deep-4gpu-20260707T112602Z
```

Target model:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e
```

Heldout/eval corpus:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z/shard-{0,1,2,3}/dataset
```

Common evaluator settings:

- `max_steps=5`
- `train_starts=8192`
- `heldout_starts=4096`
- `heldout_samples=288`
- `draft_lm_head=int4-dequant`
- `draft_lm_head_group_size=128`
- `draft_lm_head_scale_dtype=bf16`

Tooling:

- `scripts/train-qwen27-intrinsic-mtp-adapter.py`
- `scripts/evaluate-qwen27-intrinsic-mtp-offline.py`

The new deep scopes save `diagnostic_dense_updates.safetensors` instead of
`model_extra_tensors.safetensors`, because these tensors are dequantized
diagnostic replacements for GPTQ-packed checkpoint weights. They are not an
endpoint-compatible patch.

Tracked compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-intrinsic-mtp-deep-scope-4gpu-summary-20260707.json
```

## Results

Heldout metric: mean accepted draft tokens over `4096` starts.

| Run | Scope | LR | Before | After | Delta | Visible tokens/step | Endpoint-compatible |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `attn-lr1e-6` | `attn` | `1e-6` | `1.301025` | `1.399902` | `+0.098877` | `2.399902` | no |
| `mlp-lr1e-6` | `mlp` | `1e-6` | `1.300537` | `1.408691` | `+0.108154` | `2.408691` | no |
| `attnmlp-lr5e-7` | `attn-mlp` | `5e-7` | `1.300781` | `1.416016` | `+0.115234` | `2.416016` | no |
| `alldense-lr5e-7` | `all-dense` | `5e-7` | `1.300537` | `1.413086` | `+0.112549` | `2.413086` | no |

Best result:

```text
attnmlp-lr5e-7: 1.416015625 accepted draft tokens
```

## Interpretation

The lift is real but small. Training hundreds of millions of dequantized dense
MTP parameters improves the heldout accepted-depth by only about `+0.115`
accepted draft tokens, leaving the best candidate at `2.416` visible tokens per
verifier step. That is still below the current endpoint MTP3 branch-trace
range and far below the accepted-depth needed for `>100 tok/s`.

Because these variants are also not endpoint-compatible with the packed INT4
checkpoint format, there is no reasonable endpoint integration path for this
screen.

## Decision

Close deep intrinsic-MTP scope training as no-endpoint.

Do not repeat FC-only, FC+norms, attention-only, MLP-only, attention+MLP, or
all-dense intrinsic-MTP sweeps on this v6/v6b corpus unless there is a new
mechanism or a much stronger accepted-depth signal. The next drafter route
should be a genuinely stronger draft source, such as the full-vocab five-aux
EAGLE3/DFlash rank-push pre-gate, or a different architecture that proves high
accepted prefix length before endpoint work.
