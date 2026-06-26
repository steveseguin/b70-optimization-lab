# 2026-06-26T0821 - Q6_K fused output argmax screen

## Verdict

Rejected. The source patch is valid after a backend-support fix, but it does not
beat the current fresh-response record.

- Current promoted record: `103.2992004295621 tok/s` fresh row0 after TTFT.
- This screen: `103.01920886435965 tok/s` fresh row0 after TTFT.
- Canary: `128/128` rows pass (`32` repeats x `4` cases).
- Freshness: `cached_tokens=0` on the headline row.
- LocalMaxxing: not submitted; no new record.

## Patch

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/20260626T0821-llamacpp-q6k-fused-output-argmax.patch`

Intent:

- Existing fused-output argmax supported Q4_0 and Q8_0 output weights.
- Current Gemma 4 assistant MTP output head is Q6_K, so the previous fused-output
  argmax lane did not exercise the assistant output head on the active stack.
- Added Q6_K cases to SYCL `mul_mat_vec_q_argmax` and `mul_mat_vec_q_argmax_multi`,
  and enabled the Gemma 4 assistant/target guards for Q6_K.

Important fix during the attempt:

- First screen
  `data/gemma4-q8-gpu0-q6k-fusedoutargmax-screen-20260626T080607Z`
  aborted before readiness with
  `GGML_ASSERT(*cur_backend_id != -1)` in
  `ggml_backend_sched_split_graph`.
- Cause: execution path accepted Q6_K, but SYCL `supports_op` for
  `GGML_OP_MUL_MAT_ARGMAX` still advertised only Q4_0/Q8_0, leaving the fused
  node unassigned.
- Added Q6_K to that support guard and rebuilt successfully.

## Valid Screen

Run:

- `data/gemma4-q8-gpu0-q6k-fusedoutargmax-supportfix-screen-20260626T082104Z/summary.json`

Identity:

- Source: `/home/steve/src/llama.cpp-gemma-record-stack`, commit identity
  `c926ad098` plus dirty Gemma stack and this patch.
- Server:
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- Target:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- GPU: one B70 (`GPU_INDEX=0`, `ONEAPI_DEVICE_SELECTOR=level_zero:0`)
- Prompt shape: `filled-long`, requested p512/o512, actual `588` prompt /
  `512` output tokens.
- Key flags:
  - `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`
  - `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`
  - `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`
  - `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`
  - `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`
  - `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`
  - `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`
  - `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.136`
  - `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`
  - `GGML_SYCL_ENABLE_VMM=0`, `GGML_SYCL_DISABLE_GRAPH=0`
  - `--ctx-checkpoints 0`

Result:

- `headline_tok_s_after_ttft`: `103.01920886435965`
- `headline_tok_s_wall`: `89.74495265539471`
- `cached_tokens`: `0`
- `canary_pass_all`: `true`
- `canary_rows_completed`: `128`

## Interpretation

This lane is a clean negative result. It makes the fused output argmax path more
complete for Q6_K, but it is not a fresh throughput win on the active Gemma 4
stack. The current record already avoids most assistant-output overhead through
direct draft argmax IDs/unroll, and recent profiling shows the target verifier
`process_ubatch` path dominates. Do not promote this patch for record runs
unless another patch makes assistant output extraction hot again.

Next higher-value lane remains router/materialization fusion for verifier MoE
selection, as documented in `20260626T0830-verifier-frontier-source-audit.md`.
