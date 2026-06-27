# 2026-06-26 11:55 - Gemma Focus Continuation

## Context

Gemma 4 26B A4B Q8 remains the active priority. MiniMax TP4 may be repaired
later, but it should not consume the main optimization lane while Gemma still
has plausible source-level work.

Current valid Gemma best is now:

- `103.95374341972274 tok/s` fresh row0 after TTFT;
- `104.13506066488091 tok/s` supporting repeated-request mean;
- `cached_tokens=0`;
- `1536/1536` chat canary;
- LocalMaxxing `cmqviful602p0qr01vp27jw5i`;
- micro-record over the previous `103.51547512013657 tok/s` route-cache row,
  not a material breakthrough;
- evidence:
  `data/gemma4-q8-gpu2-routecache-mtpfusedoutargmax-selfusedweights-full-20260626T222525Z/summary.json`.

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

## 2026-06-26T20:05Z GEGLU Matmul-Epilogue Route-Cache Consumer

Patch under test: extend the existing one-shot
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1` host route-plan reuse into the two down
matmul-epilogue consumers, especially
`LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1`. The intent was metadata-only:
reuse the immediately preceding gate/up `MUL_MAT_ID` route plan instead of
copying strided `ids` to host and rebuilding expert counts/offsets for the down
epilogue. Arithmetic stayed on the same Q8 down matmul/epilogue path.

Initial screen looked promising:

- `data/gemma4-q8-gpu2-geglu-epilogue-routecache-screen-20260626T195205Z/summary.json`
- canary: `128/128`, pass
- cached-token validity: `[0, 0]`, row0 fresh-response eligible
- fresh row0: `104.70795597094846 tok/s`
- support mean: `104.25250585801564 tok/s`

Full validation rejected it:

- `data/gemma4-q8-gpu2-geglu-epilogue-routecache-full-20260626T195349Z/summary.json`
- canary: `1536/1536`, pass
- cached-token validity: eight rows all `0`
- fresh row0: `101.8211074778421 tok/s`
- support mean: `102.70197770331635 tok/s`

Decision: reject / do not promote / do not submit to LocalMaxxing. The screen
was variance. The full gate is below the current promoted
`103.51547512013657 tok/s` record. Preserve the patch idea and result as a
negative artifact, but keep the active source stack on the known-good route-cache
recipe unless a larger fused-MoE change needs this route-plan reuse again.

Decision for the exact-node `MUL_MAT_ID` fast-path filter: reject / do not
promote for performance. The exact filter itself is a useful diagnostic knob
and can remain default-off, but the `ffn_moe_gate_up-0` fast-path variants do
not beat the valid `103.51547512013657 tok/s` record.
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
compute.

## 2026-06-26T22:20Z Direct-Unroll Depth Sweep On Route-Cache Record Stack

Question: can Gemma4 Q8 break out of the ~103 tok/s band by increasing MTP
direct-unroll depth beyond the current `n_max=7` record recipe?

Current source audit confirmed that `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL` is a
real single-`llama_decode(ctx_dft, ...)` graph unroll for the Gemma4 assistant,
not only a sampler/output-copy shortcut. The assistant graph chains each sampled
token into the next internal MTP step and concatenates sampled IDs. Therefore
larger `n_max` values are a legitimate throughput experiment, not a no-op.

All runs used the current Q8 route-cache record identity except for
`--spec-draft-n-max` / `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL`. All passed
32 chat-canary repeats (`128` rows), reported `cached_tokens=0`, and are
fresh-row0 eligible.

| Run | Depth | Fresh row0 tok/s | Support mean tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-routecache-depthn6-screen-20260626T222018Z/summary.json` | 6 | `95.55580165915312` | `96.11208142072961` | valid loss |
| `data/gemma4-q8-gpu1-routecache-depthn8-screen-20260626T222018Z/summary.json` | 8 | `66.46195714907394` | `66.42095566261824` | valid loss |
| `data/gemma4-q8-gpu2-routecache-depthn9-screen-20260626T222018Z/summary.json` | 9 | `70.69767490830706` | `70.7292565692439` | valid loss |
| `data/gemma4-q8-gpu3-routecache-depthn10-screen-20260626T222018Z/summary.json` | 10 | `74.80440647496813` | `74.84375573606496` | valid loss |

