# Gemma4 MoE RMS Reuse Micro-Record

Date: 2026-06-27

## Summary

Tested a default-off llama.cpp source patch,
`LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`, on the current Gemma 4 26B A4B Q8 B70
record stack. The patch reuses the unweighted `RMS(attn_out)` inside each
Gemma4 MoE layer for:

- shared MLP input norm;
- routed expert FFN input norm;
- router input norm.

The router still applies the existing `1/sqrt(n_embd)` scale before the router
matmul. This was intentionally conservative so the experiment only removes
duplicate RMSNorm graph nodes and does not move router scaling across the
linear projection.

## Result

Full validation:

- run dir:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`;
- summary:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/summary.json`;
- benchmark:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/p512o512.json`;
- canary: `1536` repeats / `6144` rows passed;
- all benchmark rows reported `cached_tokens=0`;
- fresh row0 headline: **104.30919255569083 tok/s** after TTFT;
- first-row wall throughput: `90.85119259916031 tok/s`;
- support mean: `103.93445004566178 tok/s`;
- LocalMaxxing: `cmqw1tgzx0366qr01g4lkv7f1`.

Screen before full validation:

- run dir:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-filledlong-screen-20260627T070313Z/`;
- canary: `64/64`;
- fresh row0: `104.27340324045828 tok/s`.

One earlier screen accidentally used `BENCH_PROMPT_MODE=long` and is not
comparable to the promoted filled-long record:

- `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-screen-20260627T070149Z/`;
- fresh row0: `46.65192294066687 tok/s`;
- reason invalid for comparison: wrong benchmark prompt identity.

## Identity

Target/verifier:

```text
/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
```

Draft:

```text
/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf
```

Important runtime identity:

```text
GPU_INDEX=0
CTX_SIZE=8192
BATCH_SIZE=1024
UBATCH_SIZE=768
THREADS=8
POLL=100
FLASH_ATTN=off
GGML_SYCL_ENABLE_VMM=0
GGML_SYCL_DISABLE_GRAPH=0
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1
LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1
LLAMA_MTP_DRAFT_FAST_ARGMAX=1
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7
MTP_N_MAX=7
MTP_N_MIN=3
MTP_P_MIN=0.10
MTP_BACKEND_SAMPLING=0
MTP_DRAFT_THREADS=32
MTP_DRAFT_THREADS_BATCH=32
MTP_EXTRA_ARGS='--ctx-checkpoints 0'
BENCH_PROMPT_MODE=filled-long
PROMPT_TOKENS=512
MAX_TOKENS=512
```

## Decision

Accept as the current fresh row0 micro-record because it passed the full gate
and improved row0 from `104.22626983476746` to `104.30919255569083 tok/s`.

Do **not** treat this as material progress toward `>150 tok/s`: the support mean
is lower than the prior record (`103.934` vs `104.174`) because one repeated
support row was slower. This is a tiny row0 micro-record and the lane still
needs structural verifier-side reduction or a different fresh-valid speculation
engine for a meaningful jump.

## Artifacts

- Patch note:
  `patches/gemma4-26b-a4b-q8-b70/20260627-llamacpp-gemma4-moe-reuse-attn-rms-record.md`
- LocalMaxxing queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-rmsreuse-ub768-nmin3-pmin010-fresh-20260627.queue.json`
- LocalMaxxing response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-rmsreuse-ub768-nmin3-pmin010-fresh-20260627.submit.log`
