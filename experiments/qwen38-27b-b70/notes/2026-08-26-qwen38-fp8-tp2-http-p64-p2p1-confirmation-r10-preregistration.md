# Qwen3.8 official FP8 TP2 p64 oneCCL P2P confirmation R10

Status: **preregistered confirmation; not launched**.

R9's one-server c64 result (`730.598639 tok/s`) cleared its 5% advancement
threshold by only `0.016947 tok/s`; R9 remains excluded from publication.
R10 therefore runs two wholly new fresh servers with
`CCL_TOPO_P2P_ACCESS=1` and the complete c1/2/4/8/16/32/64 ladder.

Everything else remains the qualified official-FP8 TP2, FP16-KV,
target-only/MTP0, 64-slot, 256-batched-token, prefix-cache-off, size-one-graph
service. Every response must contain 128 raw token IDs, use zero cached prompt
tokens, and pass output isolation. Both logs must prove P2P activation and both
attempts must clean up.

Promotion requires all pointwise throughput ranges ≤10%, all TTFT/end-to-end
p50/p95 ranges ≤15%, and a two-attempt c64 median of at least
`730.581692 tok/s`. Rates and latencies are exact medians of the two attempts;
R9 is never pooled. No value is interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-prereg.json).
