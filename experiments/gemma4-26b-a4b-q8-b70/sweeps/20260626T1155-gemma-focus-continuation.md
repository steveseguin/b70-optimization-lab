# 2026-06-26 11:55 - Gemma Focus Continuation

## Context

Gemma 4 26B A4B Q8 remains the active priority. MiniMax TP4 may be repaired
later, but it should not consume the main optimization lane while Gemma still
has plausible source-level work.

Current valid Gemma best remains:

- `103.2992004295621 tok/s` fresh row0 after TTFT;
- `cached_tokens=0`;
- `1536/1536` chat canary;
- LocalMaxxing `cmqsylo2l011nqr011yydjvne`;
- evidence:
  `data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z/summary.json`.

## Results Added This Session

Two valid negative screens were completed and recorded:

1. `LLAMA_GEMMA4_MOE_TOP_K=1` +
   `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1`
   - summary:
     `data/gemma4-q8-gpu0-sortedtopk-selectedsoftmax-weightedsum-pmin0136-screen/summary.json`
   - canary: `512/512`
   - fresh row0: `100.17712860142362 tok/s`
   - decision: reject; sorted top-k is correct but slower.

2. `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM=1` +
   `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DIRECT_F32_PARALLEL_SLOTS=1`
   - summary:
     `data/gemma4-q8-gpu0-fuseddown-directf32-parslots-screen-20260626T1145/summary.json`
   - canary: `512/512`
   - fresh row0: `100.64563787402767 tok/s`
   - decision: reject; closes the remaining cheap fused-down variant.

Third screen completed after this note was opened:

3. `LLAMA_GEMMA4_MOE_TOP_K=1` +
   `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1` +
   `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`
   - summary:
     `data/gemma4-q8-gpu0-sortedtopk-fusedselectedsoftmax-pmin0136-screen-20260626T1155/summary.json`
   - canary: `512/512`
   - fresh row0: `100.50527983189384 tok/s`
   - decision: reject; combining sorted top-k with fused selected-softmax is
     correct but still below the `103.299 tok/s` record.

## Read-Only Audit Findings

Two subagents audited the remaining Gemma source frontier.

### Verifier Candidate-vs-Max

Exact candidate-vs-max does **not** avoid the LM-head work for greedy
verification. To prove a draft token is the greedy token, the verifier still
needs the true max over the vocabulary unless there is a separate exact bound.
The current stack already uses `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`, which
avoids host raw-logit extraction and CPU vocab scans. Prior
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` runs were also slower on this stack,
so do not rerun that path as-is.

### Router Materialization / MoE Fusion

The relevant graph insertion point is `llm_graph_context::build_moe_ffn()` in
`/home/steve/src/llama.cpp-gemma-record-stack/src/llama-graph.cpp`, around the
selected-expert and selected-weight materialization block.

For Gemma4 selected-softmax mode:

- router logits are F32 `[128, n_tokens]`;
- selected expert IDs are I32 `[8, n_tokens]`;
- selected weights are F32 `[1, 8, n_tokens]`;
- downstream `mul_mat_id` and weighted-sum/fused-down paths consume IDs and
  weights separately.

Because ordinary ggml ops are single-output, a clean `top_k + selected-softmax`
fusion cannot emit both IDs and weights without either unsafe side effects or a
deeper fused op. The defensible larger design is a Gemma4-only small-token MoE
op that outputs `[n_embd, n_tokens]` directly, fusing router selection,
selected-softmax, gate/up, GEGLU, down, and weighted sum under tight guards:

- `arch == LLM_ARCH_GEMMA4`;
- selected-softmax / `SOFTMAX_WEIGHT` gating;
- `n_expert == 128`, `n_expert_used == 8`;
- verifier-sized `n_tokens <= 8`;
- no LoRA, no expert bias/group path;
- supported Q8 target layouts only.

## Next Bias

The cheap router combo lost. Stop cheap Gemma flag sweeps and start a bounded
design note / prototype plan for the deeper single-output Gemma4 small-token MoE
op. That is the next credible path toward `>150 tok/s`; repeated
sampler/logit-output/fused-down/router-materialization flags are already covered
and below the current `103.299 tok/s` record.

## 2026-06-26T16:19Z Fused Selected-Softmax Weighted-Sum Screen

Prototype:
`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1` on top of the current record
stack (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
`LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`, MTP `n_max=7`, `p_min=0.136`).

Intent: fuse the final selected-softmax + weighted-sum aggregation around the
existing down-projection output, without changing target/draft quality or
headline validity. This was the bounded next step after the cheap router and
fused-down toggles lost.

Result:

- summary:
  `data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-fusedagg-pmin0136-screen-20260626T161913Z/summary.json`
- canary: `512/512`, pass
- cached-token validity: `[0, 0, 0, 0]`, row0 is fresh-response eligible
- fresh row0: `100.3584163628206 tok/s` after TTFT
- repeated-row mean: `101.70347410674582 tok/s` after TTFT, support-only
- decision: reject / do not promote. Correct, but slower than the valid
  `103.2992004295621 tok/s` record.

Interpretation: this isolated final aggregation fusion is not enough. It likely
saves a small materialization/softmax path but adds a custom kernel launch and
does not reduce the dominant target/draft forward cost. The next credible path
is still a deeper Gemma4 small-token MoE fusion that removes more of the
gate/up/activation/down/weighted-sum path together, or a separate MTP acceptance
improvement that increases fresh accepted tokens per step without learned
history.
