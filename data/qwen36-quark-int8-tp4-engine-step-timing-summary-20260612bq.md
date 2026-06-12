# Qwen3.6 Quark W8A8 INT8 TP4 Engine Step Timing

Date: 2026-06-12

Scope: diagnostic timing only. The model remains
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` on 4x Intel Arc Pro B70,
served by vLLM/XPU TP4 with the accepted graph-cache posture. The EngineCore
timing hook is disabled unless `VLLM_XPU_ENGINE_STEP_TIMING=1` is set.

## Runs

| Run | Decode tok/s | TPOT | Engine total | Main signal |
| --- | ---: | ---: | ---: | --- |
| `20260612bq` rank-0 labels | `99.803` | `10.022 ms/token` | `10.051 ms` mean | Engine wall time matches endpoint TPOT. |
| `20260612br` all-rank labels | `99.829` | `9.985 ms/token` | `9.942 ms` mean | Rank 3 is the slowest model-forward rank. |

Benchmark shape: p512/o256/c1, streaming completions, `ignore_eos`, no VRAM
sampling.

## EngineCore Attribution

All values are per-token EngineCore step means from the env-gated hook.

| Region | `20260612bq` mean | `20260612br` mean | Interpretation |
| --- | ---: | ---: | --- |
| `total_ms` | `10.051 ms` | `9.942 ms` | The service is paced by the engine step. |
| `future_result_ms` | `9.835 ms` | `9.703 ms` | The dominant wait is inside model execution/completion. |
| `execute_model_submit_ms` | `0.075 ms` | `0.079 ms` | Submit overhead is not the main limiter. |
| `scheduler_schedule_ms` | `0.045 ms` | `0.047 ms` | Python scheduler work is small for c1. |
| `scheduler_update_from_output_ms` | `0.023 ms` | `0.024 ms` | Output update is small. |
| `sample_tokens_submit_ms` | `0.021 ms` | `0.032 ms` | Sample submission is small. |

The first conclusion is negative but useful: optimizing Python scheduling,
OpenAI streaming, or request accounting cannot by itself reach `200 tok/s`.
The target needs the engine wall step to move from about `10 ms/token` to
about `5 ms/token`.

## All-Rank Worker Timing

All-rank labels show real rank skew.

| Rank | `model_forward` mean | `forward_total` mean | `gdn_attention_core_xpu.native` mean |
| ---: | ---: | ---: | ---: |
| 0 | `5.615 ms` | `5.665 ms` | `1.509 ms` |
| 1 | `5.580 ms` | `5.630 ms` | `1.510 ms` |
| 2 | `5.812 ms` | `5.863 ms` | `1.580 ms` |
| 3 | `6.058 ms` | `6.109 ms` | `1.564 ms` |

Rank 3 is about `0.48 ms` slower than rank 1 on `model_forward`, but even the
slowest no-sync rank is still well below the `~9.7 ms` EngineCore
`future_result` wait. The next measurement should find whether the missing
wall time is hidden device completion, collective synchronization,
host/device queueing, batch-queue behavior, or timing-label nesting.

## Quality And Restore

After diagnostic timing, the accepted backend was restored and checked:

- Provenance: both prefix cases passed; sentinels `4752`, `11436`, and `198`
  matched.
- No-thinking Qwen-specific smoke: `pass_all=true` and
  `baseline_match_all=true`.

## Artifacts

- `patches/vllm-qwen36-engine-step-timing-20260612bq.diff`
- `data/qwen36-quark-int8-tp4-engine-step-timing-20260612bq.log`
- `data/qwen36-quark-int8-tp4-engine-step-timing-p512o256-metrics-20260612bq.json`
- `data/qwen36-quark-int8-tp4-engine-step-timing-summary-20260612bq.json`
- `data/qwen36-quark-int8-tp4-engine-allrank-timing-20260612br.log`
- `data/qwen36-quark-int8-tp4-engine-allrank-timing-p512o256-metrics-20260612br.json`
- `data/qwen36-quark-int8-tp4-engine-allrank-timing-summary-20260612br.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-engine-timing-20260612br.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-engine-timing-20260612br.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-engine-timing-nothink-smoke-20260612br.json`

## Next Gates

1. Instrument the `future_result` wait more deeply: worker queue receive,
   collective completion, command-list completion, and output handoff.
2. Rotate or pin rank placement to test whether rank 3 is a physical card,
   PCIe/NUMA, route-skew, or scheduling issue.
3. Build the no-server c1 model-runner ceiling harness to measure the minimum
   possible TPOT with identical tokens and no API scheduler path.
4. Move the oneDNN sidecar from descriptor/probe to one-layer
   execute-and-compare with exact tensor checksums.
5. Test TP2 plus replicas as a latency topology. If TP4 collective pacing is
   the limiter, spare B70s should be used for replicas or target-verifier
   branches instead of every token passing through all four cards.
