# 2026-07-05 - ReplaySSM stage profile and current frontier

Status: **diagnostic only; no LocalMaxxing submission**.

This note records the first direct stage-boundary comparison between the current
strict Qwen27 record family and the only quality-clean draft-INT4/ReplaySSM
family. It corrects an older stale estimate that treated LM-head/logits as the
dominant current-record bottleneck.

## Valid record family being compared

Current strict fresh-response record to beat:

- model label: `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head
  (BF16 scales)`;
- one Intel Arc Pro B70, TP1, MTP3, XPU graph, `max_cudagraph_capture_size=8`;
- strict Qwen realistic suite, chat mode, one cold response per prompt,
  `cached_tokens=0` on every row;
- headline record: `65.27648650325429 tok/s`, LocalMaxxing
  `cmr5iu3gk00bfq901nidgcana`.

Stage-profiling runs below set:

```text
VLLM_XPU_STAGE_BOUNDARY_SYNC=1
VLLM_XPU_STAGE_BOUNDARY_DEVICE_ELAPSED=1
VLLM_XPU_STAGE_BOUNDARY_PRINT_EVERY=20
VLLM_XPU_STAGE_BOUNDARY_SKIP_FIRST=5
RUN_QUALITY=0
```

Because the timing instrumentation synchronizes at stage boundaries, the
reported throughput is lower than the normal record row. These are cost
attribution runs, not headline candidates.

## Runs

Record-family timing run:

```text
label: qwen27-stageprofile-record-bf16scale-20260705T163924Z
summary: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-stageprofile-record-bf16scale-20260705T163924Z-candidate-summary-20260705T163924Z.json
server log: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-stageprofile-record-bf16scale-20260705T163924Z-20260705T163924Z/server.stdout.log
instrumented median: 62.49493265550195 tok/s
```

ReplaySSM timing run:

```text
label: qwen27-stageprofile-replayssm-s4-stagefix-20260705T163924Z
summary: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-stageprofile-replayssm-s4-stagefix-20260705T163924Z-candidate-summary-20260705T163924Z.json
server log: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-stageprofile-replayssm-s4-stagefix-20260705T163924Z-20260705T163924Z/server.stdout.log
instrumented median: 57.15342576193111 tok/s
env: VLLM_XPU_GDN_REPLAYSSM_SPEC=1,
     VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8,
     VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0,
     VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0
```

Both runs passed the strict fresh/cached-zero gate. Quality was intentionally
skipped because these were timing diagnostics, not promotion runs.

## Stage-boundary medians

All parsed timing rows were `num_tokens=4`.

| Stage | Record median ms | ReplaySSM median ms | Delta |
| --- | ---: | ---: | ---: |
| `forward` | `30.555` | `32.468` | `+1.913` |
| `compute_logits` | `2.490` | `2.490` | `0.000` |
| `sample` | `0.130` | `0.132` | `+0.002` |
| `sample_to_state_update_end` | `0.019` | `2.147` | `+2.128` |
| `state_update_to_bookkeeping_start` | `10.398` | `10.434` | `+0.036` |
| Rough device-stage sum | `43.7` | `47.7` | `+4.0` |

Interpretation:

- ReplaySSM's quality-clean GDN transaction costs about `4 ms/step` versus the
  current record family: roughly `2 ms` in forward/staging and `2.1 ms` in
  state update/commit.
- Logits and sampler are **not** the ReplaySSM-vs-record delta.
- Even a perfect removal of ReplaySSM overhead only returns this draft-INT4
  family near the existing `65 tok/s` record; it does not create a credible
  `100+ tok/s` path by itself.

## Acceptance comparison

Current record-family MTP3 acceptance:

```text
summary: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-baseline-samewindow-20260704T033352Z-20260704T033352Z-acceptance-summary.json
draft steps: 552
emitted tokens / step: 2.760869565217391
mean acceptance length incl target: 2.789855072463768
full accept rate: 0.40217391304347827
accepted hist: {0:113, 1:112, 2:105, 3:222}
```

