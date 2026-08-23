# Ornith 1.5 35B-A3B: direct V-cache projection epilogue regresses

Date: 2026-08-23 EDT

Status: **CLOSED PERFORMANCE NEGATIVE — do not ship**

Ornith's Qwen-derived full-attention graph retains ten one-token V-cache store
launches after the accepted Q/K norm-RoPE fusion has already absorbed the ten
K-cache stores. A one-shot accepted-graph dump established the exact V chain:

```text
Vcur [512] -> RESHAPE [256,2] -> VIEW [512] -> F16 SET_ROWS [512,8192]
```

The cache row is selected by a one-element I64 graph leaf. The candidate kept
the incumbent reordered-ESIMD Q4_K/Q6_K dot-product helper and its FP32 `Vcur`
output. Each row-pair leader additionally converted those same FP32 sums to
F16 and wrote the indexed cache row, allowing the later `SET_ROWS` to be
skipped. The default-off matcher required the ten full-attention layer IDs,
exact tensor names/shapes/types, the no-copy reshape/view alias chain, a
ready graph-leaf index, reordered ESIMD weights, and non-overlapping cache,
weight, input, and FP32 output ranges.

## Correctness and activation

The strict seed-42 greedy 128-token control and candidate transcripts were
byte-identical with SHA-256
`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`.
The candidate recorded exactly 1,270 epilogues (10 layers across 127 decoded
evaluations). Repeated decode-only engine runs recorded 8,970 hits apiece.

## Performance

The coarse CLI A/B/B/A bracket crossed and was not sufficient for a decision:
control `84.6, 83.7 tok/s` (mean 84.15) versus candidate `84.4, 84.8 tok/s`
(mean 84.60). It therefore advanced to the established seven-repetition,
higher-resolution `tg128` engine bracket.

| Arm | Engine runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `133.399053`, `133.504375` | **133.451714** |
| direct V-cache epilogue | `132.645912`, `133.503679` | **133.074796** |

The directly measured engine delta is **-0.282%**. The first candidate lost
clearly and the second only tied the second control. Removing ten small cache
store submissions does not repay the added ESIMD epilogue work, so no
fresh-server test was justified and no throughput is inferred from launch
counts.

The accepted source and binaries were restored after the test. The exact
default-off candidate is archived at
`../patches/llamacpp-ornith15-attn-v-cache-performance-negative-20260823.patch`;
the structured result is
`../data/2026-08-23-ornith35b-attn-v-cache-summary.json`.
