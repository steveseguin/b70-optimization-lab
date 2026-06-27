# 2026-06-27 Gemma 4 26B Current-Stack MTP Profile

Purpose: profile the current promoted Gemma 4 26B Q8 target plus Q4_0 MTP
draft stack after the `104.22626983476746 tok/s` fresh-response record, then
decide whether the next work should be more flag sweeping or source-level
changes.

## Run

- Data: `../../../data/gemma4-q8-gpu0-currentstack-mtpprofile-20260627T053818Z/`
- Server log: `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-currentstack-mtpprofile-20260627T053818Z.server.log`
- Target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- Current-stack knobs: `MTP_N_MAX=7`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`,
  direct argmax-ID unroll 7, q-only assistant inputs, Gemma4 assistant fused
  output argmax, verifier backend argmax IDs, deferred target `h_nextn`,
  selected-softmax + fused selected-softmax, weighted sum, route cache,
  `BATCH_SIZE=1024`, `UBATCH_SIZE=768`, `THREADS=8`, `POLL=100`,
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, VMM off, SYCL graph on.
- Profiling: `LLAMA_MTP_DRAFT_PROFILE=1`
- Benchmark shape: `PROMPT_TOKENS=512`, `MAX_TOKENS=128`, `BENCH_REPEATS=1`,
  `CANARY_REPEATS=8`

## Validity

This is a diagnostic, not a LocalMaxxing or headline result.

- Chat canary passed: `32` rows.
- Benchmark row reported `cached_tokens=[1]` because canaries ran before the
  benchmark request, so the benchmark row is not a fresh-response headline
  under the current validity rule.
- The row measured `99.5534113318176 tok/s` after TTFT on 128 output tokens,
  but it should not be compared to the `512`-token record or submitted.

## Profile Findings

Final MTP profile snapshot from `server.stdout.log`:

- draft acceptance: `109 accepted / 126 generated`, mean accepted length
  `7.06`, per-position acceptance
  `(1.000, 0.944, 0.889, 0.833, 0.833, 0.778, 0.778)`;
- target decode phase: `process_calls=149`, `process_tokens=2452`,
  `verify_rows=2452`, `process_ubatch_ms=12118.505`,
  `post_extract_ms=212.336`;
- draft decode phase: `draft_decodes=82`, `draft_decode_tokens=82`,
  `process_ubatch_ms=488.134`, `post_extract_ms=38.356`;
- direct fast path counters: `fast_topk_calls=82`, `vocab_scanned=0`,
  `sampler_calls=0`, `hidden_rows=0`, `handoff_rows=0`;
- confidence gates did not fire: `stops gap=0`, `pmin=0`, `nmax=0`,
  `avg_top1_p=1.000000`, `avg_logit_gap=0.000000`.

Interpretation:

- The current direct-unroll assistant path is operating as an ID-only argmax
  producer. It does not expose real top-1 probability or logit gap, so
  `MTP_P_MIN` and gap-threshold sweeps are mostly variance unless a source
  patch adds a compact score side channel.
- Target verifier work dominates. In this diagnostic, target `process_ubatch`
  time is roughly 25x draft `process_ubatch` time.
- Higher blind unroll depth is already ruled out by the 20260627T0531 depth
  screen. To chase `>150 tok/s` fresh-response, the useful directions are:
  reduce target verifier MoE / LM-head work, or make direct-unroll confidence
  real enough to avoid wasteful target verifier rows.

## Dead Follow-Up: Gate/Up Scale Epilogue

A read-only MoE audit proposed fusing a possible
`ffn_moe_gate_up_scaled` multiply into the `MUL_MAT_ID` epilogue. Local profile
inspection found no `ffn_moe_gate_up_scaled` node in the active Gemma 26B Q8
path; the current hot gate/up nodes are plain
`MUL_MAT_ID:ffn_moe_gate_up-*`.

Decision: do not implement a selected-scale gate/up epilogue for the current
path unless a future profile shows that scale node exists. It is a dead patch
target for this record stack.

## Next Useful Source Work

1. Add a compact direct-argmax score side channel (top1/top2 or logit gap) so
   direct unroll can make real fresh-valid confidence decisions without
   disabling the fused assistant output argmax.
2. Explore exact verifier candidate-vs-max for the target LM head. It must
   preserve greedy correctness and avoid materializing full logits where
   possible.
3. Revisit gate/up only if the patch preserves the tuned Q8 `MUL_MAT_ID`
   arithmetic. Broad route-cache/device-map/in-place variants and blind
   singleton-direct variants are already recorded as losses or near-neutral.

