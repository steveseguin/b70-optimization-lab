# MTP1 M=2 route-direct boundary closure

Date: 2026-07-16

## Outcome

The fixed-M2 route-direct boundary is exact, and its best variant improves the
complete per-layer routed chain for every declared route pattern, but it does
not clear the predeclared `0.50 ms` minimum projected saving over 43 routed
layers. It is therefore not integrated into vLLM or loaded into the TP4
service.

The frozen model, TP4+EP topology, MTP1 policy, FP8 KV cache, quantization, and
record benchmark identity did not change. The verified one-session decode
record remains `63.349927998683015 tok/s`; no LocalMaxxing submission was made.

## Benchmark correction

An independent audit found that the first route-direct extension of the probe
had placed GEMM2 after gather, so the timed graph did not execute the intended
chain. The data under
`data/deepseek-v4-reap-mxfp4-m2-route-direct-upper-bound-20260716/` and
`data/deepseek-v4-reap-mxfp4-m2-route-direct-implementation-20260716/` are
preserved as invalid experiment artifacts and must not be used for performance
claims.

The corrected gate executes:

`remap -> GEMM1 -> clamped SwiGLU -> GEMM2 -> gather`

It uses the real GEMM1 output as GEMM2 input, pins the compact scheduler lane
count in the result, and compares each route through the generic and candidate
row maps against an independent fixed-M1 oracle. It also validates the final
weighted gather. Every corrected candidate below passed all 84 changed-input
cases bitwise exactly.

## Corrected card-0 results

| Candidate | Minimum projected saving / 43 layers | Decision |
|---|---:|---|
| 4-lane sequential compact GEMMs + direct gather | -2.6445 ms | reject |
| 12-lane compact GEMMs + direct gather | 0.3907 ms | reject |
| 12-lane compact GEMMs + generic activation/gather | 0.4139 ms | best base, below gate |
| routed activation, 2 lanes | 0.0065 ms | reject |
| routed activation, 4 lanes | 0.2326 ms | reject |
| routed activation, 12 lanes, route rescans | 0.4186 ms | reject |
| routed activation, 12 lanes, precomputed-map broadcast | 0.4236 ms | reject |

The best base saves `0.5460-0.9418 ms` on every route pattern with local work
but only `0.4139 ms` for the valid all-remote EP case. The precomputed-map
activation improves the all-remote case only to `0.4236 ms` and makes the
six-local case the other near miss at `0.4841 ms`.

The direct gather is slower than the existing generic gather. Reducing the
compact GEMM scheduler to four persistent route lanes destroys parallelism on
overlap and duplicate routes. Reducing activation route lanes similarly
serializes useful work. Reusing the direct-remap row map removes redundant
activation mapping work, but the extra specialized activation still does not
remove a launch boundary.

## Preserved implementation

The benchmark-only source is on XPU branch
`codex/deepseek-v4-m2-route-direct`, signed commit
`3aa2181` (parent compact-scheduler commit `ae1cbd4`). It contains:

- fixed M=2/top-k-6 direct remap;
- fixed M=2 direct gather;
- optional four-lane sequential compact GEMM scheduler;
- route-aware clamped SwiGLU variants.

These are experiment artifacts, not production dispatch. No fake/meta
registration or vLLM production guard was added.

Corrected raw evidence is under
`data/deepseek-v4-reap-mxfp4-m2-route-direct-corrected-20260716/` and the probe
is `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/probe-mxfp4-m2-compact-scheduler.py`.

## Next boundary

Do not service-test this patch as-is. The next fusion with enough ceiling must
remove a launch, not merely make one padded-row kernel smaller. The leading
candidate is a source-direct GEMM1 scheduler that reads the two token rows
directly, emits the route map from its first N tile, and thereby removes the
standalone remap launch while preserving expert-grouped GEMM1 output for the
existing activation, compact GEMM2, and generic gather.

It must retain exact handling of cross-token expert overlap and duplicate
routes, pass the same 84-case oracle, and clear the same `0.50 ms` minimum gate
before any four-card or service work.
