# Qwen3.6 Rolling One-Token Verifier Probe

This re-prefills each accepted output prefix and asks the accepted backend to generate one next token.

- base URL: `http://127.0.0.1:18080`
- baseline JSON: `data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json`
- seed: `20260611`
- max tokens per case: `32`
- all matched: `False`

| Case | Checked | Matched | First mismatch | Mean ms | p90 ms | Rolling request tok/s |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| `natural_latency_plan` | 18 | 17 | pos 17 expected `11436` got `321` | 74.83 | 80.87 | 13.36 |
| `repetitive_kernel_notes` | 15 | 14 | pos 14 expected `4752` got `6126` | 73.80 | 77.18 | 13.55 |

Interpretation:

- If this fails, full-prefix re-prefill verification is not aligned with accepted incremental decode.
- If this passes while prompt-logprob multi-token windows fail, the right next target is a rolling verifier with resident KV, not teacher-forced multi-token prefill.
- `rolling_request_tok_s` includes full re-prefill cost and is not a production target.
