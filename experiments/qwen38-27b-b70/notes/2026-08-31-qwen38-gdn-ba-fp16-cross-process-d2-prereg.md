# Qwen3.8 GDN B/A FP16 cross-process D2 preregistration

Date: 2026-08-31

Status: **preregistered before D2 operator calls**

## Question

R9 proved eager TP1 nondeterminism. The current overlay, unlike the official
image, forces every strict-suite GDN B/A prefill projection through a 256-row
padded FP16 `F.linear`. Is that exact treatment bitwise stable across fresh
processes at all real prompt sizes?

## Frozen diagnostic

- current deterministic image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU 0; eight fresh containers; fixed seed 20260831;
- K=5120, N=96 (TP1) and N=48 (TP2), M values
  `48,49,52,53,55,56,57,59,65,71,75,78`;
- exact overlay treatment: zero-pad M to 256, run FP16 `F.linear`, slice real
  rows; also run the direct unpadded operation as a control;
- two identical calls per operation inside each process and SHA-256 comparison
  across all eight processes.

Pass requires bitwise within-process and cross-process equality for both modes
at all 24 shape/M cases. Padded-versus-direct equality is recorded separately;
it is not required for determinism but determines whether the overlay changes
the numerical result. This is an operator diagnostic only, never a speed or
quality promotion.
