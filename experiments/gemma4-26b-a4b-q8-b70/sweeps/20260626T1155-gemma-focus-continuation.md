# 2026-06-26 11:55 - Gemma Focus Continuation

## Context

Gemma 4 26B A4B Q8 remains the active priority. MiniMax TP4 may be repaired
later, but it should not consume the main optimization lane while Gemma still
has plausible source-level work.

Current valid Gemma best is now:

- `103.30108468098005 tok/s` fresh row0 after TTFT;
- `cached_tokens=0`;
- `1536/1536` chat canary;
- LocalMaxxing `cmqvalync02lhqr01h76rnti3`;
- micro-record over the previous `103.2992004295621 tok/s` row, not a
  material breakthrough;
- evidence:
  `data/gemma4-q8-gpu0-mulmatid-routecache-full-20260626T184617Z/summary.json`.

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
     correct but still below the `103.299-103.301 tok/s` record band.

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
and below the current `103.299-103.301 tok/s` record band.

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

## 2026-06-26T16:25Z Narrow `p_min` Follow-Up

After the fused aggregation loss, three one-GPU scalar screens checked whether
the current record lane had an adjacent `p_min` win. All used the current record
identity (`n_max=7`, `n_min=2`, Q8 target, Q4_0 draft, selected-softmax,
weighted-sum, q-only MTP inputs, backend verifier argmax IDs, deferred
`h_nextn`, `--ctx-checkpoints 0`). All benchmark rows reported
`cached_tokens=0`, so row0 remains fresh-response eligible.

| Run | `p_min` | Canary | Fresh row0 tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu1-pmin01362-screen-20260626T162554Z/summary.json` | `0.1362` | `512/512` | `100.00594304849302` | valid loss |
| `data/gemma4-q8-gpu2-pmin01364-screen-20260626T162554Z/summary.json` | `0.1364` | `512/512` | `100.11375932284292` | valid loss |
| `data/gemma4-q8-gpu3-pmin01368-screen-20260626T162554Z/summary.json` | `0.1368` | `512/512` | `101.59422926511867` | valid loss |

The GPU0 `p_min=0.136` control launched at the same time but stuck during
model-fitting / load before producing canary or benchmark output and was killed.
It produced no summary and should not be treated as a result.

Decision: this supports the MTP audit conclusion that the current recipe is not
acceptance-limited. Avoid more scalar `p_min` sweeps unless a source change
changes the acceptance/cost curve.

## 2026-06-26T17:21Z GEGLU Down Matmul-Epilogue Prototype

Prototype:
`LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1`, emitted through the Gemma4
GEGLU fused-down graph path but implemented as:

1. pack routed GEGLU activations into contiguous rows;
2. reuse the tuned per-expert Q8_0 `mul_mat` schedule;
3. fuse the final route scatter, down-scale, and weighted sum epilogue.

This was intended as an intermediate step toward the deeper single-output
Gemma4 small-token MoE fusion without writing the full monolithic op.

Implementation finding:

- First startup failed with
  `GGML_OP_MOE_GEGLU_SELECTED_DOWN_WEIGHTED_SUM is backend-only` because the
  fused GEGLU op was placed on CPU.
- A diagnostic support guard showed the real shape was valid, but `ids` was a
  strided I32 view: `ids ne=[8,2] nb=[4,512]`, not contiguous.
- The helper was updated to allow strided `ids`: copy the covered device span,
  pack a dense host id matrix for route sorting/profile accounting, and keep the
  original device `ids` plus original strides for the final device epilogue.
- After that, the server reached canaries and benchmark execution.

Result:

- summary:
  `data/gemma4-q8-gpu0-geglu-down-matmul-epilogue-short-pmin0136-20260626T172132Z/summary.json`
- canary: `32/32` repeats (`128` rows), pass
- cached-token validity: `[0, 0, 0, 0]`, row0 is fresh-response eligible
- fresh row0: `46.15915016610455 tok/s` after TTFT
- repeated-row mean: `47.29437104441836 tok/s` after TTFT, support-only
- decision: reject / do not promote. Correct in the screen, but much slower
  than the valid `103.2992004295621 tok/s` record.

Interpretation: decomposing GEGLU into a route-pack plus per-expert matmul keeps
correctness but is launch/host-sort heavy and loses most of the benefit of the
current selected-softmax + weighted-sum lane. Do not spend full validation time
on this exact route. The useful artifact is the strided-`ids` support discovery
for any future fused GEGLU backend-only op.

## 2026-06-26T17:51Z Exact-Node `MUL_MAT_ID` Fast-Path Filter

Patch under test: add default-off
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NAME_SUBSTR`, checked inside
`ggml_sycl_mul_mat_id_multi_token_filter_allows()`, so the existing
multi-token `MUL_MAT_ID` fast paths can be scoped to one profiled node name
instead of broad classes like all `gate_up` or all `down` nodes.

