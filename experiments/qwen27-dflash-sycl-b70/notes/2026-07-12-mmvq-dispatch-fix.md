# 2026-07-12 MMVQ Dispatch Fix — The Real Cliff Root Cause

## Summary

Extended the Q4_0 SYCL MMVQ (matrix-vector quantized) kernel from a hard
batch limit of 8 to 17, eliminating a 3-4x performance cliff that blocked
DFlash speculative decode at n_max > 7. DFlash n_max=15 improved from
8.49 to 38.5 tok/s (4.5x).

## Root Cause

The cliff had TWO layers, both in `mmvq.cpp`:

1. **Switch statement limit** (line 699-715): `reorder_mul_mat_vec_q4_0_q8_1_sycl_switch_ncols`
   only had cases for ncols_dst 1-8, with `GGML_ABORT` for larger values.
   Fixed by adding cases 9-17.

2. **Dispatch loop fallback** (line 2101-2132): `ggml_sycl_op_mul_mat_vec_q`
   has a `for (int i = 0; i < src1_ncols; i++)` loop. When ncols <= 8, it
   calls the batched kernel and returns immediately. When ncols > 8, it
   falls through to single-column processing — **reading the full 15 GB
   weight matrix once per column instead of once total**.

   For batch=9: 9 × 15 GB = 135 GB at 608 GB/s = 222 ms (matches observed 231 ms).
   For batch=16: 16 × 15 GB = 240 GB → should be 395 ms (observed 377 ms, close).

   Fixed by changing `src1_ncols <= 8` to `src1_ncols <= 17` for Q4_0.

3. **can_use_mul_mat_vec_q gate** (ggml-sycl.cpp:4332): `MMVQ_MAX_BATCH_SIZE`
   was 8 globally. Fixed with a type-specific check: Q4_0 allowed up to 17,
   all other types stay at 8.

## Verification (llama-bench ppN = prefill at batch N)

| Batch | Before (t/s) | After (t/s) | Improvement |
|-------|:-:|:-:|:-:|
| pp8 | 128.93 | 128.93 | — (unchanged) |
| pp9 | 39.02 | **108.51** | **2.78x** |
| pp16 | 42.46 | **145.76** | **3.44x** |

Smooth scaling confirmed: no cliff between pp8 and pp16.

## DFlash End-to-End Results

| Config | Before fix | After fix | Acceptance | Mean Len |
|--------|:-:|:-:|:-:|:-:|
| MTP3 | 58.3 | 53.2 | 0.731 | 3.17 |
| DFlash n_max=15 | 8.49 | **38.5** | 0.440 | 7.41 |
| DFlash n_max=8 | 4.78 | 33.1 | 0.518 | 5.04 |

DFlash n_max=15 achieves mean accepted length 7.41 on code prompts —
close to hipfire's reported range (7-9). The remaining gap to hipfire's
213 tok/s is:
1. Draft cycle overhead (~100 ms vs ~10 ms theoretical)
2. Bandwidth utilization (62% vs ~68%)
3. DFlash draft model maturity ("still under training")

## Patch

`patches/qwen36-27b-autoround-int4-b70/llamacpp-sycl-mmvq-ncols17-q4_0-20260712.patch`
