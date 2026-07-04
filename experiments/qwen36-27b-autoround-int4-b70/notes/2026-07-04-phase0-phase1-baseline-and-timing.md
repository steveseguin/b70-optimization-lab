# 2026-07-04 - Phase 0/1 baseline lock and timing refresh

## Scope

This note records the first execution pass from
`2026-07-04-next-optimization-execution-plan.md` for the current Qwen27 active
record lane:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- checkpoint:
  `/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`;
- runtime label: AutoRound W4A16 target + runtime INT8 LM-head with BF16 scales;
- MTP: target-verified `qwen3_next_mtp`, `num_speculative_tokens=3`, cg8;
- gate: fixed Qwen realistic suite, 12 unique prompts, each prompt once,
  `cached_tokens=0`, no prefix/KV/context/response/history reuse.

The goal remains to beat the current valid LocalMaxxing row
`65.27648650325429 tok/s` (`cmr5iu3gk00bfq901nidgcana`) without lowering
quality or using warmed/cache/history effects.

## Phase 0 - baseline lock

Command:

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-webhie-int8lmhead-bf16scale-phase0-baseline-20260704 \
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=0 PORT=19410 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Artifacts:

- strict result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-phase0-baseline-20260704-20260704T020205Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-phase0-baseline-20260704-20260704T020205Z`;
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-phase0-baseline-20260704-20260704T020205Z/server.stdout.log`.

Result:

| Metric | Value |
| --- | ---: |
| median tok/s, generated tokens 1-100 after TTFT | `65.56930784255283` |
| p10 tok/s, generated tokens 1-100 after TTFT | `59.64437041204901` |
| mean tok/s, generated tokens 1-100 after TTFT | `65.26223803662062` |
| min / max tok/s, generated tokens 1-100 after TTFT | `54.12103670988303` / `74.4744334068544` |
| median full-output after-TTFT tok/s | `65.90389917058495` |
| median wall full-output tok/s | `49.78746581529376` |
| median TTFT | `604.468232486397 ms` |
| max TTFT | `24633.653877070174 ms` |
| prompt count | `12` |
| cached tokens | all `0` |
| validity | fresh-response valid |

Interpretation:

- The current record family reproduced cleanly and slightly above the
  submitted `65.27648650325429 tok/s` median.
- The high max TTFT is an outlier that affects wall-clock/TTFT statistics but
  does not invalidate the after-TTFT decode metric. Keep tracking TTFT
  separately for service work.
- The server log confirmed both target and draft INT8 LM-head preparation with
  BF16 scales, e.g. `scale_dtype=torch.bfloat16`.

## Phase 1 - timing refresh

Command:

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-webhie-int8lmhead-bf16scale-phase1-timing-20260704 \
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
VLLM_XPU_DECODE_TIMING=1 \
VLLM_XPU_DECODE_TIMING_SYNC=1 \
VLLM_XPU_DECODE_TIMING_SUMMARY=1 \
VLLM_XPU_DECODE_TIMING_SKIP_FIRST=32 \
VLLM_XPU_DECODE_TIMING_LABEL_REGEX='lm_head_int8\.|logits\.local_argmax_lm_head|gpu_model_runner\.(model_forward|forward_total|compute_logits|rejection_sampler|sample_total|draft_total|postprocess_total|preprocess_total|bookkeeping_sync)|spec_decode\.(greedy_sample|propose\.(model_forward|build_attn_metadata|copy_buffers|select_hidden|select_sample_hidden|tree_compute_logits))' \
VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX='lm_head_int8\.|logits\.local_argmax_lm_head|gpu_model_runner\.(compute_logits|rejection_sampler)|spec_decode\.(greedy_sample|propose\.(model_forward|tree_compute_logits))' \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Artifacts:

- strict result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-phase1-timing-20260704-20260704T020549Z.json`;
- summarized timing:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-phase1-timing-summary-20260704T020549Z.json`;
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-phase1-timing-20260704-20260704T020549Z`;
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-phase1-timing-20260704-20260704T020549Z/server.stdout.log`.

The timing run also passed the fresh-response gate (`cached_tokens=0` every
row), but its throughput is diagnostic because sync timing instrumentation
perturbs the path:

| Diagnostic metric | Value |
| --- | ---: |
| median tok/s, generated tokens 1-100 after TTFT | `58.71192754813103` |
| p10 tok/s, generated tokens 1-100 after TTFT | `51.29897556523546` |
| mean tok/s, generated tokens 1-100 after TTFT | `57.57312978310146` |
| median TTFT | `620.3460824908689 ms` |

Top timing labels by total time:

