# Qwen3.8 official FP8 TP2 p64 capacity screen R4 closeout

Status: **closed promising diagnostic; not publication evidence**.

The one fresh p64 server passed direct model verification, output isolation,
and cleanup. c64 measured `694.859186 tok/s`, 47.79% above the qualified p32
c32 control of `470.181647 tok/s`. Median/p95 TTFT at c64 was
`889.249 / 1,742.852 ms`; all 64 requests were within the configured active
slots.

Every response returned 128 raw token IDs, used zero cached prompt tokens, and
avoided every cross-base compact-oracle collision. Single-user behavior stayed
on the existing baseline at `21.536814 tok/s`.

This clears the preregistered 5% selection threshold but remains a one-server
diagnostic. It is not added to the package or website. Two wholly new p64
servers must pass the frozen throughput and latency stability gates before any
public promotion. No value is interpolated or extrapolated.

See the [machine-readable closeout](../data/2026-08-26-qwen38-fp8-tp2-http-p64-capacity-screen-r4-closeout.json).
