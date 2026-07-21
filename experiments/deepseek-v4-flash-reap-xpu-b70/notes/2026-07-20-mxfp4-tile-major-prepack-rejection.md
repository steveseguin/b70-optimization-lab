# MXFP4 K32xN64 tile-major prepack: exact on three cards, rejected

Date: 2026-07-20

## Numbers first

**Verdict: FAIL. Keep the selector off. Do not use this layout in a promoted
recipe.**

- Four-card exact gate: **FAIL**. Cards 1, 2, and 3 passed **120/120**
  changed-input eager comparisons and **210/210** fixed-address graph replays in
  aggregate, including positions 28 and 58 on every card. Physical card 0
  passed a small pre-screen, then reproducibly hit
  `UR_RESULT_ERROR_DEVICE_LOST` at the fourth changed-input schedule before its
  full gate could complete.
- Candidate slowest-bandwidth route on completed card 3, 2-local:
  **369.379 -> 260.713 GB/s**, **-1.297 ms/token saved** (a regression).
- Representative card-3 3-local route: **414.917 -> 277.035 GB/s**,
  **-2.069 ms/token saved**. Applying that ratio to the in-model 288.7 GB/s
  profile gives approximately **192.775 GB/s**, not the 370--410 GB/s target.
- Conservative worst valid route among completed measurements, card 1
  6-local: **444.852 -> 291.029 GB/s**, **-4.098 ms/token saved**.
- The required exact-speed gate was `>= 0.50 ms/token`; the result is a clear
  **FAIL**. A nonspec B-A-B was therefore not run, and there is no implied new
  nonspec throughput number versus 43.77 tok/s.
- Nothing was submitted to LocalMaxxing.

## What was built

The default-off selector is:

```text
VLLM_XPU_MXFP4_TILE_MAJOR_PREPACK=1
```

When enabled, the load-time converter replaces the old independent tensors
with one allocation containing 1,088-byte records in this order:

```text
[expert, n_tile, k_group,
  1024-byte raw MXFP4 weight tile (N64 x K32/2),
  64-byte raw E8M0 scale sidecar]
```

The weight and scale tensor views alias that allocation; there is no persistent
duplicate packed weight copy. The matching reader specializes the grouped GEMM
for N64 under the selector. With the selector unset, the existing layout and
reader remain unchanged.

This was a layout-only experiment. The candidate retains the same CUTE B
fragment, 4-bit unpack, raw E8M0 `byte << 23` scale reconstruction, BF16 scale
application, ascending K32 `cute::gemm` calls into the FP32 accumulator, and
BF16 store. No K160 target identity, revision, or quantization changed.

## Source and binary identity

- vLLM source commit:
  `e4af6e380dc1be771a8695720e688ff12af5169d`
- XPU-kernels source commit:
  `f370fca23f1d43d5b184f21ea90b893fde46517d`
- Rebuilt `build/temp/libgrouped_gemm_xe_2.so` SHA-256:
  `3d0823b5a4b35ad8396f4d80edfb02db6cf79f28208ccbf26c2842f0d07dcb1e`
- Unchanged `build/temp/_xpu_C.abi3.so` SHA-256:
  `d62ea1cf4728250809052c68fdd74983b4f2c0dcaf924624e7a507c8d4c8392f`