ReplaySSM trace:

```text
summary: data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-draftint4-replayssm-stagefix-promote-graph-20260705T142314Z/verify-summary.json
steps: 98
mean target-verified tokens / step: 2.7448979591836737
full accept rate: 0.4489795918367347
accepted hist: {0:24, 1:21, 2:9, 3:44}
```

Acceptance is comparable. The ReplaySSM family loses on step cost, not on token
acceptance.

## Consequence for the next speed lane

The current exact-BF16-scale INT8 LM-head `compute_logits` stage is only about
`2.5 ms` per target verifier step in the stage-boundary run. That is still worth
improving, but it is not the sole `>100 tok/s` unlock for the current record
recipe.

The real route to `100+ tok/s` needs at least one of:

1. materially more target-verified tokens per expensive target step;
2. a stronger target-matched drafter that is valid on fresh chat-style prompts;
3. a deeper verifier redesign that reduces target forward cost, not just the
   final LM-head projection;
4. a graph-safe exact GDN/DeltaNet transaction so stronger drafting can be used
   without state corruption.

Do not promote fast invalid draft-INT4 rows. Do not spend more record-chasing
time on ReplaySSM micro-optimizations unless the goal is making the
quality-clean draft-INT4 family equal the `65 tok/s` record. For a new record,
prioritize stronger speculation/oracle work and target-forward reduction.

## Follow-up decode-timing summary: current MTP3 draft cost is the ceiling

Run:

```text
label: qwen27-decodetiming-record-bf16scale-20260705T165456Z
summary: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-decodetiming-record-bf16scale-20260705T165456Z-candidate-summary-20260705T165456Z.json
server log: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-decodetiming-record-bf16scale-20260705T165456Z-20260705T165456Z/server.stdout.log
strict fresh median: 66.04071358389794 tok/s
p10: 58.26184804540971 tok/s
mean: 64.27135554497296 tok/s
TTFT median: 620.9397369530052 ms
cached_tokens: 0/12 all zero
quality: skipped; timing/support run only
```

Timing summary from `[vllm-xpu-timing-summary]`:

| Label | Count | Avg ms |
| --- | ---: | ---: |
| `gpu_model_runner.model_forward` | `2176` | `13.835` |
| `spec_decode.propose.model_forward_next` | `4372` | `11.387` |
| `spec_decode.propose.model_forward_first` | `2176` | `0.250` |
| `gpu_model_runner.compute_logits` | `2176` | `0.116` |
| `spec_decode.greedy_sample.compute_logits` | `6568` | `0.110` |
| `logits.local_argmax_lm_head` | `8766` | `0.087` |
| `lm_head_int8.gemm_w8a8` | `8766` | `0.040` |
| `lm_head_int8.per_token_quant` | `8766` | `0.027` |
| `gpu_model_runner.rejection_sampler` | `2163` | `0.394` |

Interpretation:

- The record family is no longer dominated by a `2-10 ms` dense LM-head block in
  the measured path. The INT8 LM-head plus local argmax path is already small.
- The heavy current cost is target forward plus the two recurrent MTP draft
  forward passes per MTP3 step. This explains why wrapper-level sampler,
  standalone full-vocab top-1 kernels, chunked logits, scratchpad ring changes,
  and ReplaySSM micro-optimizations do not produce a `100+ tok/s` path.
- New-record work should therefore prioritize a materially cheaper or stronger
  target-matched drafter, accepted-token-per-target-step gains, or target
  forward/kernel reductions. The corrected Ex0bit EAGLE3 retest on 2026-07-05
  is justified because it is a different one-layer external drafter and the old
  EAGLE3 run likely did not read nested `eagle_config.eagle_aux_hidden_state_layer_ids`
  as `[1, 31, 60]`.