Interpretation: depth is not the remaining path to `>150 tok/s` in this
implementation. Larger unrolls do accept deeper drafts on the benchmark rows
(for example `n=10` accepted `462/488` generated on row0), but the expanded
assistant graph cost grows faster than accepted-token savings. `n=6` also loses,
so the existing `n=7` route-cache recipe remains the local optimum. Do not rerun
simple `n_max > 7` depth sweeps unless a source patch materially reduces the
assistant unroll graph cost.

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

## 2026-06-26T19:09Z Early Selected-Softmax Weights For GEGLU Down

Patch under test: when `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1` and a
GEGLU selected-down backend is explicitly requested, materialize selected
softmax weights before the activation/down block instead of setting
`weights=nullptr`. This lets
`ggml_moe_geglu_selected_down_weighted_sum()` fire for the combined
selected-softmax-weighted-sum lane.

Reason: the current combined selected-softmax-weighted-sum path normally fuses
only after `ffn_moe_down` already exists. The earlier GEGLU selected-down path
requires `weights != nullptr`; without this patch, the combined selected-softmax
path cannot exercise it.

Run:

- summary:
  `data/gemma4-q8-gpu0-selectedsoftmaxws-gegludown-earlyweights-routecache-screen-20260626T190911Z/summary.json`
- env deltas:
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1`,
  `LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`
- canary: `32/32` repeats (`128` rows), pass
- cached-token validity: `[0, 0]`, row0 is fresh-response eligible
- fresh row0: `100.92860408939487 tok/s` after TTFT
- wall row0: `88.30958095057842 tok/s`
- repeated-row mean: `100.88521816690852 tok/s` after TTFT, support-only
- current record: `103.30108468098005 tok/s`

Decision: reject / do not promote. Correct, but slower than both the
route-cache micro-record and the prior `103.2992004295621 tok/s` material
baseline. This confirms that routing through the GEGLU selected-down
matmul-epilogue backend remains a loss even when selected-softmax weights are
available early. Preserve the source patch as a negative / enabling artifact,
but do not spend more time on this exact GEGLU-down family.

## 2026-06-26T20:27Z MoE Weighted-Sum 2D Launch

Patch under test: add default-off
`LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D=1` to route `GGML_OP_MOE_WEIGHTED_SUM`
through a 2D `token x row` SYCL `parallel_for` instead of the current flattened
1D kernel. Semantics are identical: same expert tensor, same weights, same
strides, same per-row sum. The intended win was removing per-output
`idx / n_embd` and `idx % n_embd` integer work in the accepted MoE path.

Harness fix made before promotion attempts:

- `scripts/run-gemma4-26b-first-baseline.sh` now records
  `llama_gemma4_moe_weighted_sum_2d` in `summary.json`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh` now prints
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D` in server launch logs.

Screen / variance scan:

- `data/gemma4-q8-gpu2-moe-weightedsum-2d-screen-20260626T202719Z/summary.json`
  - canary `128/128`, cached tokens `[0, 0]`
  - fresh row0 `103.5435126657234 tok/s`
  - support mean `102.539530590951 tok/s`
- `data/gemma4-q8-gpu0-moe-weightedsum-2d-screen-20260626T202959Z/summary.json`
  - canary `128/128`, cached tokens `[0, 0]`
  - fresh row0 `101.35034097096046 tok/s`
  - support mean `102.34984602482261 tok/s`
- `data/gemma4-q8-gpu1-moe-weightedsum-2d-screen-20260626T202959Z/summary.json`
  - canary `128/128`, cached tokens `[0, 0]`
  - fresh row0 `101.48255322931645 tok/s`
  - support mean `102.3812573687189 tok/s`
- `data/gemma4-q8-gpu3-moe-weightedsum-2d-screen-20260626T202959Z/summary.json`
  - canary `128/128`, cached tokens `[0, 0]`
  - fresh row0 `102.99795406628424 tok/s`
  - support mean `102.08773488585275 tok/s`

Full validation:

- `data/gemma4-q8-gpu2-moe-weightedsum-2d-full-20260626T202959Z/summary.json`
- canary: `384/384` repeats (`1536` rows), pass
- cached-token validity:
  `[0, 0, 0, 0, 0, 0, 0, 0]`, row0 is fresh-response eligible
- fresh row0: `103.5104909373625 tok/s`
- support mean: `103.26493464181871 tok/s`
- support median: `103.42693492994971 tok/s`
- then-current record: `103.51547512013657 tok/s`
- delta vs headline: `-0.00498418277407 tok/s`

Decision: reject / do not promote / do not submit to LocalMaxxing. The first
GPU2 screen was variance; the full run missed the fresh-response row0 record
and other GPUs screened lower. The patch is quality-safe and default-off, but
not a demonstrated speed win. Do not enable
`LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D` in the promoted Q8 recipe unless a future
change makes weighted-sum launch shape newly relevant.

## 2026-06-26T20:52Z Current Record Profile

## 2026-06-26T23:50Z Route-Cache Device-Map Negative

Patch under test: extend the one-shot
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1` path with a default-off persistent device
row-mapping cache, enabled by
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_DEVICE_MAP=1`.

Reason: the source audit found that a route-cache hit still rebuilt/copy-backed
the routed row map for the immediately following matching `MUL_MAT_ID`. The
patch preserved the existing host route-cache semantics but let the following
op reuse a persistent device `mmid_row_mapping` buffer when the immediate cache
hit matched. This was intended to remove one device copy on the gate/up -> down
pair without changing math.

Result:

- summary:
  `data/gemma4-q8-gpu0-routecache-devmap-screen-20260626T235013Z/summary.json`
- canary: `128` repeats / `512` case rows, pass
- cached-token validity: `[0, 0, 0, 0]`, row0 fresh-response eligible
- fresh row0: `103.5829642508525 tok/s`
- support mean: `103.71749944929736 tok/s`
- then-current record: `103.9826628154082 tok/s`

Decision: reject as a speed result. Correct but below record. Keep the patch as
a default-off experiment artifact because it is a targeted diagnostic for the
route-cache/MoE metadata path, but do not enable it in promoted recipes. The
result suggests the remaining bottleneck is not this final device row-map copy.

## 2026-06-26T23:54Z Runtime Shape Four-GPU Screen

Four independent single-GPU screens checked whether simple context/batch shapes
could find a small win on the current route-cache/fused-output/fused-selected-
softmax record stack. All rows below passed canary, reported `cached_tokens=0`,
and are row0 fresh-response eligible. The earlier `20260626T233608Z` shape
attempt was backgrounded incorrectly and produced no meaningful results; ignore
those empty/incomplete dirs.

| Run | Runtime delta | Fresh row0 tok/s | Support mean tok/s | Decision |
| --- | --- | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-shape-ctx4096-screen-20260626T235411Z/summary.json` | `CTX_SIZE=4096` | `102.096146` | `103.619245` | valid loss |
| `data/gemma4-q8-gpu1-shape-ctx6144-screen-20260626T235411Z/summary.json` | `CTX_SIZE=6144` | `101.550616` | `103.060854` | valid loss |
| `data/gemma4-q8-gpu2-shape-b1536u1024-screen-20260626T235411Z/summary.json` | `BATCH_SIZE=1536`, `UBATCH_SIZE=1024` | `102.170273` | `103.401719` | valid loss |
| `data/gemma4-q8-gpu3-shape-b1024u768-screen-20260626T235411Z/summary.json` | `BATCH_SIZE=1024`, `UBATCH_SIZE=768` | `104.632994` | `103.559456` | promote to full validation |

