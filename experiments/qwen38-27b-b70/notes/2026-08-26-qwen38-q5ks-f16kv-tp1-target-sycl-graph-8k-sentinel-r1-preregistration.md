# Qwen3.8 Q5_K_S F16-KV TP1 graph 8K mechanism sentinel

This packet is intentionally one cell, not a curve. The retained llama.cpp SYCL graph build passed a complete Qwen3.6 graph battery only after pointer-stability and cache-capacity repairs. Qwen3.8 also has historical vLLM graph+MTP corruption evidence. Neither fact proves this separate MTP0 llama.cpp tuple unsafe, but together they make a current-weight 8K correctness sentinel the necessary gate before spending seven depth runs.

Two fresh lifetimes use the same Qwen3.8 UD-Q5_K_S artifact, patched graph-capable binary, argv, F16 KV, fixture, and hardware. Only `GGML_SYCL_ENABLE_GRAPH` and `GGML_SYCL_GRAPH_CACHE_SIZE` change: `0/0` control then `1/8` candidate. The candidate must return identical token IDs, hash, usage, returned-prompt hash, and cache fields for the exact 128-token request, then produce one shutdown summary satisfying the frozen counter algebra: requested equals hit plus miss and replayed, hit equals direct replay, miss equals recorded and created, cache-full is zero, and reject, unsupported, update, and recreate counters are zero.

There is no speed floor. A pass authorizes preparation of the full 0–32K graph curve and independent quality battery; the sentinel itself authorizes no site cell. It does not authorize a curve result, MTP, TP2/4, prefill, headline replacement, or LocalMaxxing submission. A failure is retained as a bounded negative and stops graph-curve expansion.

Launch remains create-only, clean-pushed-main-only, GPU0-exclusive, and inert without the exact acknowledgement embedded in the manifest.
