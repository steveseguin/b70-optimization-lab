# Qwen3.8 Flash-Next FP8 M4 MoE warps-8 component positive

Date: 2026-08-30
Status: lossless M4 component win; not the current M1 decode endpoint shape

The repaired component gate measures an M4 local MoE shape
with real layer-0 rank-0 FP8 weights, 512-global/128-local EP4 mapping,
deterministic balanced global routing, nonzero outputs, XPU events, and only one
host copy/hash after each timing phase. The active decode-like M4 shape uses 11
local valid routes in this deterministic fixture.

Changing only `num_warps` from 4 to 8 retained exact output bytes for 100/100
repeats on each of two hidden-state seeds. Median component latency changed:

- seed 20260826: 600.070 to 473.198 us, a 21.14% reduction;
- seed 20260827: default bracket 593.219 / 593.841 us versus 473.609 us,
  a 20.20% reduction against the bracket mean.

The exact user-folder configuration was selected under the production filename
and reproduced the seed-20260827 authority hash. Other map entries explicitly
retain the current defaults so the M4 candidate does not silently retune M1,
M8, M16, M32, M64, or M128.

The faster combined `BLOCK_SIZE_K=64,num_warps=8` arm was rejected: although it
reached 506.448 us in one bracket, it changed low-order output bytes on the
second seed. It remains diagnostic and cannot enter a lossless endpoint arm.
`BLOCK_SIZE_N=32` was slower; `BLOCK_SIZE_N=128` exceeded the bounded compile
screen; stage-only changes were neutral. No source or protected endpoint result
was changed.

A28 later proved that the current single-sequence production decode routed
kernel uses M1, not M4. With DP=PCP=SP=1 there is no per-layer token all-gather,
and config selection uses the one-row hidden-state input. A27 consequently
loaded this map but retained its unchanged M1 entry; it did not test the M4
treatment. The 5.8--6.1 ms projection is therefore not applicable to the
current endpoint. Preserve this valid M4 component result for M4 workloads,
but repeat the real-weight lossless screen at M1 and require a receipt of the
effective selected key before any new endpoint arm.

Structured result:
[`20260830-moe-m4-warps8-component-positive.json`](../data/20260830-moe-m4-warps8-component-positive.json)
