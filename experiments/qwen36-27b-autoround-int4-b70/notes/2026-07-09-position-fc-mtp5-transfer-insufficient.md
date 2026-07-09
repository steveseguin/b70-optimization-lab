# 2026-07-09 - Position-specific MTP5 FC transfers but is insufficient

Status: **valid offline acceptance improvement; closed before endpoint testing**.
This is diagnostic draft research, not headline throughput and not eligible for
LocalMaxxing submission.

## Question

The Qwen3.5 MTP checkpoint has one transformer layer and reuses one
full-precision `mtp.fc.weight` at every speculative depth. This experiment
kept the proven shared transformer/KV path and trained five depth-specific FCs
to determine whether that small specialization could make MTP5 acceptance high
enough to support a strict `100 tok/s` endpoint.

Four candidates trained concurrently on the four B70 GPUs. Shards 0-2 of the
v6 chat trajectories supplied training starts; shard 3 supplied the in-run
heldout set. All candidates were then evaluated on the separate v6b context
corpus (`incident-log-triage` and `sql-analytics-table`) with 8,192 starts.
The target-owned trajectories were never part of a throughput benchmark, and
no prompt/KV/history reuse is represented as a speed result.

## Results

| Candidate | Training-heldout visible tok/step | Unseen v6b visible tok/step |
| --- | ---: | ---: |
| all FCs, all-steps, lr `2e-5` | **2.763428** | **2.773804** |
| freeze FC 0, conditional-prefix, lr `2e-5` | 2.571655 | 2.527588 |
| freeze FCs 0-1, conditional-prefix, lr `2e-5` | 2.458252 | 2.432007 |
| freeze FC 0, conditional-prefix, lr `1e-5` | 2.526001 | 2.499878 |

The unchanged shared-FC baseline on this same unseen corpus measured
`2.379883` visible tokens/step (`1.379883` accepted). The all-FC candidate
therefore added `0.393921` visible tokens/step and improved accepted depth by
`28.55%` on matched data. It transferred cleanly. Its unseen conditional exact rates
by depth were `0.772217`, `0.638950`, `0.571499`, `0.525108`, and `0.527617`.
This establishes that position-specific FC capacity is useful and that the
gain was not confined to the training-heldout split.

It is nevertheless below the endpoint gate for the `100 tok/s` objective. The
current MTP3 endpoint averages about `2.747` visible tokens per verifier step;
even applying the unseen-corpus accepted-depth ratio projects only about `3.25`
visible endpoint tokens/step. Historical MTP5 step cost is about `51 ms`, so a
standalone acceptance route needs approximately `5.1-5.2` visible tokens/step
for `100 tok/s`; verifier/LM-head reductions can lower that depth requirement.
No graph-off or graph-on endpoint run was spent on this intermediate
candidate; it is used as the initializer for the residual-adapter screen.

## Artifacts

Large artifacts remain on the model USB drive:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-position-fc/mtp5-4gpu-20260709T225258Z
```

Key checksums:

```text
14d04728416d5a237b394f7f0ca6bee79585fa270045b4df9870183c5a322c48  allfc-allsteps-lr2e5/model_extra_tensors.safetensors
ad0575c8150b8b7d677fb5b3ab635806a827f2cf6a3927e2fe0ef40d4dbecec6  matrix-summary.json
f439c023599b4ea3bd0a13978f00721fd4d6aaee4fc9cb99f10967a2c08cef6b  unseen-v6b-summary.json
```

The same-corpus shared baseline is
`shared-fc-unseen-v6b-eval.json` in the same artifact root.

The all-FC model-extra artifact is `822,594,088` bytes and intentionally stays
outside Git. Commands and per-candidate logs are next to each artifact.

Reproduction tools:

```text
experiments/qwen36-27b-autoround-int4-b70/scripts/run-position-fc-mtp5-training-4gpu.sh
experiments/qwen36-27b-autoround-int4-b70/scripts/run-position-fc-eval-4gpu.sh
scripts/train-qwen27-intrinsic-mtp-adapter.py
scripts/evaluate-qwen27-intrinsic-mtp-offline.py
scripts/create-qwen27-position-fc-overlay.py
```

## Decision and next experiment

Close FC-only specialization as insufficient, but keep its best candidate as
the initialization for a larger learned predictor. The next bounded experiment
adds a depth-specific low-rank residual adapter after the shared MTP layer:

```text
hidden = hidden + up_i(silu(down_i(hidden)))
```

This adds capacity without creating unpopulated per-layer draft KV caches.
Screen four ranks concurrently, evaluate on the full unseen v6b corpus, and
require at least `3.3` visible tokens/step before an endpoint benchmark. Treat
that only as an endpoint-trial gate: at the historical MTP5 cost, acceptance
alone needs about `5.1-5.2` for a credible `100 tok/s` route.
