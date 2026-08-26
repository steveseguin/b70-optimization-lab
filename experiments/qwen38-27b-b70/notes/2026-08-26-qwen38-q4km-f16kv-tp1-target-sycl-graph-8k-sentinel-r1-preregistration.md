# Qwen3.8 Q4_K_M/F16 TP1 SYCL-graph 8K mechanism sentinel

Status: **preregistered, not launched**.

The requested seven-depth graph packet is deliberately blocked. The exact
Qwen3.8 Q5_K_S graph sentinel preserved output parity but produced zero cache
hits across 146 requests and filled its eight-entry cache, so architecture
similarity alone cannot authorize a Qwen3.8 graph curve. Qwen3.6 Q4_K_M does
have verified decode capture/replay, but it is a different weight artifact.

This bounded predecessor compares two fresh server lifetimes at exact 8K on
the checksum-pinned current Qwen3.8 Q4_K_M artifact and the same graph-port
binary. The argv is byte-for-byte equal between arms; only
`GGML_SYCL_ENABLE_GRAPH` and `GGML_SYCL_GRAPH_CACHE_SIZE` change from `0/0` to
`1/20`. Cache 20 is frozen from the 18 observed HTTP warmup/prefill graph
requests plus the two recurrent decode shapes in qualified same-architecture
Qwen3.6 evidence. Both arms must pass exact 128-token, cache-zero, cleanup,
and identical output/text/token-ID/usage/returned-prompt gates. The candidate
must report exactly 146 graph requests, at least 120 real cache hits and direct
replays, every request replayed, strict counter conservation, and zero
cache-full, compatibility, device, update, or recreate events. The source can
support a larger cache, but this packet forbids automatic escalation.

There is no speed floor. A pass grants no site cell; it only authorizes a
separately preregistered full curve and quality packet. A failure leaves all
graph cells missing, closes this cache design, and preserves every historical
speed.

Run inert validation with:

```bash
python3 -B experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py --check
python3 -B experiments/qwen38-27b-b70/scripts/test_qwen38_q4km_f16kv_tp1_target_sycl_graph_8k_sentinel_r1.py
```

Execution remains create-only and requires a clean pushed `main`, all GPU
locks, an idle GPU0 render node, and the exact acknowledgement frozen in the
manifest.