## 2026-06-27T00:29Z UBATCH=768 Full Validation / Micro-Record

Full validation promoted the `UBATCH_SIZE=768` screen on GPU3:

- summary:
  `data/gemma4-q8-gpu3-b1024u768-fullrepeat-20260626T235649Z/summary.json`
- p512/o512 raw benchmark:
  `data/gemma4-q8-gpu3-b1024u768-fullrepeat-20260626T235649Z/p512o512.json`
- canary: `1536` repeats / `6144` case rows, pass
- cached-token validity:
  `[0, 0, 0, 0, 0, 0, 0, 0]`, row0 fresh-response eligible
- fresh row0: `104.07050714456982 tok/s`
- wall row0: `90.4869993907642 tok/s`
- support mean: `103.588578767931 tok/s`
- support median: `104.0494971181019 tok/s`
- prior valid record: `103.9826628154082 tok/s` row0,
  `104.09604904731648 tok/s` support mean
- LocalMaxxing: approved as `cmqvmjvzx02qvqr01qh9jikow`
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-fresh-20260627.queue.json`
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-fresh-20260627.submit.log`

Decision: valid fresh-response row0 micro-record, but not material progress.
The prior record's support mean was higher, and the new gain is only
`+0.08784432916162 tok/s` on the headline row. Treat `UBATCH_SIZE=768` as the
current published row0 recipe, but keep `UBATCH_SIZE=1024` as the same-family
control because it remains at least as strong by support mean.

