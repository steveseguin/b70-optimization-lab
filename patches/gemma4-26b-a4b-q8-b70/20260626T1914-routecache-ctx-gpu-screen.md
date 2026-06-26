# Gemma 4 26B Q8 Route-Cache CTX/GPU Screen

Date: 2026-06-26

Status: GPU2/ctx8192 screen promoted after full validation. The other three
screen rows remain non-promoted.

## Purpose

Recheck the current route-cache recipe across four independent one-B70 runs to
separate small runtime-shape/GPU variance from a real improvement. This keeps
Gemma 26B as the active lane while leaving MiniMax TP4 as optional side work.

## Common Recipe

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one full model replica on one B70, no TP;
- draft-MTP `n=7`, `n_min=2`, `p_min=0.136`;
- `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`;
- `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`;
- `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`;
- `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`;
- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`;
- `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`;
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`;
- `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`;
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`;
- `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`;
- `GGML_SYCL_ENABLE_VMM=0`;
- `GGML_SYCL_DISABLE_GRAPH=0`;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`;
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-long`;
- screen depth: `CANARY_REPEATS=32`, `BENCH_REPEATS=2`.

## Screen Results

All screen rows reported `cached_tokens=0`, so these are fresh-response eligible
screens, but not promotion-depth validations.

| Label | GPU | CTX | Canary | Fresh row0 after TTFT | Support mean after TTFT | Headline cached tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemma4-q8-gpu2-routecache-ctx8192-repeat-screen-20260626T191410Z` | 2 | 8192 | 128/128 | `103.89855970182825` | `103.41785095575216` | 0 |
| `gemma4-q8-gpu1-routecache-ctx4096-screen-20260626T191410Z` | 1 | 4096 | 128/128 | `103.5062668438265` | `103.40510985752661` | 0 |
| `gemma4-q8-gpu0-routecache-ctx2048-screen-20260626T191410Z` | 0 | 2048 | 128/128 | `103.38904345107419` | `102.31694859854301` | 0 |
| `gemma4-q8-gpu3-routecache-ctx16384-screen-20260626T191410Z` | 3 | 16384 | 128/128 | `103.2123470627072` | `103.30490446775657` | 0 |

## Decision

The GPU2 / ctx8192 screen is above the then-current promoted `103.30108468098005`
fresh-response micro-record, but the margin can easily be screen/GPU variance.
Do not submit it to LocalMaxxing until a full gate passes.

Full validation:

```bash
GPU_INDEX=2 PORT=18262 \
LABEL=gemma4-q8-gpu2-routecache-ctx8192-full-20260626T191746Z \
CTX_SIZE=8192 \
CANARY_REPEATS=384 BENCH_REPEATS=8 \
scripts/run-gemma4-26b-mtp-candidate.sh
```

Full-gate result:

- run:
  `data/gemma4-q8-gpu2-routecache-ctx8192-full-20260626T191746Z/summary.json`;
- chat canary: **1536/1536**;
- all 8 benchmark rows reported `cached_tokens=0`;
- fresh row0 after TTFT: **`103.51547512013657 tok/s`**;
- support mean after TTFT: `103.19340167720759 tok/s`;
- row0 wall: `90.22004912439446 tok/s`;
- LocalMaxxing: `cmqvbq8tf02m1qr010dom0vu1`.

Decision: promote as the current valid fresh-response Gemma 26B Q8 one-B70
micro-record. This supersedes `103.30108468098005 tok/s`, but the margin is
small and should be treated as runtime/GPU-variance cleanup, not material
progress toward the `>150 tok/s` target.
