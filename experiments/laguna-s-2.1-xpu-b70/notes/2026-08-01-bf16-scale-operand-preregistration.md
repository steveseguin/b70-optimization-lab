# Laguna INT4 BF16 scale operand screen

Date: 2026-08-01 America/Toronto

Status: **preregistered; static ISA screen only.**

## Motivation

The protected exact BF16-KV record is `125.4619731637751 tok/s`. Reaching
130 at unchanged acceptance requires about 3.62% more throughput, or roughly
1.13 ms less verifier-cycle time. The target executes the INT4 W13 and W2
grouped GEMMs in every transformer layer, so the incumbent INT4 mainloop is
one of the few remaining components large enough to matter.

Checkpoint INT4 scales are stored as BF16. The incumbent loads each BF16 scale,
widens it exactly to FP32, retains the widened value in `scales[]`, and uses a
BF16-by-FP32 vISA multiply whose destination is BF16. This screen asks whether
retaining the original BF16 scale through that operation removes widening,
move, or register-allocation work without changing arithmetic.

## Frozen treatment

Start from protected kernel commit
`99886d783` in a fresh source worktree. Add a compile-time-only probe selector
which changes the scale register/operand representation from FP32 back to BF16
for the existing exact combination:

- `w4a16_policy_m_8`, group size 32;
- BF16 activations and scales, INT4 weights;
- `ScaleVec=true`, `DequantMad=false`, `TransposedScales=true`;
- BMG 128-GRF code generation;
- the same two SIMD16 BF16 multiply instructions and the same two DPAS
  instructions per unrolled K tile.

The treatment may change only scale storage and operand marshalling. It may not
fold scaling into FP32 accumulation, fuse away a BF16 rounding point, change
the quantization group, reinterpret the checkpoint, use fast math, or change
the DPAS inputs/order. The protected worktree and DSO remain untouched.

## Correctness premise

Converting a BF16 scale to FP32 is exact. Therefore, for the finite checkpoint
scales admitted by the production path, BF16 multiplication by the original
BF16 scale and BF16 multiplication by its exact FP32 widening have the same
real operands and the same BF16 destination rounding. Before any production
build, prove this with a host oracle over every signed INT4 dequantized input
value and every relevant BF16 scale bit pattern. Classify exceptional NaN,
infinity, signed-zero, and subnormal cases explicitly instead of assuming
them away.

## Gates and stop rules

1. Compile incumbent and treatment through the existing minimal IGC probe.
   Require exactly two DPAS instructions, 32 BF16 scale multiplies, no
   spill/scratch markers, and no topology change. The treatment must remove at
   least eight final BMG instructions or materially reduce allocated GRFs.
   Otherwise stop before a production extension build or GPU work.
2. If the static gate passes, build a separate default-off, fail-closed source
   selector in the fresh worktree. Inspect the exact diff and final ELF.
3. Run the deterministic changed-input component gate on one healthy B70 for
   W13 (`M=120,N=2048,K=3072`) and W2 (`M=120,N=3072,K=1024`). Require raw
   BF16 equality on every output and at least 3% improvement in the summed
   stable median using 200 warmups and 15 samples of 40 launches. A smaller
   result stops before model integration.
4. A component pass authorizes a separate endpoint preregistration only. It is
   not a throughput claim.

No target/draft/KV precision change, prompt or teacher change, warmed score,
retry selection, metric substitution, reset, reboot, driver reload, or other
recovery action is authorized by this screen.