Next implication: do not read this as a new optimization mechanism. The Gemma
frontier is still verifier/target MoE cost and MTP assistant graph cost. The
most credible next work remains a deeper small-token Gemma4 MoE fusion or a
different fresh-request speculation method that increases accepted tokens per
step without warmed/history reuse.

Diagnostic profile of the current promoted route-cache recipe:

- summary:
  `data/gemma4-q8-gpu2-routecache-profile-current-20260626T205222Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu2-routecache-profile-current-20260626T205222Z.server.log`
- env deltas:
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_PROFILE=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_PROFILE_EVERY=50`,
  `GGML_SYCL_NODE_PROFILE=1`, `LLAMA_MTP_DRAFT_PROFILE=1`
- canary: `8/8` repeats (`32` rows), pass
- cached-token validity: `[0]`, row0 fresh-response eligible
- fresh row0 under profiling: `79.69891891516477 tok/s` after TTFT

This is **not** a headline speed result because node/route profiling adds
overhead. Its value is hotspot direction:

- target `process_ubatch_ms=17780.627` of `target total_ms=17794.513`; target
  process dominates;
- draft decode was much smaller (`draft_decode_ms=1643.053`);
- acceptance was already high: `445 accepted / 462 generated`, mean
  acceptance `7.74`, per-position `(1.000, 0.985, 0.970, 0.955, 0.955, 0.939,
  0.939)`;
- hottest profiled nodes included:
  `MUL_MAT:result_output` total `355.442`,
  `MUL_MAT_ID:ffn_moe_gate_up-0` total `333.604`,
  target LM head `MUL_MAT:node_2255` total `297.711`,
  and `MUL_MAT_ID:node_64` down total `189.670`.

Interpretation: the remaining useful work is target/verifier compute reduction
(especially target MoE gate/up and LM-head path), not more acceptance/p-min
tuning or route-cache-only metadata tweaks. The following gate/up seeded
route-cache experiment tested one bounded consequence of this profile and lost.

## 2026-06-26T21:05Z Gate/Up Fast Path Seeding Route Cache

Patch under test: add default-off
`LLAMA_SYCL_MUL_MAT_ID_GATE_UP_FAST_SEED_ROUTE_CACHE=1`.

Intent: let the verifier-sized `ffn_moe_gate_up-*` `MUL_MAT_ID` nodes use the
existing direct multi-token Q8 fast path while preserving the current record
down path. Before launching the gate/up fast path, the patch builds the same
host route metadata used by `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1` so the
following `ffn_moe_down` can still consume the normal cached route plan. This
was materially different from the earlier broad/exact-node fast-path losses
because it did not force the down projection onto the fast path.

Run:

- summary:
  `data/gemma4-q8-gpu2-gateupfast-seedroute-screen-20260626T210513Z/summary.json`
- env deltas:
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`,
  `LLAMA_SYCL_MUL_MAT_ID_GATE_UP_FAST_SEED_ROUTE_CACHE=1`
