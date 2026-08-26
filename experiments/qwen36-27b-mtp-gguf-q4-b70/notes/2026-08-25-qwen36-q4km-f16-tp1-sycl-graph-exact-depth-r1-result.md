# Qwen3.6 embedded-MTP Q4_K_M/F16 TP1 SYCL-graph exact-depth R1 result

State: **seven raw graph cells passed; negative optimization; quality pending**.

The create-only campaign completed all exact active-context depths
0/2K/4K/8K/16K/24K/32K with five repetitions of `pp2048` and `tg128` per
cell. The measured prefill/decode averages were:

| Active context | Prefill tok/s | Decode tok/s |
| ---: | ---: | ---: |
| 0 | 818.204240 | 28.579918 |
| 2,048 | 800.162651 | 28.049278 |
| 4,096 | 780.493068 | 27.664886 |
| 8,192 | 746.470110 | 27.180377 |
| 16,384 | 688.173276 | 26.233159 |
| 24,576 | 644.830793 | 25.366200 |
| 32,768 | 606.643612 | 24.569574 |

Graph evidence passed at every depth. Every decode phase recorded and replayed
graphs with zero cache-full, rejection, unsupported-device, update, or recreate
counters. Depth-0 prefill recorded eight shapes and replayed all 24 requests
without cache-full. Prefill from 2K through 32K is mixed partial: cache 8
recorded eight shapes while `cache_full` rose from 20 to 80 as exact depth
increased. These phases must not be described as fully graph-certified.

Against the accepted matching graph-off Q4_K_M/F16 curve, graph-on lost every
prefill and decode cell. The unweighted mean deltas were **-8.137743% prefill**
and **-2.333593% decode**. The depth-0 prefill loss was -0.986596%; nonzero
prefill losses ranged from -10.254954% at 2K to -7.397340% at 32K. No causal
explanation is inferred from this result.

The result binds the exact embedded-MTP-capable Q4_K_M artifact while running
target-only at MTP0, fa0 source plus the ordered three-patch graph chain, the
graph-enabled llama-bench and backend hashes, the canonical 32-entry effective
DSO closure, cache-8 environment, verbose argv, all raw output hashes, and the
matched graph-off result hash. Cleanup passed with no terminal error.

This is raw-engine coverage and mechanism evidence only. Quality is still
pending, site ingestion is not authorized, no record or submission is
authorized, graph estimates were not used, and the faster graph-off values and
all historical featured speeds remain protected.
