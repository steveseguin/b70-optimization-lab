# 2026-06-26 11:45 - Fused-Down Direct-F32 Parallel-Slot Screen

## Goal

Test the last narrow untested member of the Gemma4 fused-down selected expert
family: a direct-F32 current-activation kernel with one work group per
`(token, expert-slot, output-row-block)`.

This combines two previously separate valid losses:

- direct-F32 fused-down path: about `100.83 tok/s`;
- Q8_1 parallel-slot fused-down path: about `102.24 tok/s`.

## Command

Record recipe plus fused-down direct-F32 parallel slots:

```bash
GPU_INDEX=0 PORT=18360 \
LABEL=gemma4-q8-gpu0-fuseddown-directf32-parslots-screen-20260626T1145 \
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
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM=1 \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DIRECT_F32_PARALLEL_SLOTS=1 \
GGML_SYCL_ENABLE_VMM=0 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_DISABLE_GRAPH=0 \
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 \
BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100 FLASH_ATTN=off \
scripts/run-gemma4-26b-mtp-candidate.sh
```

## Result

Summary:
`data/gemma4-q8-gpu0-fuseddown-directf32-parslots-screen-20260626T1145/summary.json`

Server log:
`/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-fuseddown-directf32-parslots-screen-20260626T1145.server.log`

- Canary: **512/512 pass**.
- Fresh-response validity: `cached_tokens=[0,0,0,0]`; headline uses row 0 only.
- Row 0 throughput after TTFT: **100.646 tok/s**.
- Mean repeated-row throughput after TTFT: **101.960 tok/s**.
- Current valid record remains **103.299 tok/s**.

## Decision

Reject for promotion. The combined direct-F32 + parallel-slot fused-down kernel is
valid but slower than the current selected-softmax + weighted-sum record stack.

This closes the remaining cheap fused-down variant. Future Gemma work should not
keep sweeping fused-down env combinations unless a materially different kernel
design changes the amount of target verifier work.
