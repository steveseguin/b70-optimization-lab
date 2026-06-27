# 2026-06-27T15:36Z Q8-Reorder Current-Stack Node Profile

## Purpose

Refresh the diagnostic node profile after the Q8 MoE-ID reorder breakthrough.
This is **not** a headline performance result: `GGML_SYCL_NODE_PROFILE=1`
disables normal SYCL graph behavior and adds profiling overhead.

## Run

- summary:
  `data/gemma4-q8-gpu1-nodeprofile-q8reorder-ub720-rms-20260627T153621Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-nodeprofile-q8reorder-ub720-rms-20260627T153621Z.server.log`
- current Q8 reorder identity:
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`,
  `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`,
  `UBATCH_SIZE=720`, `n_max=7`, `n_min=3`, `p_min=0.10`
- diagnostic env:
  `GGML_SYCL_NODE_PROFILE=1`, `GGML_SYCL_NODE_PROFILE_DETAIL=1`,
  `GGML_SYCL_NODE_PROFILE_EVERY=24`, `LLAMA_SERVER_SPEC_PROFILE=1`
- canary: 16/16 rows, pass
- cached-token validity: `[0]`
- profiled row0 speed: 106.053 tok/s after TTFT, diagnostic only

## Hotspot Snapshot

End-of-run server profile:

- `draft_ms=594.912`, `calls=85`, `draft_tokens=350`, avg `6.999 ms`
- `target_decode_ms=6347.722`, `calls=85`, `tokens=1609`, avg `74.679 ms`,
  avg/token `3.945 ms`
- `target_prompt_ms=3692.703`, `calls=34`, `tokens=1208`, avg `108.609 ms`
- `target_generation_ms=2655.019`, `calls=51`, `tokens=401`, avg `52.059 ms`
- process / sample / accept / emit are tiny (`<0.05 ms` average each)

Top node-profile entries near the end of the run:

- `MUL_MAT:node_2075` / `token_embd.weight` LM head:
  `134.247 ms`, 68 calls, avg `1.974 ms`
- `MUL_MAT_ID:ffn_moe_gate_up-0`:
  `127.705 ms`, 85 calls, avg `1.502 ms`
- `MUL_MAT_ID:node_2059` / block 29 down:
  `86.230 ms`, 85 calls, avg `1.014 ms`
- `MUL_MAT_ID:ffn_moe_gate_up-29`:
  `84.404 ms`, 85 calls, avg `0.993 ms`
- `MUL_MAT_ID:node_58` / block 0 down:
  `77.600 ms`, 85 calls, avg `0.913 ms`
- most remaining top-30 nodes are `MUL_MAT_ID:ffn_moe_gate_up-*`, roughly
  `64-72 ms` each over the profiled window.

## Interpretation

The LM head is the largest single node, but the aggregate bottleneck is still
the target/verifier MoE body, especially Q8 `ffn_moe_gate_up-*` across many
layers. The draft side and acceptance path are not the current limiter.

This supports moving away from small runtime/threshold sweeps and toward one of
the larger source lanes:

1. a narrow Q8 verifier gate/up body improvement that preserves the tuned
   Q8-reorder `MUL_MAT_ID` path;
2. a larger MoE gate/up+GEGLU+down boundary that avoids replacing the tuned dot
   body with a naive slower kernel;
3. an exact verifier output/LM-head redesign only if it avoids the full output
   materialization path without repeating the known-slower
   `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` lane.
