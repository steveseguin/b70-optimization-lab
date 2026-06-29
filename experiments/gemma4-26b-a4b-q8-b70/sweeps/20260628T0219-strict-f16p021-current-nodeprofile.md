# 2026-06-28 Gemma 4 26B Current F16 P021 Node Profile

Purpose: refresh the SYCL node profile after promoting
`LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`. Earlier node profiles were from the
pre-p021 ~90 tok/s era and should not drive the next >100 attempt.

This run is diagnostic only. Node profiling materially slows runtime and must
not be used as a LocalMaxxing or headline throughput result.

## Run

- Data:
  `../../../data/gemma4-q8-gpu0-strict-vdr2-f16p021-nodeprofile-current-n3-nmin2-p00475-ub1024-20260628T021937Z/`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-strict-vdr2-f16p021-nodeprofile-current-n3-nmin2-p00475-ub1024-20260628T021937Z.server.log`
- Target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- Runtime: llama.cpp `c926ad098`, local VDR2 reordered-Q8 build
- Record-stack flags: route cache, Q8 MoE-ID reorder, verifier backend argmax
  IDs, deferred target `h_nextn`, direct draft argmax unroll 7,
  q-only assistant attention inputs, assistant fused output argmax,
  selected-softmax fused, weighted-sum, RMS reuse,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`
- Profiling:
  `LLAMA_SERVER_SPEC_PROFILE=1`, `GGML_SYCL_NODE_PROFILE=1`,
  `GGML_SYCL_NODE_PROFILE_DETAIL=1`, `GGML_SYCL_NODE_PROFILE_EVERY=24`

## Validity

The gate itself was valid, but the score is profiler-perturbed:

- canary rows: `64/64`
- `realistic_final_gate.passed=true`
- `cached_tokens_all_zero=true`
- profiler-slowed median 1-100 after TTFT:
  `63.15413032574937 tok/s`

## Final Profile Block

- `graphs=3120`, `unique_nodes=1393`, `top=30`
- #1 target/verifier LM head:
  - `MUL_MAT:node_2075`
  - `total_ms=1131.905`, `calls=824`, `avg_ms=1.374`
  - `src0=token_embd.weight`, `q8_0`, `ne=[2816,262144,1,1]`
  - `src1=result_norm`, `f32`, `ne=[2816,1,1,1]`
- #2 final-layer verifier MoE gate/up:
  - `MUL_MAT_ID:ffn_moe_gate_up-29`
  - `total_ms=482.280`, `calls=900`, `avg_ms=0.536`
  - `src0=blk.29.ffn_gate_up_exps.weight`, `bf16`,
    `ne=[2816,1408,128,1]`
- #3-#8, #10, #12-#18, #20-#28, #30 are verifier MoE `MUL_MAT_ID`
  gate/up nodes, mostly Q8 layers at about `0.34-0.38 ms/call`.
- #11, #19, #29 are verifier MoE down nodes, about `0.32-0.36 ms/call`.
- #9 is cumulative `RMS_NORM:norm`, `39000` calls, `0.008 ms/call`.

Server spec profile:

- `draft_ms=3675.269`, `calls=903`, `draft_tokens=2207`,
  `avg=4.070 ms`
- `target_decode_ms=42385.430`, `calls=903`, `tokens=6317`,
  `avg=46.938 ms`, `avg_token=6.710 ms`
- `target_generation_ms=29016.030`, `calls=751`, `tokens=2958`,
  `avg=38.637 ms`, `avg_token=9.809 ms`
- request-level draft acceptance:
  `0.57664`, mean acceptance length `2.72`, per-position
  `(0.826, 0.500, 0.391)`
- cumulative MTP acceptance:
  generated draft tokens `2207`, accepted draft tokens `1461`, mean accepted
  length `2.98`, per-position `(0.824, 0.649, 0.507)`

## Interpretation

The current p021 record stack is still target/verifier-bound.

The LM head remains the largest single node, but current-stack retesting of
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1`,
`LLAMA_SPEC_VERIFY_RAW_ARGMAX=1`, and
`LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX=1` did not crack 100 and the fused-output
path was a large loss. See
`20260628T0222-strict-target-argmax-current-negative.md`.

The next credible path is verifier MoE `MUL_MAT_ID`: one bf16 final-layer
gate/up node plus many Q8 gate/up/down nodes dominate nearly the entire top-30
list after the LM head. Small route-cache/addressing variants are already
negative, so future work should change the actual dot/body work or graph
boundary, not only metadata handling.
