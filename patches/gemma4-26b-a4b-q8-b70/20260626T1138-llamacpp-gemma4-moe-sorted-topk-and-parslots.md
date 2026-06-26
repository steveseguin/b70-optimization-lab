# llama.cpp Gemma 4 MoE Sorted Top-K And Parallel-Slot Toggles

Source tree:
`/home/steve/src/llama.cpp-gemma-record-stack`

Primary file:
`ggml/src/ggml-sycl/ggml-sycl.cpp`

## Patch Summary

Two source-level experiment toggles were added:

1. `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1`
   - In `top_k_f32_sycl()`, keep the sorted top-k winner order by suppressing the
     existing final swap of positions 0 and 1.
   - Default behavior is unchanged when the env var is unset.
   - Tested in
     `gemma4-q8-gpu0-sortedtopk-selectedsoftmax-weightedsum-pmin0136-screen`.
   - Result: valid but slower, **100.177 tok/s** row0 after TTFT, **512/512**
     canary pass.

2. `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DIRECT_F32_PARALLEL_SLOTS=1`
   - Adds a dormant direct-F32 fused-down weighted-sum parallel-slot kernel path.
   - Tested in
     `gemma4-q8-gpu0-fuseddown-directf32-parslots-screen-20260626T1145`.
   - Result: valid but slower, **100.646 tok/s** row0 after TTFT, **512/512**
     canary pass.

Follow-up sorted-router combo:

- `LLAMA_GEMMA4_MOE_TOP_K=1` +
  `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1` +
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`
- Tested in
  `gemma4-q8-gpu0-sortedtopk-fusedselectedsoftmax-pmin0136-screen-20260626T1155`.
- Result: valid but slower, **100.505 tok/s** row0 after TTFT, **512/512**
  canary pass.

## Minimal Relevant Diff

```diff
--- a/ggml/src/ggml-sycl/ggml-sycl.cpp
+++ b/ggml/src/ggml-sycl/ggml-sycl.cpp
@@
 static void top_k_f32_sycl(...)
 {
     const sycl::range<1> block_dims(block_size);
     const sycl::range<1> grid_dims(nrows);
+    const char * sorted_env = std::getenv("LLAMA_GEMMA4_MOE_SORTED_TOP_K");
+    const bool keep_sorted =
+        sorted_env && (std::strcmp(sorted_env, "1") == 0 ||
+                       std::strcmp(sorted_env, "true") == 0 ||
+                       std::strcmp(sorted_env, "TRUE") == 0 ||
+                       std::strcmp(sorted_env, "yes") == 0 ||
+                       std::strcmp(sorted_env, "on") == 0);
@@
-                    if (k > 1) {
+                    if (k > 1 && !keep_sorted) {
                         int32_t temp = dst_idx_row[0];
                         dst_idx_row[0] = dst_idx_row[1];
                         dst_idx_row[1] = temp;
                     }
```

## Harness Follow-Up

The result harness now captures these env keys in `launcher_identity`:

- `llama_gemma4_moe_sorted_top_k`
- `llama_gemma4_moe_fused_down_weighted_sum_parallel_slots`
- `llama_gemma4_moe_fused_down_weighted_sum_direct_f32_parallel_slots`

That is metadata-only and does not change benchmark behavior.