## Follow-up: layer timing visibility and target-forward attribution

Two extra timing runs were made after the EAGLE3 aux-layer retest to separate
"what is slow in the graph-on record path" from "which Qwen3 Next submodules
dominate when Python scopes are visible".

### Graph-on record recipe, timing scopes inside compiled graph are invisible

Run:

```text
label: qwen27-layertiming-record-bf16scale-20260705T171657Z
summary: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-layertiming-record-bf16scale-20260705T171657Z-candidate-summary-20260705T171657Z.json
bench: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-layertiming-record-bf16scale-20260705T171657Z-realistic128-chat-tokenids-qwensuite-20260705T171657Z.json
server log: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-layertiming-record-bf16scale-20260705T171657Z-20260705T171657Z/server.stdout.log
```

Gate:

- strict fresh/cached-zero gate passed (`cached_tokens=0` on `12/12`);
- quality intentionally skipped (`RUN_QUALITY=0`) because this is timing
  support, not a promoted candidate;
- median `64.96264358090735 tok/s`, p10 `58.004327748808834`, mean
  `64.2096995639903`;
- prefix-cache hit rate remained `0.0%`.

Timing config requested `qwen3_next.*` labels, but only outer labels appeared
in `[vllm-xpu-timing-summary]`. This is expected: `timed_region()` deliberately
no-ops while Torch/Dynamo is compiling, so Python scopes inside the compiled /
captured model body are not visible in summary output.

Outer graph-on timing rows:

| Label | Count | Total ms | Avg ms |
| --- | ---: | ---: | ---: |
| `spec_decode.propose.model_forward_next` | `4368` | `50570.894` | `11.578` |
| `gpu_model_runner.model_forward` | `2174` | `29822.919` | `13.718` |
| `logits.local_argmax_lm_head` | `8758` | `756.003` | `0.086` |
| `spec_decode.greedy_sample.compute_logits` | `6562` | `714.015` | `0.109` |
| `spec_decode.propose.model_forward_first` | `2174` | `543.273` | `0.250` |
| `lm_head_int8.gemm_w8a8` | `8758` | `345.028` | `0.039` |
| `gpu_model_runner.compute_logits` | `2174` | `248.089` | `0.114` |
| `lm_head_int8.per_token_quant` | `8758` | `235.240` | `0.027` |

Interpretation:

- In the graph-on path, the outer aggregate cost is dominated by recurrent MTP
  next-token proposer forwards plus target model forward. LM-head/logits are
  small.
- The surprising asymmetry is that `model_forward_first` is tiny while each
  recurrent `model_forward_next` is large. This is the next place to audit if
  we want a `100+ tok/s` source change: determine whether recurrent MTP-next is
  taking the intended captured/compiled path, or whether metadata/padding/graph
  dispatch causes a slow replay path.

### Eager/no-compile attribution, diagnostic only

Run:

```text
label: qwen27-layertiming-eager-nocompile-bf16scale-20260705T172115Z
summary: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-layertiming-eager-nocompile-bf16scale-20260705T172115Z-candidate-summary-20260705T172115Z.json
bench: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-layertiming-eager-nocompile-bf16scale-20260705T172115Z-realistic128-chat-tokenids-qwensuite-20260705T172115Z.json
server log: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-layertiming-eager-nocompile-bf16scale-20260705T172115Z-20260705T172115Z/server.stdout.log
compilation: COMPILATION_CONFIG='{"mode":0,"cudagraph_mode":"NONE"}',
             QWEN36_27B_ENABLE_XPU_GRAPH=0
```

Gate:

- strict fresh/cached-zero gate passed (`cached_tokens=0` on `12/12`);
- quality intentionally skipped;
- median `27.872504407556416 tok/s`, p10 `25.06533758568078`, mean
  `27.493303845651912`.

This is **not** a throughput candidate. Disabling compile and graph is only a
diagnostic trick to make Python-level model scopes visible.

