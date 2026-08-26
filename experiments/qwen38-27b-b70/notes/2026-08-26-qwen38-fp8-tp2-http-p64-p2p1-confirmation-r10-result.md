# Qwen3.8 official FP8 TP2 p64 oneCCL P2P confirmation R10 result

Status: **qualified and promoted**.

Two wholly new fresh servers confirmed the
`CCL_TOPO_P2P_ACCESS=1` candidate across c1/2/4/8/16/32/64. Both logs prove
activation on both TP ranks. Every response returned 128 raw token IDs,
reported zero cached prompt tokens, avoided cross-base oracle collisions, and
both attempts cleaned up fully.

| Active users | Aggregate tok/s | Per-user tok/s | TTFT p50 / p95 ms | Range |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 21.557059 | 21.557059 | 95.048 / 95.048 | 0.283% |
| 2 | 41.424196 | 20.712098 | 122.743 / 170.950 | 0.203% |
| 4 | 81.299381 | 20.324845 | 211.000 / 211.286 | 0.299% |
| 8 | 157.990884 | 19.748860 | 267.133 / 267.680 | 0.094% |
| 16 | 293.363030 | 18.335189 | 262.556 / 391.232 | 0.260% |
| 32 | 504.387101 | 15.762097 | 426.066 / 728.501 | 0.525% |
| 64 | **774.394144** | **12.099908** | **768.749 / 1,525.973** | **0.117%** |

The exact c64 attempts were `774.848183` and `773.940105 tok/s`. Their median
is 11.30% above the previously qualified `695.792088 tok/s` P2P-off profile
and clears the frozen 5% promotion floor. Worst throughput range across the
ladder was 0.525%; worst reported latency range was 4.404%, within the
10%/15% preregistered gates.

This promotes P2P access only for the 64-slot concurrency service. The
single-slot and long-context receipts retain their captured P2P-off identity;
the shared launcher therefore exposes an explicit setting and the concurrency
wrapper selects one. This remains target-only/MTP0 with FP16 KV, 4,096-token
capacity, 256 batched tokens, prefix cache off, and a size-one graph.

Evidence: [structured aggregate](../data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.json),
[attempt 1](../data/qwen38-fp8-tp2-http-p64-p2p1-confirmation-20260826-r10-attempt1/),
[attempt 2](../data/qwen38-fp8-tp2-http-p64-p2p1-confirmation-20260826-r10-attempt2/),
[preregistration](2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-preregistration.md).
