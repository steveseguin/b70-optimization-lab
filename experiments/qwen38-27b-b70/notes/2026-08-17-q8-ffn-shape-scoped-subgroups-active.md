# Qwen3.8 27B Q8 TP2 shape-scoped MMVQ subgroup count

Date: 2026-08-17

Status: active; claimed before implementation.

## Hypothesis

The accepted reordered-Q8 MMVQ uses eight SG16 subgroups per workgroup on
B70. A previous *global* launch-width sweep found SG4 statistically flat but
slightly positive (`+0.091%`) and SG16 slightly negative (`-0.045%`). That
global control changed every reordered MMVQ together, so it could hide a gain
in one dominant FFN family behind a regression in another.

Qwen3.8-27B repeatedly uses two dominant local TP2 FFN shapes:

- gate/up fused pair: K=`5120`, N=`8704+8704`;
- down projection: K=`8704`, N=`5120`.

This experiment independently selects SG4 for either exact family while all
other MMVQs retain the accepted hardware-derived SG8 geometry. It changes
launch population only: the accepted reordered weight layout, DP4A sequence,
FP32 accumulation and subgroup reduction, model, F16 KV, tensor split, and
target-only quality contract remain unchanged.

## Contract

- isolated source/build derived from the accepted Qwen3.8 Q8 stack;
- default-off same-binary doors for pair-only, down-only, and both;
- exact-shape admission plus once-per-device reachability logging;
- bounded `p64/n1` liveness/verification smoke under the established host-RAM
  cap;
- position-balanced `p64/n256/r3` screen with fresh processes;
- advance only a repeatable positive result outside run variance to the full
  cache-zero output oracle and semantic/long-context gates;
- preserve the accepted reproduction unless a candidate clears every gate.

The earlier global subgroup sweep and compile-time fixed-shape experiment are
controls, not duplicates: neither isolated subgroup population by FFN family.
