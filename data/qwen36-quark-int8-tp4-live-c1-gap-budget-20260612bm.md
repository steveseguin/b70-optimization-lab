# Qwen3.6 C1 200 Tok/s Gap Budget

Input: `data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-20260612bm.json`
Target: `200.000 tok/s` = `5.000 ms/token`.
Current corrected decode: `100.013 tok/s`.
Current decode histogram: `9.980 ms/token`.
Required saving: `4.980 ms/token` (`49.9%` of current decode latency).
Required speedup over current corrected decode: `2.000x`.

## Live Histogram

- Queue: `0.0086 ms/request`.
- Prefill: `69.145 ms/request` for the measured prompt.
- Decode: `5109.901 ms/request`.
- Inter-token latency: `10.000 ms/token`.
- Iteration tokens per step: `2.000`.

## Stage Speedup Implication

| Assumed optimized-stage share of decode | Required stage speedup |
| ---: | ---: |
| 25% | impossible |
| 33% | impossible |
| 40% | impossible |
| 50% | 505.98x |
| 60% | 5.94x |
| 70% | 3.48x |
| 80% | 2.66x |
| 90% | 2.24x |

Interpretation: a narrow micro-optimization cannot reach 200 tok/s alone. The winning path must remove about half the decode token latency, either through a large MoE/command-path improvement, target-verified multi-token acceptance, or a lower-latency topology that keeps the same model output.

## Next Gates

- Do not spend time on queue/frontdoor fixes first; measured queue time is effectively zero for c1.
- Use the sidecar/oneDNN path only if it can attack multi-millisecond decode latency, not just a microsecond GEMM slice.
- Add device-side token-step timing before committing to a custom kernel so attention, GDN, MoE, collectives, sampler, and scheduler costs are ranked.
- Treat target-verified MTP/DFlash/ngram transactions as a separate 2x-class path because they can reduce effective emitted-token latency without changing accepted output.
- Revisit TP2/single-lane topology only with exact current-model canaries, because TP4 may be paying collective/control overhead for c1.
