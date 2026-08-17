# Qwen3.8 27B Q8 TP2 DP4A2 × SG24 synergy

Date: 2026-08-17

Status: active; claimed on the reference ASRock host

The original Qwen3.8 DP4A2 transfer was quality-exact but did not beat the
one-chain endpoint under the then-current hardware-derived SG8 recurrent-quad
workgroup. Promoted SG24 changes that quad's occupancy from 128 to 384 work
items. Because the two-chain DP4A schedule changes instruction-level
parallelism and register pressure, its interaction with SG24 is materially
different from the closed unchanged transfer.

The candidate combines the exact retained Qwen3.6 DP4A2 source with the
promoted Qwen3.8 SG16 and SG24 increments. The control is the clean promoted
one-chain SG24 build. Model, Q8 layout, per-block integer value, FP32
scale/accumulation boundary, equal TP2, F16 KV, FlashAttention, and
`b1024/ub256` remain fixed. A TP2 smoke must announce SG24 on both devices and
end at `VERIFY_MISMATCH=0`.

Separate AOT binaries are unavoidable because DP4A2 is a compile-time row
body. The screen will use exact complementary binary positions and fresh
processes. A candidate must produce a repeatable positive result before any
endpoint/semantic gate. Other hosts should not duplicate this exact synergy
arm while it is active.
