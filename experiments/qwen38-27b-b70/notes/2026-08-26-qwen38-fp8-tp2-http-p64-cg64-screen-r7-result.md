# Qwen3.8 official FP8 TP2 p64 size-64 graph screen R7 result

Status: **complete negative diagnostic; do not promote**.

The requested PIECEWISE capture sizes `[1,64]` activated successfully. The
server completed both captures in two seconds; CUDAGraph memory rose from the
size-one control's 0.14 GiB/card to 0.24 GiB/card. The c64 request batch then
completed at `668.347132 tok/s`.

All 64 responses returned exactly 128 raw token IDs, used zero cached prompt
tokens, and passed the cross-base output-isolation gate. Median/p95 TTFT was
`1,511.70 / 2,352.78 ms`; median/p95 end-to-end latency was
`11,967.34 / 12,237.56 ms`. The harness exited zero and cleanup was clean.

The candidate is 3.94% slower than the qualified size-one-graph control
(`695.792088 tok/s`) and misses the frozen confirmation threshold by
`62.234560 tok/s`. No confirmation attempts will run, and the package remains
on capture size one. This closes the exact size-64 PIECEWISE capture as a
throughput improvement for this target-only/MTP0 FP8 TP2 service shape.

Evidence: [complete attempt directory](../data/qwen38-fp8-tp2-http-p64-cg64-screen-20260826-r7-attempt1/),
[preregistration](2026-08-26-qwen38-fp8-tp2-http-p64-cg64-screen-r7-preregistration.md).