Top timing rows:

| Label | Count | Total ms | Avg ms |
| --- | ---: | ---: | ---: |
| `gpu_model_runner.model_forward` | `2196` | `192235.939` | `87.539` |
| `qwen3_next.layer_type.linear_attention` | `106444` | `129622.677` | `1.218` |
| `qwen3_next.layer.linear_attention` | `106444` | `67870.571` | `0.638` |
| `qwen3_next.layer_type.full_attention` | `35468` | `65048.139` | `1.834` |
| `qwen3_next.layer.full_attention` | `42122` | `52762.903` | `1.253` |
| `qwen3_next.layer.post_attention_norm` | `148586` | `27736.188` | `0.187` |
| `qwen3_next.layer.input_norm` | `148586` | `27375.417` | `0.184` |
| `qwen3_next.gdn.core_op` | `106444` | `24720.638` | `0.232` |
| `qwen3_next.layer.mlp` | `148586` | `23542.608` | `0.158` |
| `gpu_model_runner.draft_total` | `2196` | `20309.347` | `9.248` |
| `qwen3_next.full_attention.rotary` | `42122` | `19677.073` | `0.467` |
| `qwen3_next.full_attention.qk_norm` | `42122` | `14554.381` | `0.346` |
| `spec_decode.propose.model_forward_next` | `4412` | `10776.901` | `2.443` |
| `spec_decode.propose.model_forward_first` | `2196` | `5499.365` | `2.504` |
| `gpu_model_runner.compute_logits` | `2196` | `244.660` | `0.111` |

Interpretation:

- In eager/no-compile mode, target model forward is approximately
  `48` linear-attention/GDN layers plus `16` full-attention layers per target
  step. The outer target layer timing is about two-thirds GDN/linear attention
  and one-third full attention.
- MTP draft calls use one full-attention decoder layer; the `qwen3_next.layer.full_attention`
  count includes both target full-attention layers and MTP draft layer calls
  (the target-only outer `layer_type.full_attention` count is lower).
- This does **not** prove the same proportions after graph/Inductor fusion, but
  it says the source-level targets with real compute weight are GDN/linear
  attention and recurrent MTP-next dispatch, not final logits.

## Next concrete source target

Do not run more endpoint config sweeps until this is answered:

1. Why is graph-on `spec_decode.propose.model_forward_next` about `11.6 ms` per
   recurrent draft call while graph-on `model_forward_first` is about
   `0.25 ms`, and eager/no-compile first/next are both about `2.5 ms`?
2. Does recurrent MTP-next actually replay the intended graph for batch size 1,
   or does its per-step attention metadata / slot mapping / padding path force a
   slow compiled/eager path?
3. If recurrent MTP-next is graph-missing or over-padded, the plausible win is
   large: two recurrent next calls per MTP3 verifier step are the biggest outer
   timing bucket in the graph-on record run.

Suggested next audit / patch path:

- add default-off trace fields around `_determine_batch_execution_and_padding`
  and `set_forward_context` in `vllm/v1/spec_decode/llm_base_proposer.py` for
  the recurrent next loop: requested batch size, padded input size,
  `cudagraph_runtime_mode`, `num_tokens_across_dp`, slot-mapping size, and
  whether the compiled wrapper reports graph replay or fallback;
- run a short strict fresh diagnostic with that trace, not a full quality run;
- only then patch the recurrent MTP-next graph dispatch path if the trace proves
  a mismatch.

## Follow-up: recurrent MTP-next dispatch trace

Run:

