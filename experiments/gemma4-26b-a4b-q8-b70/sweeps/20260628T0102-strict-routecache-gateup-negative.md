# 2026-06-28 Gemma 4 26B Strict Route-Cache/Gate-Up Screen

Purpose: retest low-cost route-cache and gate/up variants under the current
strict realistic cold-suite gate. Several of these variants were originally
measured under older synthetic or row0-style gates; this run closes them under
the current promotion policy.

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
- Base env: `GGML_SYCL_DISABLE_OPT=0`, `GGML_SYCL_DISABLE_GRAPH=0`,
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
| 0 | `LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT=1` | `../../../data/gemma4-q8-gpu0-strict-vdr2-gateup-singleton-n3-nmin2-p00475-ub1024-20260628T0102Z/` | 88.64037514681797 | 81.40620602689965 | 88.76608976050748 | 88.93137397531481 | 76.72645898748442 | 179.25597802968696 | valid, canary 32/32 |
| 1 | `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_DEVICE_MAP=1` | `../../../data/gemma4-q8-gpu1-strict-vdr2-routecache-devmap-n3-nmin2-p00475-ub1024-20260628T0102Z/` | 88.18334423611053 | 79.84331164587812 | 88.83189006764577 | 86.6267923774829 | 76.22279584037781 | 181.80815497180447 | valid, canary 32/32 |
| 2 | `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE=1` | `../../../data/gemma4-q8-gpu2-strict-vdr2-routecache-inplace-n3-nmin2-p00475-ub1024-20260628T0102Z/` | 87.44848512222445 | 78.26359027463839 | 87.71150944589516 | 86.8846378643342 | 76.58792345530179 | 182.2368479333818 | valid, canary 32/32 |
| 3 | singleton direct + device-map | `../../../data/gemma4-q8-gpu3-strict-vdr2-singleton-devmap-n3-nmin2-p00475-ub1024-20260628T0102Z/` | 85.4969891651534 | 79.37691692799328 | 85.66256229627129 | 87.43407215584259 | 77.67950310591687 | 180.76964444480836 | valid, canary 32/32 |

All rows had `realistic_final_gate.passed=true`,
`fresh_response_validity.valid=true`, and `cached_tokens_all_zero=true`.

## Decision

Negative. Do not submit. Do not enable these flags in promoted Gemma 26B Q8
recipes. The best row (`gate_up_q8_singleton_direct`) measured
`88.64037514681797 tok/s`, below the submitted `90.98312252660529 tok/s`
record.

This closes the low-cost route-cache/gate-up metadata variants under the
current strict gate. The next useful optimization needs to change actual target
verifier work, not how the existing small `MUL_MAT_ID` route metadata is cached.
