# 2026-07-04 - LM-head call-count source audit

## Scope

This note records the post-Phase-2 source audit for the current Qwen27 record
lane:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- checkpoint:
  `/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`;
- runtime: vLLM/XPU, one B70, target AutoRound W4A16 plus runtime INT8 LM-head
  with BF16 scales;
- record to beat: LocalMaxxing `cmr5iu3gk00bfq901nidgcana`,
  `65.27648650325429 tok/s` median generated-token throughput for tokens 1-100
  after TTFT, strict fresh-response Qwen realistic suite.

No endpoint benchmark was run for this audit and there is no LocalMaxxing
submission. The point was to decide whether a small source patch still exists
after the compact LM-head top-1 kernel and spec-top-ID integration both closed
as no-win.

## Source Findings

The exact all-greedy top-ID consumer already exists:

- `gpu_model_runner.py` can route precomputed spec top-token IDs into
  `rejection_sampler.forward_from_top_token_ids(...)`;
- `rejection_sampler.py` has exact greedy rejection from target argmax IDs plus
  target-owned bonus token IDs;
- the gate is narrow enough to be quality-safe: greedy only, no logprobs,
  penalties, masks, logits processors, synthetic acceptance, or margin gates.

The blocker is the producer. Today both target `get_top_tokens()` and draft
greedy sampling still call the LM-head quant method first and materialize dense
local logits:

- `logits_processor.py:get_top_tokens()` calls
  `lm_head.quant_method.apply(...)` before doing `max`;
- `vocab_parallel_embedding.py` runtime INT8 LM-head still returns dense logits
  from `torch.ops._xpu_C.int8_gemm_w8a8(...)`;
- `llm_base_proposer.py:_greedy_sample()` calls `compute_logits().argmax()`,
  and MTP3 repeats that once per drafted token.

The active checkpoint is `qwen3_5`, not a Qwen3Next multi-layer drafter:

- `text_config.model_type=qwen3_5_text`;
- `hidden_size=5120`;
- `vocab_size=248320`;
- `mtp_num_hidden_layers=1`.

That matters because increasing `num_speculative_tokens` reuses the same single
MTP predictor autoregressively. The strict four-GPU current-recipe depth screen
already confirmed this is not a config win: MTP3/cg8 `65.809 tok/s`, MTP4/cg8
`60.478`, MTP5/cg8 `59.257`, MTP5/cg16 `59.817`, all fresh and
`cached_tokens=0`.

## Why Lazy Row Verification Is Not A Small Patch

Conceptually, an exact MTP3 verifier only needs:

1. target argmax for row 0;
2. target argmax for row 1 only if row 0 accepted;
3. target argmax for row 2 only if row 1 accepted;
4. target-owned bonus only on full accept.

With the observed acceptance profile this could reduce expected target verifier
rows from `4` to roughly `2.5-2.8` rows/step. However, with the current
primitive stack, making that lazy in Python would turn one efficient rows-4
oneDNN W8A8 GEMM into several rows-1 GEMM launches. The microbench already
showed rows 1-4 dense LM-head latency is nearly flat, so a Python-level lazy
verifier is expected to lose.

This remains credible only if implemented as one native fused/conditional
verifier primitive, or a oneDNN-integrated top-ID/candidate epilogue that avoids
dense logits and avoids multiple GEMM launches.

## Closed Avenues Reinforced By This Audit

- Spec greedy top IDs alone: exact and strict-valid, but flat because the
  producer is dense `get_top_tokens()`.
- Draft-only row-count shortcut: invalid for headline use and previously
  collapsed because it removes normal target replacement / target-owned bonus
  behavior.
- Scheduler-only adaptive depth: strict-valid but slower because it reduced
  emitted tokens per verifier step.
- Proposer-side partial-group depth: crashed the Qwen/GDN XPU verifier metadata
  path with an indexing assert.
- Config-only MTP4/MTP5: strict no-wins on the current record recipe.
- Standalone compact full-vocab top-1 kernel: exact, but slower than dense
  oneDNN plus argmax at rows `1-4`.

## External Check

Primary-source documentation and public vLLM/Qwen3.5 reports matched the local
read:

- oneDNN matmul is a dense destination primitive with ordinary post-op fusion;
  no documented argmax/top-k/candidate-reduction matmul epilogue is exposed for
  this use case;
- vLLM reports the `qwen3_next_mtp` method alias as deprecated in favor of
  `mtp`, and warns that `num_speculative_tokens > 1` can run multiple forwards
  on the same MTP layer and lower acceptance.

Useful links:

- `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html`
- `https://uxlfoundation.github.io/oneDNN/dev_guide_graph_matmul_fusion_patterns.html`
- `https://github.com/vllm-project/vllm/issues/36643`

## Decision

Do not burn more endpoint runs on Python-level row/count shortcuts unless a new
trace proves the bottleneck moved. The remaining credible Qwen27 routes are:

1. implement a real XMX/oneDNN-level LM-head top-ID/candidate verifier primitive
   that avoids dense logits and avoids an extra reduction launch;
2. implement a native lazy verifier that keeps row-adaptive semantics inside one
   fused operation rather than launching multiple rows-1 GEMMs;
3. revisit DFlash only by adding real multi-KV-group draft metadata support for
   its mixed `4 sliding + 1 full` layer layout;
4. move to a different model/runtime lane if the goal is near-term records
   rather than deeper Qwen27 kernel engineering.

The next active Qwen27 code task, if continuing this lane, should start from one
of the first three items above. Anything else is likely config roulette.
