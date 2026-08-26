# Qwen3.8 Q8_0-weight/F16-KV TP1 cache64 graph sentinel

Status: **preregistered, not launched**. This packet is inert by default and
authorizes no website cell, speed claim, or protected-result replacement.

The packet tests one exact current-weight Qwen3.8 selector: Q8_0 weights,
TP1, MTP0, F16 KV, fit off, exact 8K HTTP serving. Two fresh lifetimes use the
same graph-patched binary, model, argv, exact request, and full quality battery.
Only `GGML_SYCL_ENABLE_GRAPH` and `GGML_SYCL_GRAPH_CACHE_SIZE` differ: graph
off/cache0 versus graph on/cache64. Exact output token IDs, text, usage and the
quality output hashes must match; every request remains cache-zero.

Cache64 is evidence-derived rather than speculative. Completed Q4_K_M,
UD-Q5_K_S and UD-Q4_K_XL full depth-plus-quality workloads each produced the
same `1182 requested / 947 direct replay` mechanism result at cache64 and
passed their frozen minimum of 896 direct replays. Earlier cache20 full
workloads saturated. The source caps the cache at64, so there is no later
capacity escalation. This evidence selects a mechanism dose; it transfers no
Q8 speed, output, quality or fit claim.

The candidate must produce one exact graph summary with strict accounting,
cache limit64, at least 120 direct replays and a direct/requested fraction of
at least 0.35. Compatibility rejection, device unsupported, update and
recreate counters must remain zero. Cache-full events are allowed only because
the matched quality workload introduces additional shapes; they remain fully
accounted as `miss - created` and `requested - replayed`.

The graph-off parent already authorizes seven Grade-C graph-off Q8/F16 cells
and passed the full Qwen3.8 battery. It is immutable evidence, not a substitute
for the same-binary control here. A sentinel pass authorizes only preparation
of a new, separately reviewed seven-depth graph packet. The sentinel itself
publishes zero cells. Failure is retained as a bounded Q8 graph-mechanism or
quality negative and does not change graph-off evidence.
