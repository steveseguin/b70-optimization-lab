# Timing observations

One observation per prompt; no response reuse. Decode uses (N−1)/(last−first) from controller committed-token timestamps. The first99 column uses 99/(timestamp100−timestamp1). TTFT runs from request scheduler start to first committed output; it includes prompt reading and first-use runtime work, and excludes the preceding reset. Pure prefill was not separately timed.

| Prompt | Outputs | Full response tok/s | First99 tok/s | TTFT s |
| --- | ---: | ---: | ---: | ---: |
| incident-retrospective | 512 | 40.1995 | 35.4887 | 120.6317 |
| code-review | 512 | 42.6942 | 40.5965 | 1.6034 |
| customer-email | 333 | 41.6487 | 42.0694 | 1.4117 |
| sql-debugging | 512 | 44.2758 | 42.5867 | 1.4950 |
| release-plan | 512 | 39.3747 | 38.3409 | 1.2115 |
| benchmark-analysis | 512 | 42.7342 | 45.9687 | 1.1839 |
| architecture-tradeoff | 512 | 44.1067 | 46.3581 | 1.2232 |
| bug-report-synthesis | 512 | 40.6931 | 39.7360 | 1.3057 |
| technical-guide | 512 | 43.0950 | 40.9801 | 1.2748 |
| risk-register | 512 | 40.2252 | 43.7779 | 1.1320 |
| performance-hypotheses | 512 | 41.4963 | 44.9253 | 1.1376 |
| decision-memo | 512 | 39.6011 | 45.9062 | 1.0706 |

Full-response median: **41.57251906798183 tok/s**; pooled interval rate: **41.6146260353132 tok/s**. Six-class median of first99 class medians: **42.68474604432647 tok/s**. All-prompt first99 median: **42.32804057372263 tok/s**. TTFT median: **1.2490112314699218 s**; first request: **120.63172018399928 s**. Do not treat the first request as a pure prompt-reading measurement.

[Exact metrics, endpoint accounting, per-class distributions and LocalMaxxing disposition](../persistent-rolling-suite-window-metrics.json). [Independent raw-witness review](../persistent-rolling-suite-run-review.json).

The earlier four-card full-response median was 42.311880797977615; the two-card service median was 47.97057758420032. The latter uses a different timing observation layer. No first99 baseline is inferred from either aggregate, and these are not certified cross-path speed ratios.
