# Qwen3.6 C1 Stage Ledger

Endpoint decode: `9.980 ms/token`.
Target: `5.000 ms/token`.
Required saving: `4.980 ms/token`.

## Timing Proxies

| source | model-forward proxy | endpoint minus proxy | theoretical tok/s if only outside/proxy gap vanished | notes |
| --- | ---: | ---: | ---: | --- |
| nosync_label_timing | 5.467 ms | 4.513 ms | 182.9 | Pure decode timing-step proxy; low overhead but not identical to the live endpoint run. |
| sync_modelonly | 8.433 ms | 1.547 ms | 118.6 | Synchronized model-forward-only proxy; closer to endpoint latency but perturbs the run. |

## Interpretation

- The endpoint c1 decode path is about 9.98 ms/token, while prior pure-decode timing proxies range from about 5.46 ms to 8.43 ms depending on instrumentation.
- The gap between endpoint decode and the nosync model-forward proxy is about 4.52 ms/token, almost the entire 4.98 ms/token saving needed for 200 tok/s.
- Even if the endpoint matched the nosync proxy exactly, throughput would be about 183 tok/s, so we still need either a smaller model-forward improvement or target-verified multi-token acceptance.
- The sync model-only proxy shows about 8.43 ms/token, which means synchronization or instrumentation can erase most of the apparent headroom; future profiling must be device-side and low overhead.
- Nested timing labels such as GDN, MoE, and all-reduce are useful directionally, but they are not exclusive wall-time slices and must not be summed into a token budget.
- A concrete no-spec path to 200 tok/s would need endpoint/outside overhead near the nosync timing path plus at least 0.467 ms/token shaved from the model-forward proxy.

## Required Next Instrumentation

- Add one low-overhead per-token timing-step capture on the accepted backend, with model_forward, scheduler/output, sampler, and streaming boundaries in the same request.
- For XPU device work, prefer queue/event timestamps or existing low-overhead timers; avoid forced synchronization in the hot path.
- Make MoE timing exclusive enough to separate route packing, GEMM1, activation/quant, GEMM2, gather, and all-reduce without double-counting nested labels.
- Tie each timing trace to request id, prompt/output token counts, graph bucket, and canary/provenance result.