- Model: `0xSero/DeepSeek-V4-Flash-180B`
- Revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`
- Quantization: MXFP4, K160 target fixed.

Tracked patch snapshots:

- `patches/deepseek-v4-flash-xpu-b70/20260720-mxfp4-tile-major-prepack-xpu.patch`
- `patches/deepseek-v4-flash-xpu-b70/20260720-mxfp4-tile-major-prepack-vllm.patch`

## Exactness gate

The harness compares the old and candidate layouts after GEMM1, clamped
activation, GEMM2, and final BF16 output. It uses independent changed-input
eager schedules followed by fixed-address graph replays. The completed cards
were bitwise identical at every compared surface:

| Physical B70 | Changed-input eager | Fixed-address graph | Positions 28/58 | Result |
|---|---:|---:|---|---|
| 0 | 3/3 pre-screen | 2/2 initial smoke | not reached in full gate | device lost; unqualified |
| 1 | 40/40 | 70/70 | pass/pass | exact |
| 2 | 40/40 | 70/70 | pass/pass | exact |
| 3 | 40/40 | 70/70 | pass/pass | exact |

Card 0 failed at the fourth full-gate eager schedule in the concurrent run. It
failed at the same point in an isolated retry and also hung when assigned
logical EP rank 3. Simple XPU compute recovered between attempts, so this was
not an initially busy-GPU condition. Further device stress was stopped; no
reset, reboot, or live service/model load was attempted. Consequently, exact by
construction is supported on all completed comparisons, but the mandatory
four-card gate did not pass.

## Bandwidth and latency

Each completed timing used 40 warmups and nine alternating baseline/candidate
samples, with 200 fixed-address graph replays per sample.

| Card | EP route | Baseline GB/s | Candidate GB/s | Saved ms/token |
|---:|---:|---:|---:|---:|
| 1 | 2-local | 369.215 | 260.814 | -1.294 |
| 1 | 3-local | 414.858 | 277.175 | -2.065 |
| 1 | 4-local | 435.946 | 344.611 | -1.398 |
| 1 | 6-local | 444.852 | 291.029 | -4.098 |
| 2 | 2-local | 369.462 | 260.808 | -1.296 |
| 2 | 3-local | 415.094 | 277.045 | -2.070 |
| 2 | 4-local | 436.019 | 346.878 | -1.355 |
| 2 | 6-local | 446.707 | 293.346 | -4.037 |
| 3 | 2-local | 369.379 | 260.713 | -1.297 |
| 3 | 3-local | 414.917 | 277.035 | -2.069 |
| 3 | 4-local | 434.271 | 345.126 | -1.368 |
| 3 | 6-local | 445.336 | 292.088 | -4.064 |

The proposed record does not create useful independent streaming in this
reader. The block-2D accesses must reconstruct many small per-record surfaces;
the resulting transactions lose the old layout's contiguous/coalesced behavior
and reduce effective bandwidth to roughly 261--347 GB/s. That overwhelms any
locality benefit from putting scales beside weights. The physical-card-0 device
loss is an independent stability rejection.

Raw logs and JSON outputs are preserved outside Git at:

```text
/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m1-mxfp4-tile-prepack-four-card-20260720Tfinal
```

The tracked structured summary is:

```text
experiments/deepseek-v4-flash-reap-xpu-b70/data/nospec-m1-mxfp4-tile-major-prepack-20260720.json
```

## Nonspec and speculative-path consequence

No same-binary nonspec B-A-B was justified: the microgate was substantially
below `+0.50 ms/token` and the candidate was unstable on one card. The 43.77
tok/s control remains the applicable nonspec reference.

This layout does **not** transfer to the M=7 DSpark draft GEMMs because those
routed GEMMs use FP8 block quantization, not MXFP4. The K160 target/verify M=8
path is MXFP4 and the generic packed reader was structurally wired at N64, but
the 80.82 tok/s record uses N128. Since this selector is rejected and remains
off, there is no validated transfer and no speed claim for that record's
draft/verify cycle.

## Next occupancy lever

The next non-repeated lever is a fixed-shape, native-FP8 oneDNN-JIT
specialization for the dense shared-down M=1 GEMV: use a narrower N tile and
more independent N workgroups while preserving K traversal, scales, FP32
accumulation, and BF16 rounding. Readiness is **low-to-medium**: the public
wrapper exposes no tile selector, so this requires a private specialization in
the pinned oneDNN JIT rather than another wrapper-level layout swap. At an
estimated 300--400 GB/s it is worth measuring but projects only about
0.300--0.375 ms/token, so it is unlikely to clear the whole 0.50 ms target by
itself.

Do not reopen the already-closed GRF128, simple prefetch, oneDNN swap,
software-dequant, or this generic tile-major prepack directions without new
evidence.
