# 20260627T2144 Q8_0 Target Strict Cold-Suite Control

## Question

Can the alternate Unsloth `gemma-4-26B-A4B-it-Q8_0.gguf` target beat the
current strict realistic-suite `UD-Q8_K_XL` record when run on the same B70
VDR2 stack?

The motivation was diagnostic only: the Q8_0 target is smaller than
`UD-Q8_K_XL` and llama.cpp/SYCL has heavily optimized Q8_0 paths. It is **not**
the promoted no-quality-loss lane unless the user explicitly accepts that
target quantization change. The gate remains the same strict cold-response
policy: fixed realistic suite, each prompt once, `cached_tokens=0`, no
repeated-prompt/history/cache acceleration, target model verifies all
speculative tokens.

## Shared Identity

- runtime: llama.cpp `c926ad098`, local VDR2 record build
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`;
- target/verifier: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-Q8_0.gguf`;
- main no-quality-loss comparison record: `UD-Q8_K_XL` target at
  `90.32179401019857 tok/s` median tokens 1-100 after TTFT;
- strict suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- core env: `GGML_SYCL_DISABLE_OPT=0`, `GGML_SYCL_DISABLE_GRAPH=0`,
  `GGML_SYCL_ENABLE_VMM=0`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`,
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`,
  `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`,
  `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`,
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`,
  `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`;
- runtime shape: `CTX_SIZE=8192`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`
  unless noted, `THREADS=8`, `POLL=100`, `FLASH_ATTN=off`,
  `REASONING=off`, `MAX_TOKENS=512`, f16 KV, `--parallel 1`,
  `--cache-ram 0`, `--ctx-checkpoints 0`.

## Results

All rows below passed canary, `fresh_response_validity.valid=true`, and
`realistic_final_gate.passed=true`.

| Run | Median 1-100 tok/s | p10 | Full512 after TTFT | Wall full512 | TTFT ms | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q80target-gpu0-strict-vdr2-nospec-ub1024-20260627T214413Z` | 82.962578 | 82.843114 | 80.377711 | 78.094030 | 182.413 | Q8_0 target no-spec is strong, but below MTP record. |
| `gemma4-q80target-gpu1-strict-vdr2-q40mtp-n3-p00475-ub1024-20260627T214413Z` | 90.097740 | 80.993582 | 85.269627 | 82.320418 | 182.835 | Q4_0 draft, n3/nmin2, near record but below. |
| `gemma4-q80target-gpu2-strict-vdr2-q80mtp-n3-p00475-ub1024-20260627T214413Z` | 85.909857 | 79.846827 | 86.062104 | 83.530725 | 181.621 | Q8_0 draft is valid but slower. |
| `gemma4-q80target-gpu3-strict-vdr2-q4kmmtp-n3-p00475-ub1024-20260627T214413Z` | 89.352459 | 79.225012 | 84.514289 | 81.719034 | 182.417 | Q4_K_M draft is valid but slower than Q4_0. |
| `gemma4-q80target-gpu0-strict-vdr2-q40mtp-n3-nmin1-p00475-ub1024-20260627T214710Z` | 91.556408 | 82.742926 | 88.157715 | 85.559804 | 181.094 | Apparent win; required confirmation. |
| `gemma4-q80target-gpu0-strict-vdr2-q40mtp-n3-nmin1-p00475-confirmA-ub1024-20260627T215106Z` | 88.948818 | 77.692223 | 83.842167 | 81.319506 | 182.743 | Exact repeat did not confirm. |
| `gemma4-q80target-gpu1-strict-vdr2-q40mtp-n3-nmin1-p00475-confirmB-ub1024-20260627T215106Z` | 89.892343 | 81.871341 | 87.341999 | 84.131568 | 183.677 | Exact repeat did not confirm. |
| `gemma4-q80target-gpu2-strict-vdr2-q40mtp-n3-nmin1-p004625-ub1024-20260627T215106Z` | 85.024736 | 80.558051 | 84.184221 | 81.664480 | 182.155 | Lower p_min neighbor lost. |
| `gemma4-q80target-gpu3-strict-vdr2-q40mtp-n3-nmin1-p004875-ub1024-20260627T215106Z` | 88.041965 | 78.924476 | 83.751305 | 81.029927 | 183.481 | Higher p_min neighbor lost. |
| `gemma4-q80target-gpu0-strict-vdr2-q40mtp-n4-nmin1-p00475-ub1024-20260627T215841Z` | 89.256163 | 78.366485 | 85.547966 | 83.029993 | 181.684 | Deeper n4/nmin1 lost. |
| `gemma4-q80target-gpu1-strict-vdr2-q40mtp-n4-nmin2-p00475-ub1024-20260627T215841Z` | 90.276784 | 82.762407 | 83.491538 | 81.012839 | 182.362 | Best depth row; still below 90.322. |
| `gemma4-q80target-gpu2-strict-vdr2-q40mtp-n5-nmin1-p00475-ub1024-20260627T215841Z` | 83.348722 | 75.837393 | 80.130941 | 77.912521 | 181.880 | n5/nmin1 loses badly. |
| `gemma4-q80target-gpu3-strict-vdr2-q40mtp-n5-nmin2-p00475-ub1024-20260627T215841Z` | 86.755572 | 70.059961 | 81.057472 | 78.620433 | 182.055 | n5/nmin2 loses. |

## Conclusion

`Q8_0` target is a useful compatibility/control lane and has a strong no-spec
baseline, but it did **not** produce a reproducible strict record and should
not replace `UD-Q8_K_XL` under the no-quality-loss rule. The single
`91.556408 tok/s` row was variance; exact repeats landed at `88.948818` and
`89.892343`, and the best deeper row landed at `90.276784`, just below the
current `UD-Q8_K_XL` record.

Do not submit these rows to LocalMaxxing as a new record. If Q8_0 is revisited,
it should be because a source/runtime change specifically benefits Q8_0 target
weights, not as more shallow MTP threshold/depth noise.
