# Qwen3.6 Quark W8A8 INT8 TP4 RPC Timing Summary

Date: 2026-06-12

Purpose: split the EngineCore `future_result` wait far enough to distinguish
worker compute, worker response packaging, and driver-side response wait for the
current accepted model path.

## Artifacts

- `patches/vllm-qwen36-engine-rpc-timing-20260612bt.diff`
- `data/qwen36-quark-int8-tp4-rpc-timing-20260612bt.log`
- `data/qwen36-quark-int8-tp4-rpc-timing-p512o256-metrics-20260612bt.json`
- `data/qwen36-quark-int8-tp4-rpc-timing-summary-20260612bt.json`
- `data/qwen36-quark-int8-tp4-rpc-fastoutput-20260612bu.log`
- `data/qwen36-quark-int8-tp4-rpc-fastoutput-p512o256-metrics-20260612bu.json`
- `data/qwen36-quark-int8-tp4-rpc-fastoutput-summary-20260612bu.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-rpc-timing-20260612bu.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-rpc-timing-20260612bu.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-rpc-timing-nothink-smoke-20260612bu.json`

## Baseline Diagnostic

Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`

Runtime: vLLM/XPU TP4, 32K context, accepted graph cache, no prefix caching.

Prompt/output: vLLM-random p512/o256, c1, streaming, `ignore_eos=true`.

Throughput:

- Corrected output throughput after first chunk: `100.621 tok/s`.
- End-to-end output throughput: `97.782 tok/s`.
- vLLM decode histogram: `9.902 ms/token`.
- vLLM time-per-output-token histogram: `9.941 ms/token`.
- Client TTFT: `83.800 ms`.
- vLLM queue time: `0.014 ms`.
- vLLM prefill time: `76.385 ms`.

RPC sample coverage:

- Engine step records: `9`.
- Worker timing records: `36`.
- Executor RPC records: `40`.
- Worker RPC records: `80`.
- Worker output records: `20`.
- Due the print cadence, the joined RPC calls are `sample_tokens` calls. That is
  still the relevant queue path because EngineCore waits on the queued
  `sample_tokens` future for emitted decode tokens.

`sample_tokens` joined RPC split:

| Metric | Mean ms | Median ms | Max ms |
| --- | ---: | ---: | ---: |
| Driver enqueue | `0.021` | `0.021` | `0.030` |
| Driver response wait | `4.297` | `4.358` | `4.465` |
| Max worker function time | `0.351` | `0.343` | `0.427` |
| Max worker after-dequeue time | `0.363` | `0.354` | `0.440` |
| Rank-0 output enqueue/materialize | `3.900` | `3.954` | `4.090` |
| Response wait minus max worker function | `3.946` | `4.008` | `4.109` |
| Worker function skew | `0.037` | `0.030` | `0.109` |

Interpretation:

- The `sample_tokens` worker function itself is only about `0.35 ms`.
- The output-rank response packaging path is about `3.9 ms` and accounts for
  almost the whole `sample_tokens` response wait.
- This points at `AsyncModelRunnerOutput.get_output()` and the async output
  copy completion path, not at sampler compute.
- The expensive portion is probably the event synchronization / device-to-host
  token-id copy becoming visible to the host. The existing labels show
  `gpu_model_runner.async_output_wrap` is only about `0.1 ms`, so the cost is
  later, when the worker response is materialized.

## Fast-Output A/B

Additional env:

- `VLLM_XPU_FAST_ASYNC_OUTPUT_LIST=1`
- `VLLM_XPU_REUSE_ASYNC_OUTPUT_COPY_BUFFER=1`

Throughput:

- Corrected output throughput after first chunk: `100.327 tok/s`.
- End-to-end output throughput: `97.730 tok/s`.
- vLLM decode histogram: `9.931 ms/token`.
- vLLM time-per-output-token histogram: `9.970 ms/token`.

`sample_tokens` joined RPC split:

| Metric | Mean ms | Median ms | Max ms |
| --- | ---: | ---: | ---: |
| Driver enqueue | `0.018` | `0.017` | `0.027` |
| Driver response wait | `4.367` | `4.358` | `4.497` |
| Max worker function time | `0.346` | `0.340` | `0.421` |
| Max worker after-dequeue time | `0.356` | `0.351` | `0.432` |
| Rank-0 output enqueue/materialize | `3.962` | `3.951` | `4.075` |
| Response wait minus max worker function | `4.021` | `4.008` | `4.159` |
| Worker function skew | `0.030` | `0.028` | `0.088` |

Interpretation:

- The fast-list and reusable-copy-buffer switches did not improve decode or the
  `sample_tokens` response wait.
- That makes a pure `.tolist()` shortcut or simple existing buffer reuse less
  likely to be enough.
- The next timing hook should split `AsyncModelRunnerOutput.get_output()` into:
  event sync, device-to-host copy completion, token-id conversion, logprobs
  conversion, and message-queue enqueue.

## Next Gates

1. Add disabled-by-default `AsyncModelRunnerOutput.get_output()` sub-timing.
   The exact target is event synchronization versus Python conversion versus
   response queue enqueue.

2. Make the reusable CPU token buffer dtype-aware. If sampled token IDs are
   `int64`, the existing `int32` buffer branch cannot fire; if they are `int32`,
   prove the branch is active with metadata.

3. Add a scalar or fixed-shape c1 output path for no-logprobs completions:
   copy only the committed token ID into a pinned one-token host slot and avoid
   constructing a tensor/list payload per decode step.

4. Run `VLLM_XPU_SYNC_ASYNC_OUTPUT_COPY=1` and
   `VLLM_XPU_DEFER_ASYNC_OUTPUT_COPY=1` as diagnostics. These are not expected
   promotions; they should confirm where the hidden copy/sync cost lands.

5. Build the no-server c1 ceiling harness with the same sampler output and
   checkpoint. If it avoids the `~4 ms` host-output wait, we have a concrete
   serving-path target.

6. Keep the oneDNN/resident MoE work moving, but do not ignore this output path:
   saving `~4 ms/token` is as valuable as a large kernel win and does not touch
   model quality.

## Public Signals Checked

- Localmaxxing public B70/vLLM rows still show the exact current model row at
  `99.428 tok/s`, and nearby B70/Qwen3.6 vLLM rows around `100 tok/s`. Higher
  B70 rows use different models, lower precision, batch/concurrency, or
  workload, so they are idea sources rather than accepted comparables.
- Intel's grouped-GEMM tuning issue emphasizes that MoE grouped GEMM
  performance depends strongly on real routing distribution and decode-stage
  skew:
  https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
- The vLLM Arc Pro B-series post describes persistent zero-gap MoE kernels,
  dynamic group balancing, host-wait/device-idle gaps, and multi-GPU scaling as
  first-class Intel Arc optimization targets:
  https://vllm.ai/blog/2025-11-11-intel-arc-pro-b
- oneDNN supports INT8 inference primitives, scaling attributes, zero-points,
  and fused post-ops. This remains relevant for the resident sidecar and
  execute-and-compare path:
  https://uxlfoundation.github.io/oneDNN/dev_guide_inference_int8.html
- vLLM's Intel quantization docs currently call out W4A16 and W8A16 AutoRound
  support on Intel platforms, with additional formats planned. That is useful
  context, but not a reason to change the current Quark W8A8 target:
  https://docs.vllm.ai/en/latest/features/quantization/inc/

## Bigger Bets Added

1. **Pinned scalar output ferry.** Replace per-token output materialization with
   a fixed pinned scalar ring and event handoff for c1/no-logprobs. The model
   output is unchanged; only the host transport path changes.

2. **Device-resident sampler/streamer lane.** Keep token selection and short
   token buffers device-side, then copy committed IDs in small batches or via a
   persistent host-visible ring. This is risky for latency semantics but may
   remove one sync per token.

3. **Single-request direct runner.** Keep the same model runner and sampler but
   bypass OpenAI serving, scheduler queues, and multiprocessing for a fixed
   c1 latency lane. Token parity with accepted vLLM is the gate.

4. **TP2 latency lane plus replicas.** Test whether TP4 is over-synchronizing
   the sparse active-token path. If TP2 wins c1 latency, spend the other B70s
   on replicas, branch verification, or aggregate traffic.

5. **Expert-parallel sparse island.** Keep dense/shared layers tensor-parallel
   but route MoE expert work to rank-local or duplicated expert islands. This
   trades the large VRAM surplus for lower synchronization and route skew.

6. **Whole-token command-list replay.** Capture a fixed decode bucket across
   attention, MoE, residual, sampler, and output handoff into a patchable Level
   Zero command sequence. This is a large engineering bet, but it attacks host
   launch and synchronization directly.

7. **Target-owned branch farm.** Use current Quark W8A8 target verification for
   ngram/MTP/EAGLE-style proposed futures. No proposed token is emitted unless
   the current target model commits it.

8. **B70 maintainer packet.** Publish a small reproducible packet for
   Intel/vLLM maintainers: route windows, exact checkpoint, command line,
   profiler traces, output-path timing, oneDNN sidecar fixtures, and the
   `5 ms/token` target.

9. **Strict same-model engine bakeoff.** Compare OpenVINO/oneDNN, llama.cpp
   SYCL, SGLang, KTransformers, and custom runners only when they can preserve
   the current model output or use BF16 as a quality oracle. No 4-bit/AWQ/Qwen3.5
   shortcut is acceptable.

10. **Parity/stability scoreboard.** Every performance branch must show exact
    provenance sentinels, no-thinking quality smoke, route-window parity where
    applicable, a reproducible command, XPU memory, and a soak/stability result
    before promotion.
