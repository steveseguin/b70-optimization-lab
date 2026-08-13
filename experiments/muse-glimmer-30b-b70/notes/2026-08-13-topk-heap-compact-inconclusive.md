# Compact k=15 top-k heap state: inconclusive

Date: 2026-08-13

The default-off `GGML_SYCL_TOP_K_HEAP_COMPACT=1` specialization reduced the
per-work-item private arrays from capacity 32 to 15 only for the retained
tree-merge/block512/heap-scan/k15 path. Comparator, selection, merge, and
output order were unchanged.

The canonical 64-token control/candidate/control smoke preserved all hashes,
proposal counts, and acceptance counts. Rates were:

| arm | prose | code | JSON | mean |
|---|---:|---:|---:|---:|
| compact off before | 65.212 | 109.917 | 213.598 | 129.576 |
| compact on | 69.342 | 114.212 | 220.864 | 134.806 |
| compact off after | 68.949 | 114.364 | 221.221 | 134.845 |

The leading control was cold. Against the warmed trailing control the
candidate saved 0.329 ms/round for prose but regressed 0.068/0.078 ms for
code/JSON and did not improve arithmetic-mean throughput. This is not enough
evidence for a full 256-token run or retention.

- experiment source: `c3df5489f`;
- revert: `910d0d71b`;
- config: `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-topk-heap-compact-current-smoke-cac.json`;
- JSONL: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-topk-heap-compact-current-smoke-cac-20260813.jsonl`.

Decision: preserve as inconclusive and revert. Do not bank any saving.

