# 2026-07-07: EAGLE3 wide top-k reranker no endpoint

## Classification

Diagnostic only. No endpoint throughput claim, no quality claim, and no
LocalMaxxing submission.

## Why

The wide top-k oracle showed `K=64` and `K=128` contain enough target-token
signal to cross `100 tok/s` only under an impossible same-cost magic extractor.
The listwise rank-push attempt did not move the draft itself. This screen asked
whether a stronger pre-verification candidate reranker could extract that
signal without changing the draft checkpoint.

## Run Identity

Runner:

```text
experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle3-wide-topk-reranker-4gpu.sh
```

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-wide-topk-reranker-4gpu-20260707T104909Z
```

Draft checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-allscope-20260707T075425Z/all-r5-lr3e-6-decay0p25/checkpoint
```

Heldout dataset:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z/shard-3/dataset
```

Compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-wide-topk-reranker-summary-20260707.json
```

## Results

Baseline top-1 draft: `1.1014610941216445` heldout mean accepted.

Prior small top-8 MLP reranker: `1.1192660550458715` heldout mean accepted.

| label | K | hidden | mean accepted |
| --- | ---: | ---: | ---: |
| `k64-h512-lr1e-3` | 64 | 512 | `1.1153924566768603` |
| `k64-h1024-lr5e-4` | 64 | 1024 | `1.091063540604825` |
| `k128-h512-lr5e-4` | 128 | 512 | `1.0834522595990486` |
| `k128-h1024-lr3e-4` | 128 | 1024 | `1.0831124702684336` |

## Decision

No endpoint speed run. No LocalMaxxing submission.

Wider candidate lists and larger MLPs did not extract the oracle signal. The
best wide reranker is below the prior small top-8 MLP reranker and far below
the `1.5-2.0` offline endpoint gate.

Cheap selected-candidate extraction from this frozen Ex0bit-format draft is
closed. Future EAGLE/DFlash work needs a materially stronger draft architecture
or better target-matched data/objective that makes the desired token rank-1
directly, not more local top-k reranker sweeps.