```text
label: qwen27-mtp-next-dispatch-trace-20260705T173032Z
summary: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtp-next-dispatch-trace-20260705T173032Z-candidate-summary-20260705T173032Z.json
bench: data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtp-next-dispatch-trace-20260705T173032Z-realistic128-chat-tokenids-qwensuite-20260705T173032Z.json
server log: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-mtp-next-dispatch-trace-20260705T173032Z-20260705T173032Z/server.stdout.log
trace: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-mtp-next-dispatch-trace-20260705T173032Z-20260705T173032Z/mtp-next-dispatch.jsonl
trace patch: patches/qwen36-27b-autoround-int4-b70/vllm-mtp-next-dispatch-trace-20260705.patch
```

Gate:

- strict fresh/cached-zero gate passed (`cached_tokens=0` on `12/12`);
- quality intentionally skipped;
- median `65.8248426232438 tok/s`, p10 `58.061042157341856`, mean
  `64.3340200039463`;
- prefix-cache hit rate remained `0.0%`.

Timing summary:

| Label | Count | Total ms | Avg ms |
| --- | ---: | ---: | ---: |
| `gpu_model_runner.draft_total` | `2176` | `54749.937` | `25.161` |
| `spec_decode.propose.model_forward_next` | `4372` | `50048.343` | `11.447` |
| `gpu_model_runner.model_forward` | `2176` | `30175.273` | `13.867` |
| `spec_decode.greedy_sample_total` | `6568` | `1085.724` | `0.165` |
| `logits.local_argmax_lm_head` | `8766` | `767.886` | `0.088` |
| `spec_decode.greedy_sample.compute_logits` | `6568` | `726.943` | `0.111` |
| `spec_decode.propose.model_forward_first` | `2176` | `546.662` | `0.251` |
| `gpu_model_runner.compute_logits` | `2176` | `254.003` | `0.117` |
| `spec_decode.propose.update_slot_metadata_next` | `4372` | `251.772` | `0.058` |
| `spec_decode.propose.copy_buffers_next` | `4372` | `134.837` | `0.031` |
| `spec_decode.propose.build_attn_metadata_next` | `4372` | `42.096` | `0.010` |
| `spec_decode.propose.select_hidden_next` | `4372` | `19.145` | `0.004` |

The trace captured the first 64 recurrent MTP-next dispatches. Every sampled
row had the expected graph-friendly outer shape:

- `cudagraph_runtime_mode: "PIECEWISE"`;
- `batch_size: 1`, `input_batch_size: 1`, `num_actual_tokens: 1`;
- `max_query_len: 1`;
- `per_layer_metadata_type_counts: {"FlashAttentionMetadata": 1}`;
- one draft attention slot mapping with shape `[1]`;
- text path still enters the multimodal-capable interface, so recurrent
  MTP-next sends `input_ids: null` and `inputs_embeds` shape `[1, 5120]`;
- M-RoPE positions are shape `[3, 1]` and non-contiguous, matching the upstream
  M-RoPE buffer design.

Interpretation:

- The recurrent MTP-next slow path is **not** explained by obvious batch
  padding, a missing PIECEWISE dispatch key, or an oversized slot mapping.
- The remaining uncertainty is whether the `~11.45 ms` `model_forward_next`
  timing is true MTP-next GPU time or async timing attribution from adjacent GPU
  work. A narrow sync-timing diagnostic is required before changing kernels.
- If sync timing confirms the cost is real, the next code target is the
  Qwen3-Next MTP predictor body (`qwen3_next_mtp.py`): the record recipe spends
  about `23 ms` per MTP3 verifier step in two recurrent next passes, and this is
  the largest draft-side barrier to `100+ tok/s`.

Next diagnostic:

- run the same strict fresh support suite with
  `VLLM_XPU_DECODE_TIMING_SYNC=1` but sync only outer labels
  `spec_decode.propose.model_forward_first`,
  `spec_decode.propose.model_forward_next`, `gpu_model_runner.model_forward`,
  and `gpu_model_runner.draft_total`;
- do not promote the throughput from that run, because sync instrumentation
  perturbs timing;
- use it only to decide whether to optimize the MTP-next model body or search
  for the true downstream synchronization point.
