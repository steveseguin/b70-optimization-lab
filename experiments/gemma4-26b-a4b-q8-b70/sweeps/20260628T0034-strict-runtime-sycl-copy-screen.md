# 2026-06-28 Gemma 4 26B Strict Runtime Copy/Allocation Screen

Purpose: use the four B70 GPUs to screen cheap SYCL/Level Zero runtime knobs
around the current strict UD-Q8_K_XL VDR2 record identity. These rows are
valid cold-suite measurements, but none beat the submitted record.

## Shared Identity

- Target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- Runtime: llama.cpp `c926ad098`, VDR2 reordered-Q8 build
  `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`
- Spec config: `n_max=3`, `n_min=2`, `p_min=0.0475`,
  direct argmax-ID unroll, q-only assistant attention inputs, assistant fused
  output argmax, verifier backend argmax IDs, deferred target `h_nextn`
- Runtime shape: `UBATCH_SIZE=1024`, `BATCH_SIZE=1024`, f16 KV,
  `FLASH_ATTN=off`, `--parallel 1 --cache-ram 0`, `--ctx-checkpoints 0`
- Baseline env: `GGML_SYCL_DISABLE_OPT=0`, `GGML_SYCL_DISABLE_GRAPH=0`,
  `GGML_SYCL_ENABLE_VMM=0`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`,
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`
- Gate: fixed realistic suite `gemma4-26b-a4b-q8-b70-realistic-v1`, each
  prompt once, `cached_tokens=0`, no prompt/KV/history reuse.

Current submitted record for this quality lane remains:

- `data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json`
- median tokens 1-100 after TTFT: **90.98312252660529 tok/s**
- LocalMaxxing approved ID: `cmqwxep4a03qiqr010chjn93s`

## Results

| GPU | Variant | Data dir | Median 1-100 tok/s | p10 | Mean | Full after-TTFT median | Wall median | TTFT median ms | Validity |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | Control | `../../../data/gemma4-q8-gpu0-strict-runtime-control-n3-nmin2-p00475-ub1024-20260628T003443Z/` | 85.40977109929057 | 75.51649331500593 | 85.75498828630758 | 83.91574022709969 | 75.13642861541788 | 180.6290804524906 | valid, canary 32/32 |
| 1 | `GGML_SYCL_USE_ASYNC_MEM_OP=0` | `../../../data/gemma4-q8-gpu1-strict-runtime-asyncmem0-n3-nmin2-p00475-ub1024-20260628T003443Z/` | 89.89151710630107 | 83.53746839861007 | 90.2085726370007 | 90.2000235757184 | 79.40761667252133 | 180.86405453504995 | valid, canary 32/32 |
| 2 | `GGML_SYCL_DEV2DEV_MEMCPY=1` | `../../../data/gemma4-q8-gpu2-strict-runtime-l0copy-n3-nmin2-p00475-ub1024-20260628T003443Z/` | 87.20277456169313 | 79.41740588731305 | 86.4957718147109 | 85.71935801535349 | 76.73865296327203 | 180.22583599667996 | valid, canary 32/32 |
| 3 | `GGML_SYCL_USE_LEVEL_ZERO_API=0` | `../../../data/gemma4-q8-gpu3-strict-runtime-levelzeroalloc0-n3-nmin2-p00475-ub1024-20260628T003443Z/` | 86.32650903005273 | 78.67333658576713 | 87.38101682388128 | 88.87111535309239 | 77.06594216502796 | 179.78570598643273 | valid, canary 32/32 |

All rows had `realistic_final_gate.passed=true`,
`fresh_response_validity.valid=true`, and `cached_tokens_all_zero=true`.

## Decision

Negative. Do not submit. These runtime knobs are either noise or losses
relative to the `90.98312252660529 tok/s` record. The best variant,
`GGML_SYCL_USE_ASYNC_MEM_OP=0`, reached `89.89151710630107 tok/s`, close to
record but still below it.

This screen also reinforces the node-profile conclusion: the lane is not
limited by host/device copy or allocation policy. The next useful work should
target verifier-side cost: exact target rows per response, LM-head verification
cost, or a materially new Gemma4 verifier MoE boundary change.
