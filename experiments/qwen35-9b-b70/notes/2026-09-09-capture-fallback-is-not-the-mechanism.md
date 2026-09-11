# Capture fallback is not the mechanism either (2026-09-09)

`c1cap`: depth-1 concurrency ladder with the graph capture ceiling raised from 64 to 256, matched
1:1 against `d1` - same depth, same rungs, same host, same card, both serial on a quiet card.

**The intervention is verified applied.** `COMPILATION_CONFIG` reaches the container as a serve
argument rather than an environment variable, so it is invisible to the harness's env check and had
to be read out of the recorded container command line:

```
d1      max_cudagraph_capture_size = 64    sizes tail: 40, 50, 60, 64
c1cap   max_cudagraph_capture_size = 256   sizes tail: 128, 160, 192, 256
```

At depth 1 a 64-user batch presents 128 decode rows, so `d1`'s top two rungs were genuinely running
outside capture and `c1cap` genuinely changed the execution path underneath them.

| users | d1 (cap 64) | c1cap (cap 256) | d1 tok/s | c1cap tok/s |
| ---: | --- | --- | ---: | ---: |
| 16 | 16/16, 16/16 | 16/16, 16/16 | 905.0 | 898.1 |
| 32 | 30/32, 31/32 | 30/32, 30/32 | 988.4 | 983.3 |
| 64 | 60/64, 61/64 | 61/64, 61/64 | 1034.5 | 1039.9 |

**Pooled divergence: 10/254 against 10/254. Identical.**

## What this closes

The exactness loss under speculation is **not** an artifact of decode shapes falling outside graph
capture and running eager. This was the one remaining hypothesis that would have made the framing
wrong rather than incomplete - eager and captured are different execution paths and this lane
already knows they disagree - so eliminating it means the finding stands as stated: speculation
itself raises the divergence rate about an order of magnitude at 32 users and above.

## Secondary result

Raising the capture ceiling is **free and worthless** at these rungs: +0.5% at 64 users, -0.8% at
16, everything inside the noise band. It is not a speed lever, and the inherited `[1..64]` list
costs nothing despite being the 27B lane's rather than this model's. That closes lever A3.

## Mechanisms eliminated so far, both with the intervention verified in-container

1. Row-count dependence of the RMSNorm (`b1sn`, `VLLM_XPU_RMSNORM_SERIAL_ROWS=256`): 10/254 -> 8/254,
   and no effect on the no-speculation divergence either.
2. Graph capture fallback (`c1cap`, ceiling 64 -> 256): 10/254 -> 10/254.

Remaining: `b3lm` (`VLLM_XPU_LM_HEAD_BATCH_INVARIANT`) targets where a two-way tie is actually
resolved rather than an upstream perturbation, and is now the leading candidate. `b2rs`
(`VLLM_XPU_GDN_ROW_STABLE_RMSNORM`) is a different formulation of the reduction that `b1sn` already
argues against, so its prior is now low.
