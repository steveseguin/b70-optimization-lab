# Laguna M12 grouped-GEMM K-loop barrier screen

Date: 2026-08-01 America/Toronto

Status: **preregistered before source implementation or device execution. No
endpoint score is authorized.**

## Evidence and hypothesis

The protected exact BF16-KV record is `125.4619731637751 tok/s`
conventionally. Its aggregate evidence implies about `32.327 ms` per verifier
cycle; reaching 130 at unchanged acceptance requires approximately
`1.128 ms/cycle` of real saving.

The exact M12 target runs one grouped INT4 W13
(`M=120,N=2048,K=3072`) and one W2 (`M=120,N=3072,K=1024`) in each of 48
layers. The protected transposed-scale GRF128 component is about `0.50 ms` per
W13+W2 layer pair. Its K32 mainloop executes a workgroup
`barrier_arrive`/`barrier_wait` pair around every K tile: 96 pairs in W13 and
32 in W2.

Every subgroup owns its A, B, scale, and accumulator fragments in registers.
The loop performs no SLM access or cross-subgroup reduction. After the complete
GEMM returns, the grouped scheduler already has a separate local-memory
workgroup barrier before assigning the next output tile. The hypothesis is
that the per-K-tile barrier pairs are inherited general synchronization rather
than a dependency of this exact register-only path.

## Frozen treatment

In a fresh XPU-kernel worktree from protected commit
`99886d783372e621941228250091dc8ebdc1595d`:

1. Add a compile-time mainloop switch that omits only the per-K-tile
   `barrier_arrive` and `barrier_wait` calls.
2. Expose it through one default-off selector with a separately named kernel.
3. Require the complete protected route: BF16 activations/scales/output,
   packed signed INT4, ordinary non-tile-major weights, group 32, total routed
   rows 120, `w4a16_policy_m_8`, GRF128, scale vectorization, physically
   transposed scales, non-MAD, and non-folded scaling.
4. Keep the post-GEMM grouped-scheduler SLM barrier unchanged. Arithmetic,
   loads, prefetch distance, scale values, dequantization, DPAS order,
   accumulation, output store, workgroup count, and scheduler order remain
   unchanged.

Selector off must preserve the protected source path. Prefill, draft, other M,
other dtypes/layouts/group sizes/policies, and every M8 fused-expert path are
out of scope.

## Gates and stop rules

1. **Static BMG gate.** Build with the record-compatible oneAPI 2025.3 ABI.
   Require the same DPAS count and order, no scratch/spill markers, unchanged
   GRF128 allocation, removal of the per-K barrier instructions, and no new
   arithmetic or memory operation. Stop on any static ambiguity.
2. **Changed-input component gate.** Use one healthy B70 and the established
   physical-transposed-scale corpus for W13 and W2. Compare selector off and on
   from the same candidate DSO. Require `6/6` raw-BF16 equality, 200 warmups per
   shape, 15 samples of 40 launches, no shape regression greater than 1%, and
   at least `3.0%` improvement in the summed stable W13+W2 median. A smaller
   result stops before model integration.
3. **Portfolio accounting.** A component pass may be combined in a separately
   preregistered endpoint portfolio with the previously measured independent
   exact M12 router component (`~0.499 ms/cycle`) only after source/dataflow
   overlap is ruled out. The component result alone authorizes no endpoint.
4. **Endpoint safety.** Any later smoke must retain the protected model and
   draft revisions, BF16 KV, width 12/depth 11, canonical q1 teacher, fixed
   prompt construction, cache-zero policy, one active generation, 146/145
   target and 14/13 draft topology, four-rank selector evidence, and clean
   teardown. A score requires a separate first-result cold preregistration.

No target/draft/KV precision change, teacher change, prompt change, retry,
warmup generation, metric substitution, reboot, reset, driver operation, or
privileged recovery is authorized by this screen. Preserve all failed source,
binary, ISA, and component evidence.
