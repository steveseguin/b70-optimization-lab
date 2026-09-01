# Qwen3.8 Flash-Next FP8 HC-up grouped graph result

Date: 2026-09-01
Status: exact-output positive; graph performance negative

The earlier eager screen made grouped GEMM look attractive for the real
layer-0 HC-up weight. The relevant endpoint execution mode reverses that
result. Across 100 changing-input XPU-graph replays, both the existing regular
linear and grouped candidate matched the eager authority exactly and produced
100 unique hashes, but their median graph replay times were `11.8875 us` and
`13.9112 us`. Grouped execution was `17.0238%` slower.

This explains why the eager component lead did not transfer to the A30
endpoint. The grouped HC-up route is closed for the full-decode graph and will
not consume another model load. The reusable exact real-weight graph probe is
tracked at
[`../tools/probe-hc-up-grouped-xpu-graph.py`](../tools/probe-hc-up-grouped-xpu-graph.py).

Structured result:
[`../data/20260901-hc-up-grouped-xpu-graph-negative.json`](../data/20260901-hc-up-grouped-xpu-graph-negative.json).
