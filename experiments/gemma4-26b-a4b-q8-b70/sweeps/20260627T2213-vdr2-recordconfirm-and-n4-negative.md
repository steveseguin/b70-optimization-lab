# 2026-06-27 VDR2 Record Confirmation And n=4 Negative

Goal: use all four B70s on the strict realistic cold suite to decide whether the
current UD-Q8_K_XL VDR2 identity had a reproducible record improvement, and
whether deeper MTP (`n_max=4`) was worth more work.

Promotion gate:

- fixed suite `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- each prompt once as a cold response;
- `cached_tokens=0` on every request;
- no prompt/KV cache reuse, response reuse, context checkpoints,
  n-gram/history acceleration, or warmed repeated prompts;
- target/verifier `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- Q4_0 MTP draft tokens verified by the Q8 target;
- headline metric: median tok/s for generated tokens 1-100 after TTFT.

Common identity:

```text
llama.cpp c926ad098, local B70 SYCL/AOT Gemma patch stack
target: gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
draft:  MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf
GPU count: 1 per run, one complete model replica per B70
CTX_SIZE=8192 BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100
FLASH_ATTN=off REASONING=off --parallel 1 --cache-ram 0 --ctx-checkpoints 0
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
GGML_SYCL_DISABLE_OPT=0
GGML_SYCL_DISABLE_GRAPH=0
GGML_SYCL_ENABLE_VMM=0
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
```

## First four-lane sweep

| Run | Spec config | Valid | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-strict-vdr2-control-repeat-n3-nmin2-p00475-ub1024-20260627T221310Z/summary.json` | `n_max=3`, `n_min=2`, `p_min=0.0475` | yes | **91.39281557735391** | 80.37573622408729 | 89.77141252723108 | 84.96309119927025 | 82.21262210763227 | 179.32311847107485 |
| `data/gemma4-q8-gpu1-strict-vdr2-profile-n3-nmin2-p00475-ub1024-20260627T221310Z/summary.json` | same, passive profile enabled | yes | 90.25734172603185 | 78.610489684836 | 89.11439689106072 | 83.56511425480687 | 81.15980311382509 | 180.05119502777234 |
| `data/gemma4-q8-gpu2-strict-vdr2-n4-nmin1-p00475-ub1024-20260627T221310Z/summary.json` | `n_max=4`, `n_min=1`, `p_min=0.0475` | yes | 82.12005329123728 | 77.84938261458619 | 85.35879491557733 | 82.13767255720401 | 79.78905200410858 | 180.81612547393888 |
| `data/gemma4-q8-gpu3-strict-vdr2-n4-nmin2-p00475-ub1024-20260627T221310Z/summary.json` | `n_max=4`, `n_min=2`, `p_min=0.0475` | yes | 85.93327599447983 | 75.89740810812947 | 85.26420796478028 | 83.52829920788818 | 80.54812967243689 | 179.72216254565865 |

Interpretation:

- The `91.3928` row is a real strict-valid observation, but it needed an exact
  same-config confirmation before promotion because recent high rows have shown
  material GPU/run variance.
- Passive profiling did not materially perturb the lane (`90.2573`).
- `n_max=4` is a clear loss in the fixed cold suite. Deeper speculation likely
  needs a new acceptance/scoring mechanism; just increasing depth adds target
  verifier work faster than it adds accepted fresh tokens.

Profile highlights from the passive lane:

```text
target_generation_ms=103470.077 calls=3710 tokens=14800 avg=27.890 ms avg_token=6.991 ms
draft_ms=10188.538 calls=4758 draft_tokens=11090 avg=2.141 ms
target decode phase: process_ubatch_ms=169680.327, sampled_extract_ms=6149.378
acceptance rate per position ~= (0.829, 0.689, 0.572)
```

`process_ubatch` dominates. The sampled-ID extract path is visible but not large
enough by itself to explain the remaining gap. Next source work should target
the verifier/target kernel side, not more p-min noise.

## Exact confirmation

Four exact repeats of the current best identity:

| Run | Valid | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json` | yes | 88.57072965699355 | 78.12918725872953 | 88.32256581191301 | 83.8309353245964 | 80.72457670760123 | 180.31806696671993 |
| `data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json` | yes | **90.98312252660529** | 80.12003134222003 | 90.18386686514286 | 85.91896026873997 | 82.89661752202322 | 179.28718304028735 |
| `data/gemma4-q8-gpu2-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json` | yes | 89.87311437412865 | 80.41912476719682 | 89.1511748113403 | 83.83042433989228 | 80.89206455773767 | 180.98254001233727 |
| `data/gemma4-q8-gpu3-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json` | yes | 87.29987510414621 | 78.76947419512518 | 87.04935557682329 | 84.3409595892499 | 81.76214928923596 | 179.86489698523656 |

Decision:

- Submit the conservative reproduced improvement, not the isolated `91.3928`
  high observation.
- LocalMaxxing accepted
  `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-recordconfirm-20260627T221722`
  as `cmqwxep4a03qiqr010chjn93s`.
- Payload:
  `data/localmaxxing-payloads/gemma4-q8-vdr2-p00475-recordconfirm-20260627T221722.json`.
- Response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-recordconfirm-20260627T221722.submit.log`.

Next actions:

- Stop plain `n_max=4`/threshold sweeps in this exact runtime identity.
- Highest-value source bets from audits:
  1. narrow VDR2 Q8 `MUL_MAT_ID` MMVQ specialization for current decode slices;
  2. exact verifier candidate-vs-max op that avoids materializing normal logits
     while preserving target-model argmax correctness;
  3. optional direct-unroll top1/top2 score side channel only if scores are
     nearly free.
