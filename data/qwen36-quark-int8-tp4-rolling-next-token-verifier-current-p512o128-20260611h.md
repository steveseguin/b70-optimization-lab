# Qwen3.6 Rolling One-Token Verifier Probe

This re-prefills each accepted output prefix and asks the accepted backend to generate one next token.

- base URL: `http://127.0.0.1:18080`
- baseline JSON: `data/qwen36-quark-int8-tp4-accepted-current-p512o128-20260611g.json`
- max tokens per case: `128`
- all matched: `False`

| Case | Checked | Matched | First mismatch | Mean ms | p90 ms | Rolling request tok/s |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| `natural_latency_plan` | 128 | 121 | pos 17 expected `11436` got `321` | 75.58 | 79.15 | 13.23 |
| `repetitive_kernel_notes` | 128 | 126 | pos 14 expected `4752` got `6126` | 74.74 | 77.35 | 13.38 |

Interpretation:

- If this fails, full-prefix re-prefill verification is not aligned with accepted incremental decode.
- If this passes while prompt-logprob multi-token windows fail, the right next target is a rolling verifier with resident KV, not teacher-forced multi-token prefill.
- `rolling_request_tok_s` includes full re-prefill cost and is not a production target.
