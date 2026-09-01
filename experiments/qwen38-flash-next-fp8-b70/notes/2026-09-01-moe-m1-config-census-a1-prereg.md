# Qwen3.8 Flash-Next FP8 M1 MoE configuration census A1

Date: 2026-09-01
Status: frozen before component execution

## Purpose

Full TP4 model loads are too expensive for first-pass kernel selection. A28
attributes `26.0844 ms/token` to routed/shared MoE, the largest measured
target-decode bucket. This component arm replays the exact layer-0, EP-rank-0,
M1 FP8 expert shape with real checkpoint weights on one B70 and screens only
source-informed Triton dimensions.

## Frozen funnel

- official `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` from local NVMe;
- vLLM `797769b34b6db5c934609b75dc04cc61ec66e5f9` and the accepted staged
  XPU runtime;
- one B70, layer 0, EP rank 0, M1, 512 global/128 local experts, top-k 10,
  hidden 2,560, intermediate 640, block scale 128x128;
- hidden seed `20260827`, balanced-global routing, five warmups, nine timing
  batches of 100 invocations, and three exact-output repeats per fresh process;
- default controls bracket the screen;
- candidates are warps 8; N tiles 32/128 with warps 4/8; K tile 64 with
  warps 8; and M tile 32 with warps 8.
- frozen runner SHA-256:
  `a96a05249cf82c748441f75f9856dca9f8689d23a43d8d4a0cdac0aed9aa898f`.

`SPLIT_K` is excluded because this runtime forcibly resolves it to 1. K=256 is
excluded because block scaling clamps it to 128. Stages 2/3/5 are excluded
because the existing stage screen was neutral and its decision is closed.
Interactions are not screened unless one of their constituents first wins.

A candidate advances to the three-seed confirmation gate only if it is byte
exact to both controls and reduces the control-bracket mean by at least 3%.
This arm cannot change a protected model result or authorize deployment. Full
TP4 qualification remains deferred until multiple component winners have been
combined.
