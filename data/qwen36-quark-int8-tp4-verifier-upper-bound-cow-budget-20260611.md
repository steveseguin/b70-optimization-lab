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

## COW / Scheduler Overhead Budget

The values below are additional milliseconds per speculative verifier
step that can be spent on copy-on-write request/KV setup, scheduler
bookkeeping, scratch block allocation/free, and result commit before
falling below `200.0 tok/s`.

Positive budget means the bucket could still hit the target after that
much extra overhead. Negative budget means the bucket already misses
the target at that acceptance fraction.

| Bucket | Accept frac | Expected tokens/step | Model budget ms | Visible budget ms | Endpoint-scaled budget ms |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.0% | 1.000 | -7.241 | -11.491 | -6.135 |
| 1 | 25.0% | 1.000 | -7.241 | -11.491 | -6.135 |
| 1 | 50.0% | 1.000 | -7.241 | -11.491 | -6.135 |
| 1 | 75.0% | 1.000 | -7.241 | -11.491 | -6.135 |
| 1 | 90.0% | 1.000 | -7.241 | -11.491 | -6.135 |
| 1 | 100.0% | 1.000 | -7.241 | -11.491 | -6.135 |
| 3 | 0.0% | 1.000 | -10.269 | -12.184 | -9.163 |
| 3 | 25.0% | 1.500 | -7.769 | -9.684 | -6.110 |
| 3 | 50.0% | 2.000 | -5.269 | -7.184 | -3.057 |
| 3 | 75.0% | 2.500 | -2.769 | -4.684 | -0.003 |
| 3 | 90.0% | 2.800 | -1.269 | -3.184 | 1.828 |
| 3 | 100.0% | 3.000 | -0.269 | -2.184 | 3.050 |
| 6 | 0.0% | 1.000 | -10.544 | -12.102 | -9.437 |
| 6 | 25.0% | 2.250 | -4.294 | -5.852 | -1.804 |
| 6 | 50.0% | 3.500 | 1.956 | 0.398 | 5.829 |
| 6 | 75.0% | 4.750 | 8.206 | 6.648 | 13.462 |
| 6 | 90.0% | 5.500 | 11.956 | 10.398 | 18.041 |
| 6 | 100.0% | 6.000 | 14.456 | 12.898 | 21.095 |
| 8 | 0.0% | 1.000 | -13.883 | -15.420 | -12.777 |
| 8 | 25.0% | 2.750 | -5.133 | -6.670 | -2.091 |
| 8 | 50.0% | 4.500 | 3.617 | 2.080 | 8.596 |
| 8 | 75.0% | 6.250 | 12.367 | 10.830 | 19.282 |
| 8 | 90.0% | 7.300 | 17.617 | 16.080 | 25.694 |
| 8 | 100.0% | 8.000 | 21.117 | 19.580 | 29.968 |

Interpretation:

- Bucket 3 is already near the 200 tok/s line on synchronized model-forward timing and clears it on endpoint-scaled timing.
- Buckets 6 and 8 have enough sublinear verifier scaling to clear 200 tok/s if draft correctness and scheduler state are fixed.
- The rejected n-gram and hybrid MTP runs failed quality, so these numbers are only an upper bound for a future exact proposer.
- If a true perfect-draft harness comes in materially below this estimate, pivot back to persistent MoE/layout work.
- The COW patch should log actual scratch/fork overhead and compare it to the endpoint-scaled budget above.
