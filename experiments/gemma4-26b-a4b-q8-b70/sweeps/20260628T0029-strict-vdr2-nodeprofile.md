# 2026-06-28 Gemma 4 26B Strict VDR2 Node Profile

Purpose: capture the SYCL graph/node hot spots for the current strict
UD-Q8_K_XL + Q4_0-MTP lane under the realistic cold-response gate. This run is
diagnostic only; node profiling adds enough overhead that the measured
throughput is not comparable to the submitted record.

## Run

- Data:
  `../../../data/gemma4-q8-gpu0-strict-vdr2-nodeprofile2-n3-nmin2-p00475-ub1024-20260628T002941Z/`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-strict-vdr2-nodeprofile2-n3-nmin2-p00475-ub1024-20260628T002941Z.server.log`
- Runtime: llama.cpp `c926ad098`, VDR2 reordered-Q8 build
  `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`
- Target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- Spec config: `n_max=3`, `n_min=2`, `p_min=0.0475`,
  direct argmax-ID unroll, q-only assistant attention inputs, assistant fused
  output argmax, verifier backend argmax IDs, deferred target `h_nextn`
- Runtime shape: `UBATCH_SIZE=1024`, f16 KV, `FLASH_ATTN=off`,
  `--parallel 1 --cache-ram 0`, `--ctx-checkpoints 0`,
  `GGML_SYCL_DISABLE_OPT=0`, `GGML_SYCL_DISABLE_GRAPH=0`,
  `GGML_SYCL_ENABLE_VMM=0`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`
- Profiling: `LLAMA_SERVER_SPEC_PROFILE=1`, `GGML_SYCL_NODE_PROFILE=1`,
  `GGML_SYCL_NODE_PROFILE_DETAIL=1`, `GGML_SYCL_NODE_PROFILE_EVERY=24`

## Validity And Result

The benchmark gate itself was valid, but the score is not a candidate record
because node profiling perturbs runtime.

- Fixed suite: `gemma4-26b-a4b-q8-b70-realistic-v1`
- Prompts: 12 unique prompts, each sent once
- `cached_tokens`: all zero
- Canary: `16/16` rows passed
- `realistic_final_gate.passed`: `true`
- Median generated-token throughput for tokens 1-100 after TTFT:
  `59.55962845637647 tok/s`
- p10 / mean: `52.04565185050634` / `58.885685249834324`
- Full 128-token after-TTFT median: `56.528041950643185 tok/s`
- Median TTFT: `210.30924300430343 ms`

The current submitted record remains
`90.98312252660529 tok/s` from
`../../../data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json`.

## Node Profile Snapshot

Final profile block:

- `graphs=2496`, `unique_nodes=1393`, `top=30`
- #1 node: target/verifier LM head full vocab projection
  - `MUL_MAT:node_2075`
  - `total_ms=891.483`, `calls=646`, `avg_ms=1.380`
  - `src0=token_embd.weight`, `q8_0`, `ne=[2816,262144]`
  - `src1=result_norm`, `f32`, `ne=[2816,1]`
- #2 node: final-layer verifier MoE gate/up
  - `MUL_MAT_ID:ffn_moe_gate_up-29`
  - `total_ms=345.776`, `calls=674`, `avg_ms=0.513`
  - weight is `bf16`, `ne=[2816,1408,128]`
- #3 cumulative node: `RMS_NORM:norm`
  - `total_ms=252.122`, `calls=30004`, `avg_ms=0.008`
- #4-#6 nodes: assistant direct argmax unroll output projections
  - `MUL_MAT_ARGMAX:mtp_direct_argmax_unroll_token_0/1/2`
  - about `238-240 ms` total each, `607 calls`, `0.393-0.395 ms/call`
  - these use the Q4_0 MTP draft `token_embd.weight` reported as `q6_K`
    packed tensors
- #7 and below: verifier MoE down and gate/up per layer, generally
  `0.30-0.34 ms/call` for Q8 layers and `0.34-0.51 ms/call` for the bf16
  edge/final layer.

Server spec profile at run end:

- `draft_ms=3018.186`, `calls=676`, `draft_tokens=1808`,
  `avg=4.465 ms`
- `target_decode_ms=31103.329`, `calls=676`, `tokens=3927`,
  `avg=46.011 ms`, `avg_token=7.920 ms`
- `target_generation_ms=25633.716`, `calls=620`, `tokens=2428`,
  `avg=41.345 ms`, `avg_token=10.558 ms`
- Final request acceptance:
  - `draft acceptance = 0.50336`
  - `mean acceptance length = 2.50`
  - position acceptance `(0.660, 0.460, 0.380)`
- Cumulative `draft-mtp` stats:
  - generated draft tokens `1808`, accepted draft tokens `1076`
  - mean accepted length `2.78`
  - position acceptance `(0.776, 0.575, 0.430)`

## Interpretation

- The strict lane is target/verifier-bound. Draft generation is visible, but
  still much smaller than target/verifier decode.
- The verifier LM head remains the largest single node. Earlier strict tests of
  verifier fused/raw/softcap argmax shortcuts did not produce a confirmed win,
  so simply changing the argmax publication path is exhausted.
- The remaining broad hot surface is verifier MoE `MUL_MAT_ID` gate/up and down
  across layers. Small reordered-Q8 addressing variants (`grouped`,
  `direct_vdr2`, `pair_slots`, `top8_slots`) are already negative or
  unconfirmed, so future MoE work should be a materially different kernel or
  graph-boundary change.
- A real next step needs either:
  1. fewer exact target/verifier rows per fresh response;
  2. a faster exact verifier LM-head/max proof;
  3. a structural Gemma4 verifier MoE boundary improvement.

Do not use this node-profile run for LocalMaxxing. Use it only to guide source
work and to avoid more draft-side or tiny threshold sweeps.