Reason: the detailed node profile showed `MUL_MAT_ID:ffn_moe_gate_up-0` as the
single hottest node (`~2.53 ms/call`, 53 calls). Earlier broad `gate_up` /
`down` fast-path screens regressed, but exact-node targeting had not been
tested.

All screens below used the current record identity (`n_max=7`, `n_min=2`,
`p_min=0.136`, Q8 target, Q4_0 MTP draft, selected-softmax, weighted-sum,
q-only MTP inputs, backend verifier argmax IDs, deferred target `h_nextn`,
direct draft argmax IDs, `--ctx-checkpoints 0`). All passed 32 canary repeats
(`128` case rows), reported `cached_tokens=0`, and are fresh-row0 eligible.

| Run | Extra env | Fresh row0 tok/s | Decision |
| --- | --- | ---: | --- |
| `data/gemma4-q8-gpu0-mulmatidfast-gateup0-namesubstr-screen-20260626T175110Z/summary.json` | `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`, `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NAME_SUBSTR=ffn_moe_gate_up-0` | `99.58440630277339` | valid loss |
| `data/gemma4-q8-gpu0-mulmatidfast-gateup0-grouped-screen-20260626T175257Z/summary.json` | plus `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0=1` | `100.16927670537243` | valid loss |
| `data/gemma4-q8-gpu1-mulmatidfast-gateup0-perslot-screen-20260626T175257Z/summary.json` | plus `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_PER_SLOT_Q8_0=1` | `101.221389918208` | valid loss |

Decision: reject / do not promote for performance. The exact filter itself is a
useful diagnostic knob and can remain default-off, but the `ffn_moe_gate_up-0`
fast-path variants do not beat the valid `103.2992004295621 tok/s` record.
Avoid expanding this into a broad layer/name sweep unless a later profile shows
a changed hotspot distribution.

## 2026-06-26T18:05Z Strided-ID Fused Selected Softmax Weighted Sum

Patch under test: relax the graph/backend guards for
`GGML_OP_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM` so the existing fused
selected-softmax + weighted-sum SYCL kernel can accept strided expert IDs. The
kernel already takes `ids_nb0` / `ids_nb1`, so this aligns the guards with the
implementation instead of forcing `ggml_is_contiguous(ids)`.

Guard relaxations:

- `src/llama-graph.cpp`: allow `selected_experts->nb[0] == sizeof(int32_t)`,
  `selected_experts->nb[1] % sizeof(int32_t) == 0`, and non-transposed IDs
  instead of requiring full contiguity.
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: same support-guard relaxation for
  `GGML_OP_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM`.

Run:

- summary:
  `data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-stridedids-screen-20260626T180548Z/summary.json`
- canary: `32/32` repeats (`128` rows), pass
- cached-token validity: `[0, 0]`, row0 is fresh-response eligible
- fresh row0: `102.36018628889175 tok/s` after TTFT
- wall row0: `89.28643807246222 tok/s`
- repeated-row mean: `102.3606235488539 tok/s` after TTFT, support-only
- server log only confirms the env switches; it does not emit per-op placement
  for the fused op.

Decision: reject / do not promote as a record. Correct and very close, but still
below the valid `103.2992004295621 tok/s` headline. The guard relaxation remains
a useful default-off diagnostic / enabling patch for future fused-MoE work, but
it is not enough by itself to move the record.

Next implied action: stop revisiting selected-softmax/top-k/name-filter screens
unless a new source change changes the MoE cost curve. The remaining meaningful
Gemma lane is a larger verifier-side small-token MoE fusion or an exact
shape-specific Q8_0 expert kernel that reduces the target/verifier MoE cost,
not more scalar launch-flag sweeps.

## 2026-06-26T18:18Z Strided-ID Selected-Down Matmul-Epilogue

Patch under test: extend the default-off Gemma4 fused selected-down path so
`GGML_OP_MOE_SELECTED_DOWN_WEIGHTED_SUM` can reach the existing
`LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_MATMUL_EPILOGUE=1` backend when
expert IDs are strided.

Changes:

