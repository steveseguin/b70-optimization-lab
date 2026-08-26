# Qwen3.8 Q8_0-weight/F16-KV TP1 cache64 graph curve

Status: **completed valid, Grade C publication boundary**. Exactly seven
TP1/MTP0/Q8_0-weight/F16-KV cache64 SYCL-graph HTTP cells are authorized at
0, 2K, 4K, 8K, 16K, 24K, and 32K active context. Graph-off cells, Q8_0 KV,
other quants/topologies, prefill, headlines, protected values, and
LocalMaxxing are unchanged.

All seven exact-depth requests passed with zero cached tokens and 128 returned
tokens. Decode ranges from 19.167301559287175 tok/s at x0 to
17.521196458119796 tok/s at 32K under the conventional 99-interval metric.
The full quality battery passed: 7 exact cases, 2 stable repeats, the
25,200-token needle, and 10/10 cache-zero quality requests.

Graph telemetry passed with 947 direct replays against the frozen 896 floor,
64 cache entries, and exact counter conservation. All 19 terminal checks and
cleanup passed. The compact result binds all 25 raw artifacts by SHA-256.

This is a separate graph-patched cache64 profile. It can be slower than the
graph-off profile at the same selector and does not replace graph-off F16 or
Q8_0-KV routes. The synthetic exact-depth curve remains Grade C even though
the separate natural-language quality battery passed.

- result: `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-result.json`
- validator: `experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-q8weights-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-result.py`
- raw root: `/mnt/fast-ai/bench-results/qwen38-q8weights-f16kv-tp1-sycl-graph-cache64-depth-quality-20260826-r1`
