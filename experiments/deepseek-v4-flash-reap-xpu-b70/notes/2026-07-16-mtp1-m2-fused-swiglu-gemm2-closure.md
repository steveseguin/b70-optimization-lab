# MTP1 M=2 fused SwiGLU/GEMM2 closure

Date: 2026-07-16

## Outcome

The fixed-M2 Xe2 kernel that consumes the grouped GEMM1 gate/up output,
applies the exact clamped SwiGLU contract inside the GEMM2 A loader, and then
executes MXFP4 GEMM2 is bitwise correct but decisively slower. It is preserved
as an experiment and must not be integrated or service-tested.

The frozen model, TP4+EP topology, MTP1 policy, FP8 KV cache, and quantization
did not change. The verified one-session decode record remains
`63.349927998683015 tok/s`; no LocalMaxxing submission was made.

## Correctness

Card 0 passed all `84/84` changed-input cases bitwise exactly. The probe checks
the real chain

`remap -> GEMM1 -> clamped SwiGLU -> GEMM2 -> gather`

against route-mapped fixed-M1 GEMM1/GEMM2 oracles and validates the final
weighted gather. The fused loader explicitly reproduces BF16 rounding of the
gate and up values, BF16 SiLU rounding, and BF16 product rounding.

## Performance

| Route pattern | Projected saving / 43 layers |
|---|---:|
| same typical | -2.5380 ms |
| disjoint typical | -6.1431 ms |
| cross-row overlap | -2.6227 ms |
| within-row duplicate | -2.3844 ms |
| all duplicate | -2.7912 ms |
| six local | -9.1332 ms |
| all remote | 0.4870 ms |

The frozen integration requirement is at least `+0.50 ms` on every valid
route. The candidate's minimum is `-9.1332 ms`, so it fails by a wide margin.
The all-remote row only measures the removed empty activation launch and also
misses the gate on this run.

## Why it failed

The activation was fused at the wrong side of the producer/consumer boundary.
The GEMM2 grid has many output-N tiles. Every tile loads the same activation A
fragment, so applying SwiGLU in that loader recomputes the same 2048-element
activation for each output tile instead of computing it once per route row.
Removing one launch and one temporary cannot repay that duplicated work.

This result rules out GEMM2 A-loader activation fusion for this tiling. A
future attempt must produce each activated value once, most plausibly by
pairing gate and up columns in the GEMM1 epilogue, or change the GEMM2 grid so
the activated A row can be shared without serializing its output-N work.

## Preserved implementation and evidence

- XPU branch: `codex/deepseek-v4-m2-fused-swiglu-gemm2`
- signed XPU commit: `cfb0155`
- new grouped-GEMM library SHA-256: `4b67d34a778e7e61ddcd2fead7957c015507269234796c0bd72fc96541f2b8f8`
- raw result: `data/deepseek-v4-reap-mxfp4-m2-fused-swiglu-gemm2-20260716/card0.json`
- probe: `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/probe-mxfp4-m2-compact-scheduler.py`

The ordinary GEMM implementation remains isolated from the fused template so
the control was not narrowed or burdened by fused state. Ordinary M1/M2
compact paths retain their int32/int64 route-index contracts; the experimental
fused op is explicitly int32-only.

## Related upper bound

Deleting only direct remap was also unstable at the frozen floor. Two exact
card-0 runs projected `0.50023792 ms` and `0.47740836 ms` minimum saving over
43 layers. That is useful iteration evidence, but not a robust integration
case. Raw results are under
`data/deepseek-v4-reap-mxfp4-m2-source-direct-gemm1-20260716/`.

## Next boundary

Do not repeat activation in the GEMM2 A loader. Audit a paired gate/up GEMM1
epilogue that emits the already activated `[route, 2048]` tensor once and
removes the standalone activation launch plus the `[route, 4096]` gate/up
temporary. It must first demonstrate that gate/up column pairs can be owned by
one workgroup without sacrificing the N-dimension parallelism that makes the
current GEMM fast. The same 84-case exact oracle and `0.50 ms` worst-route gate
remain mandatory before four-card or service testing.
