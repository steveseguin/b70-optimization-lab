# Qwen3.8 official FP8 TP2 p64 oneCCL P2P screen R9

Status: **preregistered diagnostic; not launched**.

`CCL_TOPO_P2P_ACCESS=1` was neutral at c1, but c64 increases TP collective
payloads. R9 therefore changes only this environment setting from zero to one
and measures one fresh c64 server against the same 64-row output oracle.

All model, FP8, TP2, FP16-KV, target-only/MTP0, 64-slot, 256-batched-token,
cache, and graph settings remain fixed. The output/completeness/cache/cleanup
gates are unchanged. The candidate must reach `730.581692 tok/s` (5% above
the qualified `695.792088 tok/s` control) before two confirmation servers are
allowed. This screen itself is not publishable; no value is interpolated or
extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-screen-r9-prereg.json).
