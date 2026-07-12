# 2026-07-12 MMVQ Batch Size Extension

## Problem

The SYCL MMVQ (matrix-vector quantized) kernel for Q4_0 had a hard-coded
`MMVQ_MAX_BATCH_SIZE = 8` limit (`common.hpp:174`). Spec decode verify
batches exceeding 8 tokens fell through to the MMQ (prefill) kernel, causing
a 10-12x speed cliff:
- batch=8 (n_max=7): 47.15 tok/s
- batch=9 (n_max=8): 4.78 tok/s (12x slower)

Root cause: `mmvq.cpp` has template specializations for `ncols_dst` 1-8 only,
with `default: GGML_ABORT(...)` for larger values. In NDEBUG builds the abort
is silent, producing garbage output.

## Fix

Two changes in `/home/steve/src/llama.cpp`:

1. Extended the Q4_0 switch statements in `mmvq.cpp` to handle `ncols_dst`
   9-17 (both reordered and non-reordered paths). The underlying template
   `mul_mat_vec_q_reorder_ncols<N>` already supports arbitrary N via
   `float partial_sum[ncols_dst]` — only the dispatch was limited.

2. Changed `can_use_mul_mat_vec_q()` in `ggml-sycl.cpp` to allow Q4_0 up to
   batch=17 while keeping all other quant types at the original limit of 8.
   This prevents Q4_K draft model GEMM from hitting the unextended Q4_K
   switch and silently producing garbage.

## Results

| Config | Before fix | After fix |
|--------|:---:|:---:|
| DFlash n_max=8 | 4.78 tok/s | 15.34 tok/s |
| DFlash n_max=15 | 8.49 tok/s | 11.43 tok/s |

The cliff is eliminated. However, MTP3 at ~58 tok/s remains faster than all
DFlash configs because per-token compute in attention/GDN layers still scales
with batch size, even with the fast MMVQ kernel.

## Acceptance Note

Draft acceptance rates changed slightly between MMVQ and MMQ paths (e.g.,
n_max=8 acceptance went from 0.545 to 0.429). This is expected numerical
sensitivity — different tiling produces slightly different floating-point
results, which can flip greedy token selection at boundary cases. The
quality gate (exact token matching vs no-spec baseline) must be run to
confirm output correctness.

## Patch

Local modification to `/home/steve/src/llama.cpp`. Not submitted upstream.
Preserve as a patch artifact if the approach proves valuable.
