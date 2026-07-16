# MTP1 M=2 remap and paired GEMM1/SwiGLU closure

Date: 2026-07-16

## Outcome

Two bounded attempts to widen the exact M=2 route-direct boundary are closed
before four-card or service integration:

1. A single-workgroup fixed-M2 remap, including an SLM-premapped variant, is
   exact but remains below the frozen `0.50 ms/43 layers` every-route gate.
2. A paired gate/up GEMM1 producer that performs the exact clamped SwiGLU
   epilogue once is bitwise correct, but its dual B payload and dual FP32
   accumulators reduce local-route throughput. Restricting it from 256 to 128
   GRFs does not repair the architecture.

The frozen model, TP4+EP topology, MTP1 policy, FP8 KV cache, and quantization
did not change. The verified one-session decode record remains
`63.349927998683015 tok/s`, LocalMaxxing `cmrncv39w003ylg01hogleazo`. No
service was loaded and no LocalMaxxing submission was made.

## Fixed-remap variants

Both implementations pass `84/84` changed-input cases bitwise exactly. The
fail-closed minimum is the valid all-remote route in every run.

| Variant | Run | Minimum saving / 43 layers |
|---|---:|---:|
| one workgroup, 512 threads | 1 | 0.410910 ms |
| one workgroup, 512 threads | 2 | 0.429536 ms |
| one workgroup with direct routes premapped in SLM | 1 | 0.403240 ms |
| one workgroup with direct routes premapped in SLM | 2 | 0.415113 ms |

The SLM premapping improves some local patterns, but the all-remote boundary
still measures launch/scheduling cost and does not clear the gate. This closes
further standalone remap tuning. Preserved signed XPU commits are `33e3ce4`
and `5ea7608`.

## Paired GEMM1 producer

The new fixed-M2 kernel launches 12 route lanes by 32 paired N tiles. Each
workgroup loads the activation once, computes matching 64-column gate and up
tiles from the two packed weight halves, rounds both ordinary GEMM outputs to
BF16, and then reproduces the existing BF16 clamp, SiLU, multiply, and store
contract into `[12,2048]`. The existing compact GEMM2 and generic gather remain
unchanged.

An independent source audit found the packed weight/scale offsets, CUTE
fragment pairing, BF16 rounding points, duplicate-route scheduling, barriers,
bias handling, and bindings coherent. Both compiled variants pass all `84/84`
changed-input cases bitwise exactly, including overlap, duplicates, six-local,
all-remote, bias-present, and bias-null cases.

Performance nevertheless fails decisively:

| Route | GRF256 saving / 43 layers | GRF128 saving / 43 layers |
|---|---:|---:|
| same typical | -1.925934 ms | -0.361360 ms |
| disjoint typical | -0.679051 ms | 0.511083 ms |
| cross-row overlap | -1.911892 ms | 0.040718 ms |
| within-row duplicate | -1.463149 ms | 0.037632 ms |
| all duplicate | -2.044084 ms | -0.295756 ms |
| six local | -2.655429 ms | -4.501538 ms |
| all remote | 0.520384 ms | 0.494581 ms |

GRF128 recovers sparse disjoint and overlap cases, proving register occupancy
was part of the loss, but it makes the dense six-local case still worse. The
paired kernel produced no compiler spill warning; the failure is its live
dual-payload/dual-accumulator working set and occupancy, not hidden scratch
spilling. The all-remote row contains no paired arithmetic and continues to
measure only the deleted activation boundary.

Preserved experiment source:

- XPU branch: `codex/deepseek-v4-m2-paired-gemm1-gather-add`
- signed XPU commit: `c069ed8`
- GRF256 grouped-GEMM SHA-256:
  `1f271f6b0a58d4efefc289357dc6b5240053a484abc90beb0058db8698f28889`
- GRF128 grouped-GEMM SHA-256:
  `cfe6ed10181d62cce6fa41d8ed6a3de40b51363a3d74c5510eee88cc7a127ec1`
- probe:
  `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/probe-mxfp4-m2-compact-scheduler.py`

Raw results are under:

- `data/deepseek-v4-reap-mxfp4-m2-remap-wg512-20260716/`
- `data/deepseek-v4-reap-mxfp4-m2-remap-wg512-premap-20260716/`
- `data/deepseek-v4-reap-mxfp4-m2-paired-gemm1-swiglu-20260716/`
- `data/deepseek-v4-reap-mxfp4-m2-paired-gemm1-swiglu-grf128-20260716/`

## Decision and next boundary

Do not integrate the dual-accumulator paired producer or spend a service load
on it. Do not revisit standalone remap tuning.

The next producer attempt must reduce live register state: assign gate and up
halves to separate subgroups, round their ordinary GEMM outputs to BF16, and
exchange the paired fragments through a small workgroup-local buffer before
one side applies the exact activation. Gate it on the same 84-case oracle and
the same every-route `0.50 ms` minimum. If subgroup/SLM coordination consumes
the projected launch saving, close producer fusion and widen the already exact
route-direct path by fusing generic gather with the following shared-expert
BF16 addition; that package has the next measured ceiling above the gate.

## Runtime invocation note

The frozen extensions require the 2025.3 SYCL library while current oneAPI
`setvars.sh` supplies UMF and the rest of the runtime paths. Source the normal
oneAPI environment, prepend `/opt/intel/oneapi/compiler/2025.3/lib` to
`LD_LIBRARY_PATH`, and use `ZE_AFFINITY_MASK` for single-card probes. Sourcing
only the compiler-specific vars omits `libumf.so.1` and falsely reports zero
SYCL platforms; that is an environment error, not a device failure.
