# Qwen3.8 AutoRound INT4 cross-process M-sweep D1 preregistration

Date: 2026-08-31

Status: **preregistered before D1 operator calls**

## Question

R8 proved current compiled nondeterminism on TP1, while the earlier raw
production-shape cross-process screen covered only M=65. Are the target
backbone's production INT4 GEMMs bitwise repeatable across fresh processes at
M=1 decode and every actual strict-suite prefill row count?

## Frozen diagnostic

- exact image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU 0; four fresh containers; fixed seed 20260830;
- eight production INT4 shapes covering GDN, MLP, and attention TP2 dimensions;
- M values `1,48,49,52,53,55,56,57,59,65,71,75,78`;
- two identical calls per shape/M inside each process, plus SHA-256 equality
  across all four processes.

Pass requires within-process exactness everywhere and exactly one hash per
shape/M across processes. Any mismatch is a positive causal finding and must
identify its exact shape and M. A full pass is negative evidence only; it does
not authorize model speed or correctness promotion.
