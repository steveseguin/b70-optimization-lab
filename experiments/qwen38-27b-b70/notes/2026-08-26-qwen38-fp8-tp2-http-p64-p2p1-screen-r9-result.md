# Qwen3.8 official FP8 TP2 p64 oneCCL P2P screen R9 result

Status: **promising diagnostic; confirmation required; not published**.

The one-server c64 screen completed at `730.598639 tok/s`, 5.0024% above the
qualified `CCL_TOPO_P2P_ACCESS=0` control (`695.792088 tok/s`). It clears the
frozen `730.581692 tok/s` advancement threshold by only `0.016947 tok/s`, so
the threshold decision is pass but the evidence is not remotely sufficient
for promotion by itself.

The server log confirms `CCL_TOPO_P2P_ACCESS=1` on both ranks. All 64 responses
returned 128 raw token IDs, reported zero cached prompt tokens, and passed the
cross-base output-isolation gate. Median/p95 TTFT was
`1,449.32 / 2,122.67 ms`; median/p95 end-to-end latency was
`10,945.43 / 11,147.39 ms`. The harness exited zero and cleanup was clean.

Per the preregistration, the candidate advances to two new fresh servers with
the complete c1/2/4/8/16/32/64 ladder. Publication remains forbidden unless
the confirmation median retains the 5% c64 gain and every output, cleanup,
throughput-stability, and latency-stability gate passes.

Evidence: [complete attempt directory](../data/qwen38-fp8-tp2-http-p64-p2p1-screen-20260826-r9-attempt1/),
[preregistration](2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-screen-r9-preregistration.md).
