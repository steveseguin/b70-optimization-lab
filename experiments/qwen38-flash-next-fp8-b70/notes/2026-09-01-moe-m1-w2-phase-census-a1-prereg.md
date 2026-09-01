# Qwen3.8 Flash-Next FP8 M1 MoE w2 phase census A1

Date: 2026-09-01
Status: frozen before component execution

The common-config A2 census retained warps 8, but it could not tell whether a
candidate helped the gate/up GEMM and hurt the down GEMM or vice versa. The
two phases have materially different shapes: w13 is approximately
`[128,1280,2560]`, while w2 is `[128,2560,640]`.

vLLM `cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9` adds a dormant, opt-in modular
Triton path for independent w13/w2 static configs. It preserves the historical
flat config for every other device, dtype, batch size, and caller. Phase deltas
are restricted to XPU M1 block-FP8, cannot alter the shared M tile or split-K,
are chosen before graph capture, and have 11 focused CPU tests.

This arm retains common warps 8 as its control and changes only w2 across six
source-informed candidates: warps 4; N32 with warps 4/8; N128 with warps 4/8;
and K64 with warps 8. It uses the modular production path, real layer-0 rank-0
weights, the same seed/routing/shape as the A2 census, fresh processes, control
bracketing, three output repeats, and nine timing batches of 100 calls.

Only byte-exact candidates at least 3% faster than the common warps-8 bracket
may advance. A component winner cannot change a protected model result; w1
screening and full TP4 qualification remain separate later gates.

Patch SHA-256:
`ad820bad443bba32f15b114ea76b4deb4dade754fe1bc362faddfef07eb6c519`.
Component-gate SHA-256:
`d0485a8f3f40c3312a439d8970cd7ab47bbfa597ab537c932dfc2f6566ddd94a`.
Runner SHA-256:
`46bea369b2e724e50556f61d28332b3c2c273cbc2c26454bc1ab81ed5e5c7403`.
