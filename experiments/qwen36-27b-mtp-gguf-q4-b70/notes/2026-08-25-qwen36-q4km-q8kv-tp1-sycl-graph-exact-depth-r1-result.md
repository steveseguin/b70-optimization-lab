# Qwen3.6 embedded-MTP Q4_K_M/q8KV TP1 SYCL-graph exact-depth R1 result

State: **seven raw graph cells passed; negative optimization; quality pending**.

The create-only campaign completed exact active-context depths
0/2K/4K/8K/16K/24K/32K with five repetitions of `pp2048` and `tg128` per
cell. The measured prefill/decode averages were:

| Active context | Prefill tok/s | Decode tok/s |
| ---: | ---: | ---: |
| 0 | 815.877694 | 27.772144 |
| 2,048 | 795.429139 | 25.394435 |
| 4,096 | 775.658122 | 23.531468 |
| 8,192 | 738.529652 | 20.563554 |
| 16,384 | 684.943876 | 16.006453 |
| 24,576 | 639.660372 | 13.207670 |
| 32,768 | 600.523388 | 11.299961 |

Graph evidence passed at every depth. Every decode phase recorded and replayed
graphs with zero cache-full, rejection, unsupported-device, update, or recreate
counters. Depth-0 prefill recorded eight shapes and replayed all 24 requests
without cache-full. Prefill from 2K through 32K is mixed partial: cache 8
recorded eight shapes while `cache_full` rose from 20 to 80. These deeper
prefill phases must not be described as fully graph-certified.

Against the accepted matching graph-off Q4_K_M/q8KV curve, graph-on lost every
prefill and decode cell. The unweighted mean deltas were **-8.146575% prefill**
and **-1.468264% decode**. The depth-0 prefill loss was -1.059975%; nonzero
prefill losses ranged from -10.407396% at 4K to -7.364257% at 32K. No causal
explanation is inferred from this result.

The result binds the exact embedded-MTP-capable Q4_K_M artifact while running
target-only at MTP0, q8_0 K/V cache selectors, fa0 source plus the ordered
three-patch graph chain, graph-enabled llama-bench and backend hashes, the
canonical 32-entry effective DSO closure, cache-8 environment, verbose argv,
all raw output hashes, and the matched graph-off result hash. Cleanup passed
with no terminal error.

This is raw-engine coverage and mechanism evidence only. Quality is still
pending, site ingestion is not authorized, no record or submission is
authorized, graph estimates were not used, and the faster graph-off values and
all historical featured speeds remain protected.
