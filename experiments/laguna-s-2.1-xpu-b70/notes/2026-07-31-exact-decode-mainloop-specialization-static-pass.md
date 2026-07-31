# Laguna exact decode mainloop specialization static pass

Date: 2026-07-31 America/Toronto

Status: **production static gate passed; full DSO/component gate authorized**.
No model service or score-bearing GPU run occurred.

## Identity

- kernel base: `e4163f93574326b2772742e0f51372a5a3777aa5`;
- candidate: `ec507e8b0b1bb7ca36adb81565e29c781fbc0cc2`;
- branch: `experiment/laguna-exact-specialized-20260731`;
- compiler: oneAPI `icpx` 2025.3.3, BMG AOT backend;
- artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-decode-exact-specialized-ec507e8-20260731T0951Z`.

All three BMG device builds reported `Build succeeded.` The expected final host
link then failed because the probe intentionally does not link PyTorch. The
device `.asm`, `.zeinfo`, SPIR-V, and binaries were already emitted; as in the
preceding GRF128 gate, this is a post-AOT harness boundary rather than a device
compile failure.

## Matched production ISA

The probe instantiated the real
`MoEGEMMLauncher<'R','C',w4a16_policy_m_8>` and emitted both named kernels in
one image.

| Property | exact specialized | generic GRF128 control |
| --- | ---: | ---: |
| IGC instructions | **674** | 6,174 |
| GRFs / EU threads / SIMD | 128 / 8 / 16 | 128 / 8 / 16 |
| live BF16 scale multiplies | **32** | 256 across all variants |
| INT4 shifts / bitfield ops | **16 / 16** | 256 / 256 across all variants |
| DPAS | **2** | 32 across all variants |
| `sync.allrd` / `sync.nop` | **6 / 14** | 217 / 261 |
| zeinfo scratch/private/spill fields | absent | absent |

The specialized counts are exactly the known live group-32 vectorized
mainloop: 32 scale multiplies, 16 shifts, 16 bitfield operations, and two DPAS.
The generic control contains that same body plus the folded, MAD, scalar, and
other group-size instantiations behind uniform runtime branches. The treatment
therefore removes dead variants rather than changing the live arithmetic.

IGC's comment-only register-allocation diagnostics also fall from 26/65 to 4/5
store/load flags. Neither kernel exposes scratch/private memory in zeinfo, so
these are allocator diagnostics, not evidence of runtime scratch traffic.

## Dispatch audit and decision

The new named kernel requires both the already verified GRF128 predicate and
literal `VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED=1`. The shared predicate
requires BF16 A/scales, packed INT4 B, R/C layout, non-tile-major
`w4a16_policy_m_8`, `total_m=120`, group size 32, scale-vector on, MAD/fold
off. Selector-off control, draft `total_m=10`, prefill, and other policies do
not reach the new kernel.

This clears the preregistered static stop gate by a wide margin. Proceed to a
full grouped-GEMM DSO build and then changed-input raw-BF16 comparison against
the current GRF128 control for the real W13 and W2 shapes. Endpoint execution
still requires a separate authorization after the component result.

Source snapshots:

- patch SHA-256:
  `540235f285cc84457c30b74d1ddb322ca9355e1fd7a0c44a1f4df70a22936d26`;
- bundle SHA-256:
  `8cf6b505bbb3f96f9c75c30cee46576af9972dc896dabc0dca0aaaf34e237c15`.

The subsequent [component gate](2026-07-31-exact-decode-mainloop-specialization-component-result.md)
was bitwise exact but performance-neutral/slightly negative, so the lane
stopped before an endpoint.
