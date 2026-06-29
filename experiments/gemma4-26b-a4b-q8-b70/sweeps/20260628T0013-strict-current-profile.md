# 2026-06-28 Gemma 4 26B Strict Current-Stack Profile

Purpose: profile the current submitted Gemma 4 26B Q8 realistic-suite lane under
the actual cold final gate, not the older synthetic filled-long diagnostic. The
goal was to decide whether continued work should target draft-side MTP overhead
or target/verifier compute.

## Run

- Data:
  `../../../data/gemma4-q8-gpu0-strict-vdr2-profile-current-n3-nmin2-p00475-ub1024-20260628T001306Z/`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-strict-vdr2-profile-current-n3-nmin2-p00475-ub1024-20260628T001306Z.server.log`
- Runtime: llama.cpp `c926ad098`, VDR2 reordered-Q8 build
  `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`
- Target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- Spec config: `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `--no-spec-draft-backend-sampling`, direct argmax-ID unroll, q-only assistant
  attention inputs, fused assistant output argmax, verifier backend argmax IDs,
  deferred target `h_nextn`
- Runtime shape: `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`,
  `POLL=100`, f16 KV, `FLASH_ATTN=off`, `--parallel 1 --cache-ram 0`,
  `--ctx-checkpoints 0`, `GGML_SYCL_DISABLE_OPT=0`,
  `GGML_SYCL_DISABLE_GRAPH=0`, `GGML_SYCL_ENABLE_VMM=0`,
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`
- Profiling: `LLAMA_MTP_DRAFT_PROFILE=1`

## Validity And Result

This is a valid cold final-gate run but not a record.

- Fixed suite: `gemma4-26b-a4b-q8-b70-realistic-v1`
- Prompts: 12 unique prompts, each sent once
- `cached_tokens`: all zero
- `realistic_final_gate.passed`: `true`
- Canary: `128/128` rows passed
- Median generated-token throughput for tokens 1-100 after TTFT:
  **89.65814180509349 tok/s**
- p10 / mean: `81.0384836401858` / `89.21251404987648`
- Full 512-token after-TTFT median: `86.01213797595119 tok/s`
- Full 512-token wall median: `82.5792551961039 tok/s`
- Median TTFT: `179.57304295850918 ms`

The current submitted record remains
`90.98312252660529 tok/s` from
`../../../data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json`.
Do not submit this profile run to LocalMaxxing.

## Profile Findings

Final cumulative MTP profile snapshot:

- MTP accepted `4676` of `7840` generated draft tokens, mean acceptance length
  `2.79`, per-position acceptance `(0.770, 0.576, 0.442)`.
- Target decode phase:
  - `calls=2902`, `tokens=16301`, `ubatches=2902`
  - `total_ms=92829.566`, `per_call_ms=31.988`, `per_token_ms=5.695`
  - `process_ubatch_ms=88713.159`
  - `post_extract_ms=4054.734`, almost entirely `sampled_extract_ms=4053.799`
- Draft decode phase:
  - `calls=2618`, `tokens=2619`, `ubatches=2618`
  - `total_ms=7150.390`, `per_call_ms=2.731`, `per_token_ms=2.730`
  - `process_ubatch_ms=6037.002`
  - `post_extract_ms=1070.331`, `sampled_extract_ms=1063.388`
- MTP draft-side counters:
  - `process_ms=48.994`, `draft_decode_ms=7135.246`
  - `fast_sync_ms=3.884`, `accept_copy_ms=25.343`
  - `sampler_calls=0`, `hidden_rows=0`, `handoff_rows=0`,
    `device_h_rows=0`, `device_h_fallbacks=0`

Interpretation:

- The current direct-unroll draft path is already small. Draft `process_ubatch`
  is about `6.0 s` cumulative while target/verifier `process_ubatch` is about
  `88.7 s`.
- Host sampler, hidden-state handoff, and draft-side score extraction are not
  the primary bottlenecks in the current strict lane.
- Target sampled-row extraction is visible, but because it follows target graph
  execution it likely includes synchronization/wait time. Treat the target
  verifier forward, especially Gemma4 MoE plus LM-head/argmax boundaries, as
  the real optimization surface.

## Decision

Do not spend more effort on blind `p_min`, draft quantization, draft handoff, or
small reordered-Q8 addressing variants without new profile evidence. Those
families are already exhausted or draft-side dominated.

Next useful work should be one of:

1. a structural target/verifier reduction that keeps greedy target verification
   exact, for example candidate-vs-max or a lower-cost LM-head verification
   design;
2. a source-level Gemma4 target MoE boundary change backed by node-profile
   evidence, not a broad flag sweep;
3. a real direct-path confidence side channel only if it lets us avoid
   wasteful target verifier rows while remaining valid on fresh responses.

