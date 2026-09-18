# Multi-row verifier attention census, September 18: the CUTLASS revision was the cause

Eight census runs of [`qwen38-fa-multiq-census.py`](../../scripts/qwen38-fa-multiq-census.py) against the
**untouched upstream single-row kernel** (vLLM's `flash_attn_varlen_func`, the shipped `_vllm_fa2_C`), 22 cases
each: contiguous and scattered page layouts x 11 KV lengths from 2,048 to 40,000, 20 repeats, `q_len` 6.
The reference is the same binary in every run; only the lab-built `libattn_multiq_kernels_xe_2.so` inside
`_xpu_C` changes. The gate is bit-exactness.

Four builds of the same source, differing only in toolchain and in the sycl-tla (CUTLASS) revision:

| Variant | File | Image | Host compiler | Device toolchain | sycl-tla | Exact | Max abs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r312c (session 4c) | `r312c-v64.json`, `r312c-v256.json` | `...-r312c-multiq` | lab DPC++ | lab IGC/ocloc | `cd76379` | **8/22** | 7.63e-6 |
| a (session 6) | `multiq-a-v64.json`, `multiq-a-v256.json` | `r312d-a` | DPC++ 2026.0.0 (upstream's) | lab IGC/ocloc | `cd76379` | **8/22** | 7.63e-6 |
| b (session 8) | `multiq-b-v64.json`, `multiq-b-v256.json` | `sha256:283311abb57b7e97574da822ad17cd13ca9b43ebf5db6fd15b1b34de6971a0c4` | DPC++ 2026.0.0 | IGC 2.34.4 / ocloc 26.18.38308.1 | `cd76379` | **8/22** | 7.63e-6 |
| c (session 8) | `multiq-c-v64.json`, `multiq-c-v256.json` | `sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a` | DPC++ 2026.0.0 | IGC 2.34.4 / ocloc 26.18.38308.1 | **`87f6850`** | **22/22** | **0.0** |

Each variant ran the census at v-tile 64 and at v-tile 256; the exact-case count and the maximum are the same at
both tile sizes for every variant, so the tiling is not what moves the arithmetic.

Variants r312c, a and b are **identical case by case**: the same 14 cases differ (contiguous 2,048 / 2,058 /
4,096 / 4,106 / 12,288 / 16,384 / 24,576 / 32,768 and scattered 2,058 / 4,096 / 4,106 / 8,192 / 32,768 / 40,000)
by the same 7.63e-6. Neither the host compiler (variant a) nor the device code generator (variant b) changes
anything. **Variant c -- b plus the sycl-tla revision `87f6850` that the kernel's own `CMakeLists.txt` pins as
`CUTLASS_REVISION` -- is bit-exact on all 22 cases at both v-tiles.** Everything the lab built from r309 through
r312c used `cd76379` (2026-03-18), 88 commits earlier, because that is what the clean-clone recipe checked out.

Speed (`ms_rows` / `ms_multiq` in each case record):

- v-tile 64: the multi-row path is faster on every case, **1.62x to 2.17x** (variant c; r312c 1.84-2.53x,
  a 1.67-2.53x, b 1.64-2.13x). The best ratios are in the middle of the range, 12K-32K.
- v-tile 256: mixed and mostly a loss, **0.50x to 1.26x** (variant c; the other three span 0.51-1.40x). It wins
  only at 2,048-2,058 tokens and collapses to about half speed at 4,096-4,106.

So v-tile 64 is the configuration to carry forward.

Sources: session 8 `/mnt/fast-ai/bench-results/fp8-r312d-session8-20260918/` (script
`/mnt/fast-ai/bench-results/r312d-session8-20260918.sh`, log `r312d-session8-20260918.log`), variant a
`/mnt/fast-ai/bench-results/fp8-r312d-session6-20260918/`, r312c
`/mnt/fast-ai/bench-results/fp8-r312-session4c-20260918/`. Builder Dockerfile
[`Dockerfile.r312d-multiq`](../../docker/rebase-v0290/Dockerfile.r312d-multiq), recipe
[`build-kernels-0.1.14.1-r312d-multiq-toolchain.sh`](../../docker/rebase-v0290/build-kernels-0.1.14.1-r312d-multiq-toolchain.sh)
with `VARIANT=b`/`c`; the `87f6850` clone is at `/mnt/fast-ai/build/sycl-tla-87f6850`. Both r312d images are the
r312c image with only `libattn_multiq_kernels_xe_2.so` replaced. Narrative:
[findings note](../../notes/2026-09-16-fp8-review-findings.md).
