# Packet138 phase-1 results

**All rates and cache outcomes below are projections, not device speed measurements.**

Decision: `close_gain_or_traffic_gate_not_met`. Phase-2 design allowed by this gate: **false**.

The coordinator captured 48 accepted tokens on each of twelve independent held-out prompts and one separate sanity prompt. All 624 output tokens match their pinned references; the sanity prompt is excluded from analysis. Exact same-layer CPU replay agrees on all 14,155,776 BF16 logits and 276,480 expert IDs.

The modeled 58v control is 28.8762 to 28.8762 tok/s with 97.026 to 100.026 MB/token read zero-copy. Its speed is not a measured 58v result. The unchanged one-card measured record remains 26.228599 tok/s.

The highest projected gain in any registered scenario is +5.750% (router_input, width 12, optimistic). This is a diagnostic best case, not a selected benchmark headline.

Even that case has 248 late batches out of 9217 submitted. It moves 66.106 MB/token by prefetch, including 42.039 MB/token not used by the predicted next layer. No registered case fits every copy inside its assumed window.

| Predictor | Width | Recall | Zero-copy MB/token | Projected tok/s | Gain vs modeled control | Every copy fits all scenarios? |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| router_input | 10 | 66.47% | 67.277 to 80.271 | 24.839 to 30.370 | -13.98 to 5.17% | no |
| router_input | 12 | 72.46% | 64.681 to 82.778 | 24.154 to 30.536 | -16.35 to 5.75% | no |
| router_input | 16 | 79.93% | 66.708 to 88.337 | 22.777 to 30.276 | -21.12 to 4.85% | no |
| residual_stream0 | 10 | 47.81% | 85.638 to 94.960 | 23.483 to 28.888 | -18.68 to 0.04% | no |
| residual_stream0 | 12 | 52.93% | 85.680 to 96.538 | 22.793 to 28.722 | -21.07 to -0.53% | no |
| residual_stream0 | 16 | 60.56% | 93.302 to 100.022 | 21.559 to 27.681 | -25.34 to -4.14% | no |
| residual_stream1 | 10 | 46.07% | 88.909 to 98.772 | 22.162 to 28.234 | -23.25 to -2.23% | no |
| residual_stream1 | 12 | 50.65% | 95.925 to 102.514 | 21.358 to 27.368 | -26.04 to -5.22% | no |
| residual_stream1 | 16 | 57.64% | 109.644 to 111.143 | 20.058 to 25.479 | -30.54 to -11.76% | no |
| residual_stream2 | 10 | 22.73% | 97.152 to 102.842 | 23.817 to 28.186 | -17.52 to -2.39% | no |
| residual_stream2 | 12 | 25.24% | 98.918 to 105.383 | 23.259 to 27.952 | -19.45 to -3.20% | no |
| residual_stream2 | 16 | 29.44% | 105.915 to 110.901 | 22.220 to 27.287 | -23.05 to -5.51% | no |
| residual_stream3 | 10 | 53.84% | 82.084 to 94.012 | 23.130 to 29.043 | -19.90 to 0.58% | no |
| residual_stream3 | 12 | 59.21% | 83.550 to 96.720 | 22.245 to 28.719 | -22.96 to -0.54% | no |
| residual_stream3 | 16 | 66.89% | 95.646 to 103.231 | 20.944 to 27.212 | -27.47 to -5.76% | no |

## Charged traffic

| Predictor | Width | Prefetch MB/token | Wrong prefetch MB/token | Late batches/token |
| --- | ---: | ---: | ---: | ---: |
| router_input | 10 | 44.907 to 49.857 | 26.051 to 29.442 | 0.184 to 12.497 |
| router_input | 12 | 55.197 to 66.106 | 35.873 to 42.039 | 0.431 to 13.503 |
| router_input | 16 | 76.111 to 96.213 | 56.222 to 70.098 | 1.292 to 14.036 |
| residual_stream0 | 10 | 50.295 to 53.989 | 37.822 to 40.512 | 3.269 to 14.325 |
| residual_stream0 | 12 | 61.720 to 68.049 | 48.049 to 52.809 | 4.788 to 15.750 |
| residual_stream0 | 16 | 83.615 to 99.220 | 68.018 to 80.393 | 8.238 to 17.193 |
| residual_stream1 | 10 | 72.258 to 89.166 | 57.063 to 69.745 | 7.455 to 16.517 |
| residual_stream1 | 12 | 86.332 to 111.007 | 70.028 to 89.040 | 9.889 to 16.899 |
| residual_stream1 | 16 | 110.525 to 147.967 | 92.717 to 122.335 | 13.035 to 16.002 |
| residual_stream2 | 10 | 40.436 to 44.471 | 33.260 to 36.454 | 2.521 to 12.047 |
| residual_stream2 | 12 | 48.788 to 54.043 | 40.780 to 44.770 | 3.432 to 13.220 |
| residual_stream2 | 16 | 65.136 to 71.148 | 55.648 to 60.713 | 5.264 to 14.767 |
| residual_stream3 | 10 | 56.898 to 62.484 | 39.983 to 43.629 | 4.167 to 15.363 |
| residual_stream3 | 12 | 71.870 to 80.086 | 53.131 to 58.898 | 6.236 to 16.630 |
| residual_stream3 | 16 | 94.792 to 117.270 | 75.278 to 90.953 | 10.168 to 17.812 |

## Limits and evidence

The registered scenarios charge wrong and late copies, predictor work, publication and extra planning. The 18 GB cache keeps the original global LRU and packed expert sizes. Prediction is disabled during historical prompt prefill. A positive candidate is checked again with shorter decode windows; prefill timing is unchanged.

The old receipts lack measured layer clocks. Per-layer time, bandwidth fractions, router costs and the hidden share of 58v cache work are explicit assumptions. Remote penalties are historical K1 proxies. These estimates cannot certify a speedup or replace a phase-2 device quality check. This 48-token calibration capture is not the realistic performance suite.

- [Capture hashes and exactness](evidence/capture-inputs.json)
- [Exact replay and per-prompt/layer recall](evidence/router-replay.json.gz)
- [Recall by layer and class](evidence/recall-summary.json)
- [All cache outcomes and projections](evidence/cache-projections.json.gz)
- [Timing inputs and assumptions](evidence/timing-inputs.json)
- [CPU continuation receipt](evidence/continuation.json)
- [Method and idea credit](ANALYSIS.md)
- [Retention and restoration](RETENTION.md)
