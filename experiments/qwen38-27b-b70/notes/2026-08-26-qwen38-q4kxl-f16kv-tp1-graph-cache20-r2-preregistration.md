# Qwen3.8 Q4_K_XL/F16 TP1 graph cache20 R2 preregistration

R1 was never launched. Its runtime packet correctly requests cache 20, but its
post-run report path inherits a Qwen3.6 helper that hardcodes cache limit 8.
The completed Q5_K_S and Q4_K_M cache20 sentinels proved that this creates a
procedural false failure after valid generation and cleanup.

R2 preserves R1's model, binary, patch chain, graph flags, cache capacity,
workload, arm order, acceptance gates, and lack of a speed floor. The only
functional delta is report parsing: exactly one emitted graph summary must say
`cache_limit=20`; its counters are copied exactly and the existing strict
validator still requires at least 120 hits/direct replays, exact arm parity,
zero cache-full/rejection/update/recreate events, cache-zero requests, and clean
shutdown.

A pass authorizes only a separate reviewed full-curve preregistration. It fills
no website cell and grants no quality, MTP, TP2/TP4, prefill, headline,
protected-speed replacement, or LocalMaxxing authority.