| Label | Count | Avg ms | Total ms | Max ms |
| --- | ---: | ---: | ---: | ---: |
| `gpu_model_runner.forward_total` | `540` | `21.907177` | `11829.875441` | `615.992175` |
| `gpu_model_runner.model_forward` | `540` | `21.851573` | `11799.849539` | `615.916643` |
| `gpu_model_runner.postprocess_total` | `540` | `20.875379` | `11272.704922` | `22.060377` |
| `gpu_model_runner.draft_total` | `540` | `12.527068` | `6764.616561` | `31.354991` |
| `logits.local_argmax_lm_head` | `2258` | `2.685973` | `6064.927342` | `2.859383` |
| `lm_head_int8.gemm_w8a8` | `2258` | `2.537287` | `5729.193765` | `2.678894` |
| `spec_decode.greedy_sample_total` | `1684` | `2.935668` | `4943.665648` | `3.178843` |
| `spec_decode.greedy_sample.compute_logits` | `1684` | `2.763178` | `4653.191855` | `2.940275` |
| `gpu_model_runner.preprocess_total` | `554` | `2.767337` | `1532.303` | see summary |
| `gpu_model_runner.compute_logits` | `540` | `2.755869` | `1488.169` | see summary |
| `spec_decode.propose.model_forward_next` | `1112` | `0.650347` | `723.186` | see summary |
| `spec_decode.propose.model_forward_first` | `540` | `0.760630` | `410.740` | see summary |
| `gpu_model_runner.sample_total` | `540` | `0.476971` | `257.564` | see summary |
| `gpu_model_runner.rejection_sampler` | `528` | `0.432830` | `228.534` | see summary |
| `spec_decode.greedy_sample.argmax` | `1684` | `0.088918` | `149.755` | see summary |
| `lm_head_int8.per_token_quant` | `2258` | `0.055551` | `125.442` | see summary |

Derived view:

- `2258` logits / LM-head calls over `540` verifier steps is about `4.18`
  logits calls per step.
- `lm_head_int8.gemm_w8a8` alone is about `10.61 ms` per verifier step
  (`5729.19 ms / 540`), excluding local argmax and surrounding logits plumbing.
- The strict suite generated `1536` completion tokens over `540` verifier steps,
  or about `2.84` generated tokens per verifier step.
- Server spec metrics during the same family of runs report mean acceptance
  length around `2.7-2.9`, with per-position acceptance roughly
  `0.75-0.85`, `0.54-0.63`, and `0.36-0.46` for the three draft positions.
  This is good enough that the current MTP3 path works, but it leaves a second
  major route to `90+ tok/s`: improve accepted tokens per expensive verifier
  step without adding verifier cost or using warmed/history effects.
- Quantization is cheap (`~0.056 ms` per logits call). Sampler, argmax,
  metadata, buffer copies, and GDN/state bookkeeping remain small compared with
  full LM-head materialization.

Nested timing labels are not exclusive, so do not sum all rows as independent
cost. Use this table to rank attack surfaces, not as a cycle-accurate exclusive
profile.

## Source audit from this pass

Relevant local code inspected:

- `/home/steve/src/vllm/vllm/model_executor/layers/vocab_parallel_embedding.py`
  prepares transient INT8 LM-head weights shaped `[5120, 248320]` and BF16
  scales shaped `[248320]` when `VLLM_XPU_LM_HEAD_INT8=1`; `apply()` still
  performs `per_token_quant_int8_xpu` followed by `int8_gemm_w8a8`, returning
  dense logits.
- `/home/steve/src/vllm/vllm/model_executor/layers/logits_processor.py`
  `get_top_tokens()` still calls the LM-head quant method first, so the local
  argmax path has not avoided full logits.
- `/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py`
  calls greedy sampling for the first and subsequent draft tokens, which
  explains repeated draft LM-head calls per verifier step.
- `/home/steve/src/vllm/vllm/v1/sample/rejection_sampler.py` still expects
  target logits for exact verification.
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/onednn/onednn_matmul.cpp` and
  the associated torch bindings expose dense output matmul wrappers; they do
  not expose a top-1/candidate-reduction epilogue.

External primary-source check:

- oneDNN matmul documentation describes dense `src * weights -> dst` behavior
  with optional post-ops, but not a matmul primitive that directly returns
  `argmax`/candidate-reduced output for this use case:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html`.

## Interpretation

Phase 0 is complete: the current `65.276` record family is reproducible, with a
new strict fresh row at `65.569`.

Phase 1 is complete enough to choose the next source lane:

- LM-head/logits remains the clean waste target. Current runtime INT8 LM-head
  still materializes dense `[rows, vocab]` logits for target verification and
  draft greedy sampling.
- A serious LM-head reduction must be native/tiled/XMX-level work. The preserved
  scalar prototype in
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-int8-lm-head-top1-microbench-no-win-20260703.patch`
  was correct but about `1000x` slower, so scalar SYCL/Python/chunked oneDNN
  attempts are closed.
- Removing all measured LM-head GEMM cost would not by itself guarantee
  `100+ tok/s`; it likely moves the current recipe toward the high-70s or
  high-80s unless accepted tokens per verifier step also improves. The second
  major lane is therefore accepted-token efficiency, but only with exact
  target-verified semantics and no warmed/history acceleration.
- Do not spend more time on sampler plumbing, state-copy micro-optimizations,
  output buffer reuse, or basic config sweeps unless a fresh trace shows a new
  hot path.

## Next action

Proceed to Phase 2 with one of two concrete routes:

1. build a real native tiled/XMX LM-head top-1/candidate-max prototype in
   `vllm-xpu-kernels` and reject it quickly if it cannot beat the dense
   `int8_gemm_w8a8 + argmax` path exactly; or
2. if the native kernel route is too large for the current work window, add a
   narrow diagnostic that records per-step accepted tokens, full-accept rate,
   and logits-call count for the strict suite, then use that to guide
   accepted-token/bonus-row work.

Either route must preserve the fresh-response gate and must not submit anything
to LocalMaxxing until it produces a strict, quality-passing record above
`65.27648650325429 tok/s`.
