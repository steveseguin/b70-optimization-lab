# 2026-06-26 11:55 - Sorted Top-K Plus Fused Selected-Softmax Screen

## Goal

Test whether combining the sorted `top_k` router path with the fused
selected-softmax path can recover enough router/materialization overhead to beat
the current Gemma 4 26B A4B Q8 record recipe.

This combines:

- `LLAMA_GEMMA4_MOE_TOP_K=1`;
- `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1`;
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`;
- the existing record recipe's selected-softmax + weighted-sum stack.

## Command

Record recipe plus sorted top-k and fused selected-softmax:

```bash
GPU_INDEX=0 PORT=18360 \
LABEL=gemma4-q8-gpu0-sortedtopk-fusedselectedsoftmax-pmin0136-screen-20260626T1155 \
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
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1 \
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
`data/gemma4-q8-gpu0-sortedtopk-fusedselectedsoftmax-pmin0136-screen-20260626T1155/summary.json`

Server log:
`/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-sortedtopk-fusedselectedsoftmax-pmin0136-screen-20260626T1155.server.log`

- Canary: **512/512 pass**.
- Fresh-response validity: `cached_tokens=[0,0,0,0]`; headline uses row 0 only.
- Row 0 throughput after TTFT: **100.505 tok/s**.
- Mean repeated-row throughput after TTFT: **100.384 tok/s**.
- Current valid record remains **103.299 tok/s**.

## Decision

Reject for promotion. The combination is valid, but slower than both the current
record and the prior selected-softmax fused-weights near-miss.

This closes the remaining cheap router-materialization flag combination. Future
Gemma work should move to a larger design such as a Gemma4-only small-token
fused MoE op or graph-level multi-token assistant unroll, not more
single-output router flag sweeps.
