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
