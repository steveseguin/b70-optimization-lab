# Qwen3.6 Verifier Upper-Bound Estimate

This is a timing-derived upper-bound analysis, not a promoted endpoint result.
It assumes the current Quark INT8 model remains the final verifier and asks
how much speed would be available if a proposer supplied correct drafts.

- Baseline endpoint steady-state tok/s: `99.769699`
- Baseline bucket-1 model-forward timing: `12.240958 ms`
- Target: `200.0 tok/s`

| Bucket | Steps | Model ms | Visible ms | Perfect model tok/s | Perfect visible tok/s | Endpoint-scaled tok/s | Accept frac for 200 (model) | Source |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 119 | 12.241 | 16.491 | 81.69 | 60.64 | 99.77 | n/a | `qwen36-quark-int8-tp4-ngram2-bucket-timing-natural-summary-20260611.json` |
| 3 | 33 | 15.269 | 17.184 | 196.47 | 174.58 | 239.95 | 100.0% | `qwen36-quark-int8-tp4-ngram2-bucket-timing-natural-summary-20260611.json` |
| 6 | 17 | 15.544 | 17.102 | 386.01 | 350.84 | 471.42 | 42.2% | `qwen36-quark-int8-tp4-ngram5-bucket-timing-repetitive-summary-20260611.json` |
| 8 | 9 | 18.883 | 20.420 | 423.66 | 391.77 | 517.41 | 39.7% | `qwen36-quark-int8-tp4-ngram7-bucket-timing-repetitive-summary-20260611.json` |

Interpretation:

- Bucket 3 is already near the 200 tok/s line on synchronized model-forward timing and clears it on endpoint-scaled timing.
- Buckets 6 and 8 have enough sublinear verifier scaling to clear 200 tok/s if draft correctness and scheduler state are fixed.
- The rejected n-gram and hybrid MTP runs failed quality, so these numbers are only an upper bound for a future exact proposer.
- If a true perfect-draft harness comes in materially below this estimate, pivot back to persistent MoE/layout work.