- canary: `96/96` repeats (`384` rows), pass
- cached-token validity: `[0, 0, 0, 0]`, row0 is fresh-response eligible
- fresh row0: `76.68309224299286 tok/s` after TTFT
- support mean: `76.5484238319723 tok/s` after TTFT, support-only
- then-current record: `103.51547512013657 tok/s`

Decision: reject / do not promote / do not submit to LocalMaxxing. The canary
is clean, but throughput collapses. The host ID copy / route seeding wait and
loss of graph eligibility are far more expensive than any gate/up fast-path
savings. This closes the route-cache-seeded gate/up fast-path lane as tested.
Avoid retrying this exact design unless it can seed the cache without a host
wait or without disrupting the current graph path.

## 2026-06-26T21:16Z Draft Logit-Gap Gate Control

Screen intent: test `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN` on top of the current
promoted route-cache Q8 recipe. This gate stops drafting when the MTP draft
top-1/top-2 logit margin is small.

Important correction: the current promoted recipe uses
`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`. In that mode
`draft_sampled_argmax_sample()` returns only one candidate, so the
`cur_p->size > 1` guard prevents the logit-gap check from firing. These runs
are still valid fresh-response controls for the current direct-argmax recipe,
but they are **not** a functional logit-gap experiment. The functional top-k
logit-gap lane was already tested earlier via `LLAMA_MTP_DRAFT_FAST_TOPK=1`
and lost badly (~90 tok/s; see
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1447-draft-topk-logitgap.md`).

All runs used the current record identity (`n_max=7`, `n_min=2`,
`p_min=0.136`, Q8 target, Q4_0 MTP draft, selected-softmax, weighted-sum,
q-only MTP inputs, backend verifier argmax IDs, deferred target `h_nextn`,
direct draft argmax IDs, `--ctx-checkpoints 0`, `filled-long` prompt).
All runs passed `32` canary repeats (`128` rows), reported `cached_tokens=0`,
and are fresh-row0 eligible.

| Run | `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN` | Fresh row0 tok/s | Support mean tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-routecache-logitgap015-screen-20260626T211613Z/summary.json` | `0.15` | `101.24881584728219` | `102.32779100687304` | valid loss |
| `data/gemma4-q8-gpu1-routecache-logitgap030-screen-20260626T211613Z/summary.json` | `0.30` | `103.38700795434751` | `103.26669953373366` | valid loss |
| `data/gemma4-q8-gpu2-routecache-logitgap050-screen-20260626T211613Z/summary.json` | `0.50` | `101.17041116344521` | `102.10724105547375` | valid loss |
| `data/gemma4-q8-gpu3-routecache-logitgap075-screen-20260626T211613Z/summary.json` | `0.75` | `101.22299490741584` | `102.70252959158722` | valid loss |

Decision: reject / do not promote / do not submit to LocalMaxxing. The best
fresh row0 (`103.387`) is close but still below the current valid record
(`103.51547512013657`), and the intended gap gate did not execute because the
direct-argmax path emits no top-2 candidate. Do not repeat this exact screen.
If logit-gap gating is revisited, it must use a top-k draft path, but prior
top-k/logit-gap results were far slower than the current direct-argmax record.
The next credible Gemma lane is a verifier-only source change that reduces
target compute, especially around the small-token Gemma4 MoE path or an exact
bounded candidate LM-head argmax.

## 2026-06-26T21:47Z Q8 Gate/Up GEGLU Fused Op

Patch under test: add backend-only `GGML_OP_MOE_Q8_0_GATEUP_GEGLU`, enabled by
`LLAMA_GEMMA4_MOE_GATEUP_GEGLU=1`, and use it in the strict Gemma4/Q8
small-batch MoE graph to replace:

```text
MUL_MAT_ID(gate_up) -> split gate/up -> GEGLU
```

The op quantizes the current hidden row to Q8_1 once, dots selected Q8_0 gate
and up expert rows, applies the per-expert scale to both halves, and writes the
F32 GEGLU output shaped `[n_ff, n_expert_used, n_tokens]`. The down projection
and final weighted sum stayed on the current route-cache recipe.

Run:

- summary:
  `data/gemma4-q8-gpu2-gateup-geglu-screen-20260626T214732Z/summary.json`
- env deltas:
  `LLAMA_GEMMA4_MOE_GATEUP_GEGLU=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`
- canary: `32/32` repeats (`128` rows), pass
- cached-token validity: `[0, 0]`, row0 is fresh-response eligible
- fresh row0: `84.21460316143335 tok/s` after TTFT
- support mean: `84.22833614279985 tok/s` after TTFT, support-only
- then-current record: `103.51547512013657 tok/s`

Decision: reject / do not promote / do not submit to LocalMaxxing. This is a
correct but substantial loss. Replacing the existing route-cache `MUL_MAT_ID`
gate/up path with a naive fused dot+GEGLU op reduces graph/node count but loses
the tuned math path. Preserve the env-gated patch as a dead-end artifact. Future
MoE fusion should target a larger single-output MoE boundary or improve the
route-cache `MUL_MAT_ID` path directly, not retry this exact gate/up-only op.

## 2026-06-26T22:09Z Route-Cache In-Place Fill

Patch under test: add a default-off
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE=1` path in generic
`ggml_sycl_mul_mat_id()` route-cache misses. Instead of building local host
route vectors and then copying them into the one-shot cache, the in-place path
copies `ids` directly into `route_cache.ids_host`, sorts directly into
`route_cache.expert_row_counts`, `route_cache.expert_row_offsets`, and
`route_cache.routed_row_src`, and points the current op at that storage. The
current tuned `MUL_MAT_ID` math path and the existing one-shot hit/clear cache
semantics are unchanged.

Run:

- summary:
  `data/gemma4-q8-gpu2-routecache-inplace-screen-20260626T220930Z/summary.json`
- patch note:
  `patches/gemma4-26b-a4b-q8-b70/20260626T2209-routecache-inplace-fill-loss.md`
- env deltas:
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE=1`
- canary: `128` repeats (`512` rows), pass
- cached-token validity: `[0, 0, 0]`, row0 is fresh-response eligible
- fresh row0: `101.52759496160394 tok/s` after TTFT
- support mean: `102.83917018605882 tok/s` after TTFT
- support max: `103.50911695639134 tok/s` after TTFT, support-only
- then-current record: `103.51547512013657 tok/s`

Decision: reject / do not promote / do not submit to LocalMaxxing. This is a
correct but non-winning micro patch. The remaining local-vector-to-cache copies
are not a meaningful bottleneck in the current Q8/MTP record path. Preserve the
env-gated source patch as an experiment artifact, but leave it off in promoted
recipes. Future Gemma work should move to verifier-side compute reductions
(larger small-token Gemma4/Q8 MoE boundary or a better target LM-head top-1
kernel), not another route-cache metadata tweak.

## 2026-06-26T22:23Z Route-Cache Cleanup Screens

Purpose: test whether small default-off cleanup patches around the current
route-cache recipe add up when stacked. These are not strategic `>150 tok/s`
ideas; they were a quick four-GPU screen after the larger depth and MoE lanes
closed out.

All runs used the current route-cache recipe unless noted. All passed the chat
canary screen, reported `cached_tokens=0`, and are fresh-row0 eligible.

| Run | Extra flags | Fresh row0 tok/s | Support mean tok/s | Decision |
| --- | --- | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-routecache-control-screen-20260626T222330Z/summary.json` | control | `103.52953019944134` | `102.4893408968527` | valid control |
| `data/gemma4-q8-gpu1-routecache-mtpfusedoutargmax-screen-20260626T222330Z/summary.json` | `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` | `103.78358721993459` | `102.69988321623809` | valid micro-win screen |
| `data/gemma4-q8-gpu2-routecache-selfusedweights-screen-20260626T222330Z/summary.json` | `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1` | `103.23675527167006` | `103.19892367813154` | valid neutral/loss screen |
| `data/gemma4-q8-gpu3-routecache-mtpfusedoutargmax-selfusedweights-screen-20260626T222330Z/summary.json` | both flags | `103.80041150196647` | `102.97200085696608` | best screen; validate |

Interpretation: the assistant fused-output argmax shortcut can help slightly in
the route-cache stack, while fused selected-softmax weights alone is not a win.
The stacked recipe was close enough to the then-current
`103.51547512013657 tok/s` record to justify full validation.

## 2026-06-26T22:25Z Route-Cache Cleanup Full Validation

Full validation of the stacked screen:

- summary:
  `data/gemma4-q8-gpu2-routecache-mtpfusedoutargmax-selfusedweights-full-20260626T222525Z/summary.json`;
- env deltas over the route-cache recipe:
  `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`;
- canary: `384` repeats (`1536` rows), pass;
- cached-token validity: all benchmark rows report `cached_tokens=0`;
- fresh row0: `103.95374341972274 tok/s` after TTFT;
- support mean: `104.13506066488091 tok/s` after TTFT;
- first-row wall throughput: `90.68621473793526 tok/s`;
- LocalMaxxing: `cmqviful602p0qr01vp27jw5i`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-fresh-20260626.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-fresh-20260626.submit.log`.

Decision: promote as the current valid fresh-response one-B70 Q8-target
headline, and submit to LocalMaxxing. This is a small micro-record over
`103.51547512013657 tok/s`; it does **not** change the strategic conclusion
that cheap flags and depth sweeps are exhausted. Future Gemma progress toward
`>150 tok/s` needs a material verifier/speculation design change, most likely
around reducing target-side small-token Gemma4 MoE work or avoiding full-vocab
assistant/verifier overhead without violating fresh-response validity.

## 2026-06-26T22:50Z Current-Stack Node Profile Sanity Check

Diagnostic profile:

- summary:
  `data/gemma4-q8-gpu0-current-recordstack-nodeprofile-20260626T2250Z/summary.json`;
- server stdout:
  `data/gemma4-q8-gpu0-current-recordstack-nodeprofile-20260626T2250Z/server.stdout.log`;
- env deltas:
  `GGML_SYCL_NODE_PROFILE=1`,
  `GGML_SYCL_NODE_PROFILE_DETAIL=1`,
  `GGML_SYCL_NODE_PROFILE_EVERY=24`;
- current record-stack runtime flags included
  `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`, and
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`;
- canary: `2` repeats (`8` rows), pass;
- cached-token validity: `cached_tokens=0`;
- fresh row0: `76.03622268088938 tok/s` after TTFT, diagnostic only.

Do not treat this as a speed result: node profiling synchronizes and changes
runtime behavior. It is useful only for attribution. The current-stack hot-node
ranking remains consistent with earlier profiles:

- `MUL_MAT_ID:ffn_moe_gate_up-0` is the top node (`~2.5 ms/call`) with shape
  `src0=q8_0 [2816,1408,128]`, `src1=f32 [2816,1,2]`,
  `ids=i32 [8,2]`;
- target LM head (`MUL_MAT:node_2135`, `token_embd.weight q8_0
  [2816,262144]`) remains hot (`~2.13 ms/call`);
- down projections (`MUL_MAT_ID:node_60`, `node_2119`, etc.) remain hot with
  shape `src0=q8_0/bf16 [704,2816,128]`, `src1=f32 [704,8,2]`,
  `ids=i32 [8,2]`.

Two read-only subagents independently agreed with the local profile read:

- assistant/draft path: direct unroll is already one `llama_decode()` call and
  n>7 adds real full assistant graph work; no small exact draft-loop patch is
  obvious;
- verifier/target path: the credible `>150 tok/s` lane is a larger
  Gemma4-only small-token MoE verifier op or a truly retuned target LM-head
  argmax, not another existing flag sweep.

Decision: preserve as diagnostic context. Do **not** rerun existing flags
unchanged: target fused-output argmax, broad `MUL_MAT_ID_MULTI_TOKEN_FAST`,
grouped/per-slot Q8 variants, GEGLU/down matmul epilogues, gate-up-only fusion,
and route-cache metadata tweaks have all already been valid losses or
non-winning near misses. Next implementation should be a broader exact
Gemma4 verifier MoE boundary under strict guards.
