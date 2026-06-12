# Qwen3.6 Prompt-Logprob Verifier Bucket Probe

This is a sidecar verifier proxy. It uses the accepted Quark INT8 model
through `/v1/completions` with token-id prompts and `prompt_logprobs=1`.
It does not use vLLM speculative scheduling and does not reuse KV.

- base URL: `http://127.0.0.1:18080`
- baseline JSON: `data/qwen36-quark-int8-tp4-accepted-noasync-metadata-p512o128-20260611f.json`
- cases: `2`
- window sizes: `[1, 2, 4, 8, 16, 32]`

| Case | Window | Control | Requests | All rank-1 | Accepted / draft | Mean ms | p90 ms | Sidecar request tok/s |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `natural_latency_plan` | 1 | `mutated_first_token` | 1 | 0 | 0/1 | 102.60 | 102.60 | 9.75 |
| `natural_latency_plan` | 1 | `perfect_draft` | 2 | 2 | 2/2 | 112.12 | 121.24 | 8.92 |
| `natural_latency_plan` | 2 | `mutated_first_token` | 1 | 0 | 0/2 | 99.46 | 99.46 | 20.11 |
| `natural_latency_plan` | 2 | `perfect_draft` | 2 | 2 | 4/4 | 102.35 | 103.98 | 19.54 |
| `natural_latency_plan` | 4 | `mutated_first_token` | 1 | 0 | 0/4 | 100.08 | 100.08 | 39.97 |
| `natural_latency_plan` | 4 | `perfect_draft` | 2 | 2 | 8/8 | 100.13 | 100.94 | 39.95 |
| `natural_latency_plan` | 8 | `mutated_first_token` | 1 | 0 | 0/8 | 100.27 | 100.27 | 79.78 |
| `natural_latency_plan` | 8 | `perfect_draft` | 2 | 2 | 16/16 | 413.87 | 663.13 | 19.33 |
| `natural_latency_plan` | 16 | `mutated_first_token` | 1 | 0 | 0/16 | 3331.64 | 3331.64 | 4.80 |
| `natural_latency_plan` | 16 | `perfect_draft` | 2 | 1 | 17/32 | 4410.66 | 7557.58 | 3.63 |
| `natural_latency_plan` | 32 | `mutated_first_token` | 1 | 0 | 0/32 | 117.01 | 117.01 | 273.48 |
| `natural_latency_plan` | 32 | `perfect_draft` | 2 | 0 | 29/64 | 744.91 | 754.49 | 42.96 |
| `repetitive_kernel_notes` | 1 | `mutated_first_token` | 1 | 0 | 0/1 | 3718.78 | 3718.78 | 0.27 |
| `repetitive_kernel_notes` | 1 | `perfect_draft` | 2 | 2 | 2/2 | 4123.51 | 7241.47 | 0.24 |
| `repetitive_kernel_notes` | 2 | `mutated_first_token` | 1 | 0 | 0/2 | 97.31 | 97.31 | 20.55 |
| `repetitive_kernel_notes` | 2 | `perfect_draft` | 2 | 2 | 4/4 | 97.42 | 97.83 | 20.53 |
| `repetitive_kernel_notes` | 4 | `mutated_first_token` | 1 | 0 | 0/4 | 97.44 | 97.44 | 41.05 |
| `repetitive_kernel_notes` | 4 | `perfect_draft` | 2 | 2 | 8/8 | 96.87 | 97.07 | 41.29 |
| `repetitive_kernel_notes` | 8 | `mutated_first_token` | 1 | 0 | 0/8 | 97.78 | 97.78 | 81.82 |
| `repetitive_kernel_notes` | 8 | `perfect_draft` | 2 | 2 | 16/16 | 97.27 | 97.47 | 82.24 |
| `repetitive_kernel_notes` | 16 | `mutated_first_token` | 1 | 0 | 0/16 | 98.01 | 98.01 | 163.26 |
| `repetitive_kernel_notes` | 16 | `perfect_draft` | 2 | 1 | 25/32 | 518.19 | 855.09 | 30.88 |
| `repetitive_kernel_notes` | 32 | `mutated_first_token` | 1 | 0 | 0/32 | 101.99 | 101.99 | 313.75 |
| `repetitive_kernel_notes` | 32 | `perfect_draft` | 1 | 0 | 5/32 | 8022.78 | 8022.78 | 3.99 |

Interpretation:

- `perfect_draft` rows should be all rank-1. If not, the teacher-forced
  sidecar verifier is not semantically aligned with accepted greedy decode.
- `mutated_first_token` rows should accept zero prefix tokens. If not, the
  rejection rule is broken.
- `sidecar_request_tok_s` is conservative because every request re-prefills
  the prefix. It is not the final KV-resident target speed.
