# Qwen3.8 27B Q8 TP2 DP4A3 × SG24 synergy

Date: 2026-08-17

Status: active; claimed on the reference ASRock host

The accepted DP4A2×SG24 row schedule produced a repeatable endpoint gain,
while DP4A4×SG24 retained a `+0.579%` direct-benchmark gain but collapsed to
`+0.0245%` on the pooled cold endpoint. Three independent integer chains are
the untested intermediate register-pressure/ILP point.

The candidate assigns one reordered-Q8 DP4A operation to each of three
independent integer accumulators and folds the fourth operation into one of
those chains. The three integer partial sums are combined before the unchanged
per-block FP32 scale/accumulation boundary. Model values, tensor split, SG24
geometry, runtime doors, F16 KV, FlashAttention, and `b1024/ub256` remain fixed.

The first gate is a clean oneAPI 2026.1.1 build and one-token TP2 smoke. The
performance screen will use fresh processes with exact position complements
against promoted DP4A2×SG24. Endpoint and semantic work is allowed only after
a repeatable direct gain. Other hosts should not duplicate this exact arm while
the claim is active.
