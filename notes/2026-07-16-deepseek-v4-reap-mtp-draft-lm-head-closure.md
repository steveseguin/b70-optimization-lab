# DeepSeek V4 REAP MTP draft LM-head fusion closure

## Question

The attached MTP1 draft projects a 4,096-wide hidden row through a local 32,320-token BF16 LM-head shard on each TP rank, then selects a local argmax. Because this rereads 252.5 MiB/rank per speculative cycle, a fused streaming projection/argmax kernel looked like a possible architectural win.

The gate measured the same local shape with BF16 weights and activation on every B70. It timed projection, local argmax, and the two operations together. Raw data is in `data/deepseek-v4-reap-mtp-draft-lm-head-20260716/`; the reusable benchmark is `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/bench-mtp-draft-lm-head.py`.

## Result

| GPU | projection (ms) | argmax (ms) | combined (ms) | projection GB/s | perfect fused ceiling (ms) |
|---|---:|---:|---:|---:|---:|
| 0 | 0.501800 | 0.013676 | 0.513136 | 527.63 | 0.077667 |
| 1 | 0.501696 | 0.013676 | 0.512980 | 527.74 | 0.077511 |
| 2 | 0.501592 | 0.013676 | 0.513032 | 527.85 | 0.077563 |
| 3 | 0.501566 | 0.013728 | 0.513032 | 527.88 | 0.077563 |

At an assumed 608 GB/s device bandwidth, reading the weights alone requires 0.435469 ms. The existing projection is already at about 528 GB/s, and local argmax costs only about 0.014 ms. Even a hypothetical implementation that reaches the full bandwidth roof and makes argmax free can save only about 0.078 ms per speculative cycle.

## Decision

Close the BF16 draft-head projection/argmax fusion lane. It cannot clear the 0.50 ms complete-cycle integration gate, and the already-tested local-argmax communication reduction confirms that the remaining full weight read dominates. Do not change draft-head precision or approximate the draft simply to manufacture a benchmark win; target verification would preserve correctness, but altered draft acceptance must be judged on held-out real workloads and is outside this frozen Q4 path.

The next work must use a fresh phase-correct profile of the complete record MTP1 cycle to find a boundary with a measured saving ceiling above 0.50 ms.