- `src/llama-graph.cpp`: relax the fused selected-down graph guard from
  `ggml_is_contiguous(selected_experts)` to non-transposed I32 IDs with
  `nb[0] == sizeof(int32_t)` and `nb[1] % sizeof(int32_t) == 0`.
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: relax the SYCL support guard the same
  way.
- `ggml_sycl_moe_selected_down_weighted_sum_matmul_epilogue()`: copy the
  covered ID span, densify IDs on host for route sorting/profile accounting,
  and keep the original device ID pointer plus original strides for the final
  device epilogue. This mirrors the already-working strided-ID handling in the
  GEGLU matmul-epilogue prototype.

Screens:

| Run | Extra env | Canary | Fresh row0 tok/s | Decision |
| --- | --- | --- | ---: | --- |
| `data/gemma4-q8-gpu0-selecteddown-matmul-epilogue-stridedids-screen-20260626T181834Z/summary.json` | `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM=1`, `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_MATMUL_EPILOGUE=1`, debug on | `128/128` | `102.82922518638489` | valid loss |
| `data/gemma4-q8-gpu0-selecteddown-matmul-epilogue-skipweights-stridedids-screen-20260626T182028Z/summary.json` | same plus `LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND=1`, debug off | `128/128` | `100.69151522542195` | valid loss |
| `data/gemma4-q8-gpu0-selecteddown-matmul-epilogue-stridedids-clean-screen-20260626T182204Z/summary.json` | same as first, debug off | `128/128` | `100.98858879531659` | valid loss |

All three runs reported `cached_tokens=0` for benchmark rows and are
fresh-row0 eligible. None beats the valid `103.2992004295621 tok/s` record.

Decision: do not promote as a speed result. The patch is a useful default-off
enabler/diagnostic for strided-ID selected-down work and should be kept as an
experiment artifact, but this matmul-epilogue backend is not the current record
path. `SKIP_EARLY_WEIGHTS_EXPAND` is specifically negative here.

Interpretation: the selected-down matmul-epilogue design still pays too much
route sorting / packing overhead relative to the existing record stack. The
remaining meaningful work is not another selected-down wrapper around existing
per-expert matmul; it is either a truly shape-specific target MoE kernel for
the verifier shapes or a different verifier shortcut that reduces target
`process_ubatch` work.

## 2026-06-26T18:44Z MUL_MAT_ID Route-Cache Screen

Patch under test: add a default-off host route cache for multi-token
`GGML_OP_MUL_MAT_ID` in the SYCL backend, enabled by
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`.

Hypothesis: the current record stack still executes the generic target/verifier
MoE route packer more than once for the same selected-expert IDs. Reusing the
immediately previous `ids` host copy / counting-sort / row mapping for the
following matching `MUL_MAT_ID` op might remove duplicate host waits and route
sorting without changing model math.

Implementation shape:

- default-off env gate, no behavior change unless explicitly enabled;
- cache matches the same `ids` tensor pointer, data pointer, shape, strides,
  routed-row count, and byte span;
- cache clears on hit so it is only reused for the immediate matching op and
  cannot persist across decode steps where the pointer can stay stable while
  contents change.

Screen run:

- summary:
  `data/gemma4-q8-gpu0-mulmatid-routecache-screen-20260626T184446Z/summary.json`
- canary: `32/32` repeats (`128` rows), pass
- cached-token validity: `[0, 0]`, row0 is fresh-response eligible
- fresh row0: `103.42820086552045 tok/s` after TTFT
- wall row0: `90.18501516643299 tok/s`
- repeated-row mean: `102.37260866976813 tok/s` after TTFT, support-only
- previous valid record: `103.2992004295621 tok/s`

Full validation:

- summary:
  `data/gemma4-q8-gpu0-mulmatid-routecache-full-20260626T184617Z/summary.json`
- canary: `384/384` repeats (`1536` rows), pass
- cached-token validity: `[0, 0, 0, 0, 0, 0, 0, 0]`, row0 is
  fresh-response eligible
- fresh row0: `103.30108468098005 tok/s` after TTFT
- wall row0: `89.97733776184405 tok/s`
- repeated-row mean: `103.06255061691155 tok/s` after TTFT, support-only
- previous valid record: `103.2992004295621 tok/s`
- delta: `+0.00188425141795 tok/s`
- LocalMaxxing: approved as `cmqvalync02lhqr01h76rnti3`
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626.queue.json`
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626.submit.log`

Decision: valid micro-record, but not material progress. Preserve the patch and
result because it proves the route-cache is correctness-safe and slightly
positive; do not spend more Gemma time on scalar host route-cache refinements.
The remaining performance bottleneck is still target/verifier MoE work.
