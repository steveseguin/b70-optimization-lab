# Qwen3.8 27B Q8 TP2 DP4A4 × SG24 synergy

Date: 2026-08-17

Status: active; claimed on the reference ASRock host

The four-independent-accumulator DP4A row body was performance-neutral in the
older SG8 experiment. The newly accepted DP4A2×SG24 result demonstrates that
the recurrent-quad workgroup geometry can materially alter the balance between
DP4A instruction-level parallelism, register pressure, and occupancy. DP4A4
combined with SG24 is therefore a distinct interaction rather than an
unchanged retry.

The candidate will use the retained exact DP4A4 full source on mndodd
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`, then apply the already accepted
Qwen3.8 SG16 and SG24 increments. The control is the newly promoted DP4A2×SG24
build. Model, Q8 values, integer dot product, per-block FP32 boundary, equal
TP2, F16 KV, FlashAttention, `b1024/ub256`, and all runtime doors remain fixed.

The first gate is a fresh-process, position-balanced direct benchmark. A
candidate must be safe, output-exact, and repeatably faster before any endpoint
or semantic suite. Other hosts should not duplicate this exact interaction
while the claim is active.
