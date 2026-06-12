# Qwen3.6 Prompt-Logprob Verifier Bucket Probe

This is a sidecar verifier proxy. It uses the accepted Quark INT8 model
through `/v1/completions` with token-id prompts and `prompt_logprobs=1`.
It does not use vLLM speculative scheduling and does not reuse KV.

- base URL: `http://127.0.0.1:18080`
- baseline JSON: `data/qwen36-quark-int8-tp4-accepted-current-p512o128-20260611g.json`
- cases: `2`
- window sizes: `[1, 2, 4, 8, 16, 32]`

| Case | Window | Control | Requests | All rank-1 | Accepted / draft | Mean ms | p90 ms | Sidecar request tok/s |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `natural_latency_plan` | 1 | `mutated_first_token` | 1 | 0 | 0/1 | 301.25 | 301.25 | 3.32 |
| `natural_latency_plan` | 1 | `perfect_draft` | 2 | 2 | 2/2 | 422.10 | 679.17 | 2.37 |
| `natural_latency_plan` | 2 | `mutated_first_token` | 1 | 0 | 0/2 | 99.01 | 99.01 | 20.20 |
| `natural_latency_plan` | 2 | `perfect_draft` | 2 | 2 | 4/4 | 100.37 | 100.72 | 19.93 |
| `natural_latency_plan` | 4 | `mutated_first_token` | 1 | 0 | 0/4 | 99.54 | 99.54 | 40.18 |
| `natural_latency_plan` | 4 | `perfect_draft` | 2 | 2 | 8/8 | 100.41 | 101.43 | 39.84 |
| `natural_latency_plan` | 8 | `mutated_first_token` | 1 | 0 | 0/8 | 99.50 | 99.50 | 80.40 |
| `natural_latency_plan` | 8 | `perfect_draft` | 2 | 2 | 16/16 | 418.04 | 670.71 | 19.14 |
| `natural_latency_plan` | 16 | `mutated_first_token` | 1 | 0 | 0/16 | 3544.14 | 3544.14 | 4.51 |
| `natural_latency_plan` | 16 | `perfect_draft` | 2 | 1 | 17/32 | 4464.21 | 7403.01 | 3.58 |
| `natural_latency_plan` | 32 | `mutated_first_token` | 1 | 0 | 0/32 | 251.50 | 251.50 | 127.24 |
| `natural_latency_plan` | 32 | `perfect_draft` | 2 | 0 | 15/64 | 811.90 | 889.07 | 39.41 |
| `repetitive_kernel_notes` | 1 | `mutated_first_token` | 1 | 0 | 0/1 | 4032.18 | 4032.18 | 0.25 |
| `repetitive_kernel_notes` | 1 | `perfect_draft` | 2 | 2 | 2/2 | 4186.34 | 7063.83 | 0.24 |
| `repetitive_kernel_notes` | 2 | `mutated_first_token` | 1 | 0 | 0/2 | 97.55 | 97.55 | 20.50 |
| `repetitive_kernel_notes` | 2 | `perfect_draft` | 2 | 2 | 4/4 | 99.93 | 100.96 | 20.01 |
| `repetitive_kernel_notes` | 4 | `mutated_first_token` | 1 | 0 | 0/4 | 102.82 | 102.82 | 38.90 |
| `repetitive_kernel_notes` | 4 | `perfect_draft` | 2 | 2 | 8/8 | 106.49 | 107.50 | 37.56 |
| `repetitive_kernel_notes` | 8 | `mutated_first_token` | 1 | 0 | 0/8 | 105.33 | 105.33 | 75.95 |
| `repetitive_kernel_notes` | 8 | `perfect_draft` | 2 | 1 | 14/16 | 100.32 | 101.78 | 79.74 |
| `repetitive_kernel_notes` | 16 | `mutated_first_token` | 1 | 0 | 0/16 | 103.01 | 103.01 | 155.32 |
| `repetitive_kernel_notes` | 16 | `perfect_draft` | 2 | 0 | 15/32 | 539.85 | 889.43 | 29.64 |
| `repetitive_kernel_notes` | 32 | `mutated_first_token` | 1 | 0 | 0/32 | 99.38 | 99.38 | 321.98 |
| `repetitive_kernel_notes` | 32 | `perfect_draft` | 2 | 1 | 37/64 | 3924.46 | 6606.41 | 8.15 |

Interpretation:

- `perfect_draft` rows should be all rank-1. If not, the teacher-forced
  sidecar verifier is not semantically aligned with accepted greedy decode.
- `mutated_first_token` rows should accept zero prefix tokens. If not, the
  rejection rule is broken.
- `sidecar_request_tok_s` is conservative because every request re-prefills
  the prefix. It is not the final KV-resident target speed.
