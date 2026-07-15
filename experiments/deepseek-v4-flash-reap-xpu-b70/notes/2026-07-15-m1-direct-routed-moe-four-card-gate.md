# M=1 direct routed-MoE four-card gate

Date: 2026-07-15

## Decision

Proceed to a default-off TP4 server candidate. The exact slot-direct routed-MoE
chain clears the required `0.50 ms/token` projected integration gate on all four
B70s.

The candidate replaces the M=1 generic sequence

1. rows-per-expert zeroing and hidden-state remap;
2. persistent grouped MXFP4 GEMM1;
3. two BF16 clamp launches and SiLU/multiply;
4. persistent grouped MXFP4 GEMM2; and
5. permuted gather

with four operations that retain the existing Xe2 DPAS arithmetic:

1. slot-direct GEMM1 using the six global top-k IDs;
2. exact clamp-at-10 plus SiLU/multiply;
3. slot-direct GEMM2; and
4. slot-order weighted gather.

The route remains in original global top-k slot order. Remote slots exit before
weight reads and are ignored by the gather. The guarded production path is
enabled only by `VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1`; M>1 continues through the
existing path, while an unsupported M=1 contract fails closed.

## Correctness

Each EP rank passed 40/40 changed-input XPU graph epochs. The gate compares, for
every local slot, the clamped GEMM1 row, activation row, and GEMM2 row, then the
final BF16 weighted gather. It also checks A-B-A replay stability.

Cases include all-local, all-remote, mixed and shuffled EP placement, boundary
expert IDs, zero and nonuniform weights, and duplicate expert IDs. Duplicate
coverage matters because about 2% of rows in the three real K160 hash tables
contain repeated selected experts; the generic M=2 row and two direct M=1 slots
remain bitwise identical.

The operator contracts were hardened before the gate:

- production E8M0 scales may be stored as raw `uint8` or
  `float8_e8m0fnu`, with identical bytes and no conversion;
- partial N tiles are rejected because the reused mainloop is unpredicated;
- GEMM and gather validate devices, expert-map bounds, and local IDs; and
- the fused activation validates XPU placement and exact tensor shapes.

The complete Python integration also passed 20/20 changing eager cases and
20/20 changed graph replays against `XpuFusedMoe.apply` on GPU 0.

## Performance

The primary timing case uses three local experts, the most common critical-rank
occupancy in the real hash-table audit. It uses production N64, BF16
activations, raw E8M0 bytes sampled from the real 119-122 range, int32 routes,
weights scaled to 1.5, alternating reference/candidate order, 40 warmups, nine
samples, and 200 graph replays/sample.

| EP rank | Reference us/layer | Direct us/layer | Saved us/layer | Projected ms/token (43 layers) |
|---:|---:|---:|---:|---:|
| 0 | 130.158 | 105.530 | 24.628 | 1.059 |
| 1 | 130.415 | 107.026 | 23.390 | 1.006 |
| 2 | 130.862 | 106.551 | 24.310 | 1.045 |
| 3 | 130.862 | 107.081 | 23.781 | 1.023 |

All tested occupancies clear the gate. Across ranks, the projected ranges are:

- two local experts: 1.093-1.186 ms/token;
- three local experts: 1.006-1.059 ms/token;
- four local experts: 0.928-0.961 ms/token; and
- six local experts: 1.215-1.296 ms/token.

The separately qualified exact router-normalization component projects another
0.161-0.174 ms/token across the 40 normal layers. It is now integrated behind
`VLLM_XPU_V4_M1_ROUTER_NORM=1`; hash routing is unchanged.

## Identity and evidence

- XPU kernels implementation: `497926b`
- XPU kernels guarded integration: `6522849`
- vLLM router integration: `a681dbb2b`
- `_xpu_C.abi3.so` SHA-256:
  `3d07d85ce15a418d4355b0eaf5686c9cf6c7af92c9d5bf15b3884e9758161bf2`
- `libgrouped_gemm_xe_2.so` SHA-256:
  `d6b1e93b43a137e56c72660af3138526324735f10a3ab8ea5f02a9b11d79a435`
- `_C.abi3.so` SHA-256:
  `81ad1a12bf3c4ab6e8b14974d591b9b8cdde871f03f1da0c4cf7524e4429cb9f`
- `_moe_C.abi3.so` SHA-256:
  `a94209c5e51a3e226b11502549a4d6ffef025927119f8dc1651d4cb75237ab73`
- benchmark:
  `scripts/bench-m1-direct-routed-moe.py`
- structured results:
  `data/m1-direct-routed-moe-gpu{0,1,2,3}-gate-20260715.json`

## Next gate

Load a separate graph/cache identity with both new flags enabled. Require 20/20
deterministic exact canaries and compare two strict cached-zero suites against a
same-commit flag-off control. At the 41.733 tok/s nonspeculative record, a real
0.50 ms/token saving predicts about 42.62 tok/s; the microgate predicts more,
but only the full model can show how much is absorbed by shared-expert work and
TP synchronization.
