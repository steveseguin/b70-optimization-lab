# Ornith 1.5 35B-A3B: paired recurrent QKV/gate projection regresses

Date: 2026-08-23 EDT

Status: **CLOSED PERFORMANCE NEGATIVE — do not ship**

Ornith's Qwen-derived recurrent layers project the same 2048-element
activation through an 8192-row QKV matrix and a later 4096-row gate/Z matrix.
Unlike the rejected alpha/beta pair, these outputs have overlapping lifetimes
and distinct allocations. A default-off candidate therefore combined their
otherwise unchanged reordered-ESIMD work-group grids into one launch.

The Q4_K_M file contains mixed QKV quantization: 16 recurrent QKV matrices are
Q4_K and 14 are Q6_K; every gate matrix is Q4_K. The implementation selected a
compile-time-specialized Q4_K/Q4_K or Q6_K/Q4_K paired kernel and retained the
incumbent two-row dot-product function unchanged. It activated exactly 3,810
times in a 128-token forced run (30 recurrent layers × 127 decode evaluations)
and matched the canonical transcript SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.

The mirrored same-binary engine screen was negative:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `120.721246`, `120.476032` | **120.598639** |
| paired QKV/gate | `119.117286`, `120.052148` | **119.584717** |

That is **-0.841%**. Removing 30 launches/token does not repay the instruction
footprint and scheduling cost of the heterogeneous combined grid. No server or
canary run was justified, and the accepted seven-fusion stack remains
unchanged.

The complete candidate source is preserved at
`../patches/llamacpp-ornith15-qkv-gate-paired-performance-negative-20260823.patch`.
Raw exactness and mirrored engine records plus the structured result are under
`../data/2026-08-23-ornith35b-qkv-gate-paired-*`.
