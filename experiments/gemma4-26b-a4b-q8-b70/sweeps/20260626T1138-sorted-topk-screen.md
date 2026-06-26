# 2026-06-26 11:38 - Sorted MoE `top_k` Screen

## Goal

Test whether Gemma 4 26B A4B Q8 can replace the record recipe's
`argsort_top_k` router path with the cheaper `ggml_top_k` path while preserving
the expert order expected by selected-softmax routing.

The prior `LLAMA_GEMMA4_MOE_TOP_K=1` test was not argsort-equivalent because
the SYCL `top_k_f32_sycl()` kernel sorted winners and then swapped the first two
IDs before writing output. This experiment added
`LLAMA_GEMMA4_MOE_SORTED_TOP_K=1` to suppress that final swap.

## Source / Patch

Patch record:
`patches/gemma4-26b-a4b-q8-b70/20260626T1138-llamacpp-gemma4-moe-sorted-topk-and-parslots.md`

Build:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31 --target llama-server -j 8
```

## Command

Record recipe plus sorted top-k:

```bash
GPU_INDEX=0 PORT=18360 \
LABEL=gemma4-q8-gpu0-sortedtopk-selectedsoftmax-weightedsum-pmin0136-screen \
BENCH_PROMPT_MODE=filled-long CANARY_REPEATS=128 BENCH_REPEATS=4 \
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.136 \
MTP_BACKEND_SAMPLING=0 MTP_DRAFT_THREADS=32 MTP_DRAFT_THREADS_BATCH=32 \
MTP_EXTRA_ARGS="--ctx-checkpoints 0" \
LLAMA_MTP_DRAFT_FAST_ARGMAX=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1 \
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1 \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1 \
LLAMA_GEMMA4_MOE_TOP_K=1 \
LLAMA_GEMMA4_MOE_SORTED_TOP_K=1 \
GGML_SYCL_ENABLE_VMM=0 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_DISABLE_GRAPH=0 \
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 \
BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100 FLASH_ATTN=off \
scripts/run-gemma4-26b-mtp-candidate.sh
```

## Result

Summary:
`data/gemma4-q8-gpu0-sortedtopk-selectedsoftmax-weightedsum-pmin0136-screen/summary.json`

Server log:
`/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-sortedtopk-selectedsoftmax-weightedsum-pmin0136-screen.server.log`

- Canary: **512/512 pass**.
- Fresh-response validity: `cached_tokens=[0,0,0,0]`; headline uses row 0 only.
- Row 0 throughput after TTFT: **100.177 tok/s**.
- Mean repeated-row throughput after TTFT: **99.769 tok/s**.
- Current valid record remains **103.299 tok/s**, so this is a valid negative.

## Decision

Do not promote `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1` for the Q8 record recipe. It is
correct on this screen but slower than the current best.

Useful learning: the cheaper sorted `top_k` path is not a route to the next
record by itself. Future MoE work should prioritize reducing route/materialize
overhead or fusing larger router/expert fragments, not swapping argsort for this
top-k kernel.
