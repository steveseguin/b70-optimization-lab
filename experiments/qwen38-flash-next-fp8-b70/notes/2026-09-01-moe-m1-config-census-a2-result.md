# Qwen3.8 Flash-Next FP8 M1 MoE census A2 result

Date: 2026-09-01
Status: complete; warps-8 leader retained; phase-specific tuning authorized

A2 completed nine fresh one-B70 real-weight processes in roughly 90 seconds.
Both controls and all seven candidates produced the same exact output hash.
The control bracket was `449.30418 us`; the existing warps-8 treatment remained
the leader at `407.06172 us`, a `9.401751%` reduction.

M32/warps8, K64/warps8, and N32/warps8 were close followers at
`8.90%`, `8.89%`, and `8.84%`, so none justifies replacing the existing common
configuration. N128/warps4 was a decisive `143.66%` regression and is closed.

The screen therefore did its intended job: it rejected six plausible common
configurations without loading the full model. Because the two Triton GEMMs
currently share one config despite different matrix shapes, the next bounded
arm may tune w13 and w2 independently. It must use the modular production path,
real weights, exact hashes, and a fresh process per candidate. No protected
model result changes.

Structured result:
[`20260901-moe-m1-config-census-a2.json`](../data/20260901-moe-m1-config-census-a2.json).
