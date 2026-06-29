# 2026-06-27 Strict Draft-Quant Screen Negative

Goal: test whether replacing the current Q4_0 MTP draft with higher-precision
official Unsloth MTP draft files improves the fixed realistic cold-suite result
while keeping the promoted target/verifier quality lane unchanged.

Promotion gate:

- fixed suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- each prompt sent once as a cold response;
- `cached_tokens=0` on every row;
- no prompt/KV/context checkpoint/response reuse;
- no n-gram/history acceleration;
- target/verifier unchanged: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- speculative draft tokens verified by the declared Q8 target;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT.

Common identity:

```text
llama.cpp c926ad098, local B70 SYCL/AOT Gemma patch stack
target: gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
GPU count: 1 complete replica per B70
CTX_SIZE=8192 BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100
FLASH_ATTN=off REASONING=off --parallel 1 --cache-ram 0 --ctx-checkpoints 0
VDR2 reordered-Q8 target stack:
  LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1
  LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1
  LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1
  LLAMA_MTP_DEFER_TARGET_H_NEXTN=1
  LLAMA_MTP_DRAFT_FAST_ARGMAX=1
  LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1
  LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7
  LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1
  LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1
  LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1
  LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1
  LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1
  LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1
  LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
spec: n_max=3, n_min=2, p_min=0.0475, f16 target/draft KV
```

## Results

| Run | Draft file | Valid | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-strict-vdr2-draftq4km-n3-nmin2-p00475-ub1024-20260627T2322fg/summary.json` | `gemma-4-26B-A4B-it-Q4_K_M-MTP.gguf` | yes | 84.231968 | 79.206325 | 86.277781 | 82.412828 | 79.462495 | 180.351 | loss |
| `data/gemma4-q8-gpu1-strict-vdr2-draftq5km-n3-nmin2-p00475-ub1024-20260627T2322fg/summary.json` | `gemma-4-26B-A4B-it-Q5_K_M-MTP.gguf` | yes | 88.109559 | 81.084072 | 88.392937 | 84.732133 | 82.345516 | 181.002 | loss |
| `data/gemma4-q8-gpu2-strict-vdr2-draftq6k-n3-nmin2-p00475-ub1024-20260627T2322fg/summary.json` | `gemma-4-26B-A4B-it-Q6_K-MTP.gguf` | yes | 85.728881 | 79.200083 | 86.275321 | 83.857879 | 80.728929 | 181.248 | loss |
| `data/gemma4-q8-gpu3-strict-vdr2-draftq80-n3-nmin2-p00475-ub1024-20260627T2322fg/summary.json` | `gemma-4-26B-A4B-it-Q8_0-MTP.gguf` | yes | 88.245438 | 80.580464 | 86.819067 | 83.879705 | 80.820255 | 179.759 | loss |

All rows passed `realistic_final_gate.passed=true`, had
`cached_tokens_all_zero=true`, and passed the 8-repeat canary screen. None beat
the current strict promoted `UD-Q8_K_XL` target / Q4_0 draft VDR2 record:

`90.98312252660529 tok/s`
(`data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json`).

## Conclusion

Higher-precision official MTP draft files do not improve this strict
fresh-response lane. The current default should remain the Q4_0 MTP draft for
the promoted Q8 target/verifier stack. The result reinforces that this frontier
is target/verifier-cost-bound more than draft-quality-bound: Q5_K_M and Q8_0
drafts were the closest controls, but both remained about 2.7-2.9 tok/s below
the valid record.

Do not submit these rows to LocalMaxxing. Future draft work should require a
new acceptance mechanism or verifier-cost reduction, not another simple draft
quantization swap.
