# Qwen3.8-27B Q4_K_M TP2 scheduler screen r1 — preregistration

This diagnostic tests scheduler settings that have not been compared on the
qualified Q4_K_M TP2 HTTP lane. It uses only this host's two B70 GPUs. It does
not contact or alter the other computer.

The frozen arms vary batch size, micro-batch size, total context allocation,
and host threads. The 16,384-token total-context arm provides 256 tokens per
slot at 64 slots; this is enough for the frozen short-prompt plus 128-output
suite, but it is not a long-context result.

The screen is not publication evidence. Each arm gets one fresh server and one
output-audited c64 batch. A candidate must beat the fresh 2048/256/32768/8
control by at least 3%. If it does, it advances to two fresh full concurrency
curves, the strict mixed-content target-only suite, and the two-round c64
semantic canary. No interpolation or extrapolation is allowed.

The complete contract and identities are frozen in
[`2026-08-30-qwen38-q4km-tp2-scheduler-screen-r1-prereg.json`](../data/2026-08-30-qwen38-q4km-tp2-scheduler-screen-r1-prereg.json).
