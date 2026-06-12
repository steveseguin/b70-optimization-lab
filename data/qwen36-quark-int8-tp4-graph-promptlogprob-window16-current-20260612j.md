# Qwen3.6 Prompt-Logprob Verifier Bucket Probe

This is a sidecar verifier proxy. It uses the accepted Quark INT8 model
through `/v1/completions` with token-id prompts and `prompt_logprobs=1`.
It does not use vLLM speculative scheduling and does not reuse KV.

- base URL: `http://127.0.0.1:18080`
- baseline JSON: `data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json`
- cases: `2`
- window sizes: `[16]`

| Case | Window | Control | Requests | All rank-1 | Accepted / draft | Mean ms | p90 ms | Sidecar request tok/s |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `natural_latency_plan` | 16 | `mutated_first_token` | 1 | 0 | 0/16 | 8696.23 | 8696.23 | 1.84 |
| `natural_latency_plan` | 16 | `perfect_draft` | 1 | 1 | 16/16 | 815.15 | 815.15 | 19.63 |
| `repetitive_kernel_notes` | 16 | `mutated_first_token` | 1 | 0 | 0/16 | 317.02 | 317.02 | 50.47 |
| `repetitive_kernel_notes` | 16 | `perfect_draft` | 1 | 0 | 14/16 | 3399.54 | 3399.54 | 4.71 |

Interpretation:

- `perfect_draft` rows should be all rank-1. If not, the teacher-forced
  sidecar verifier is not semantically aligned with accepted greedy decode.
- `mutated_first_token` rows should accept zero prefix tokens. If not, the
  rejection rule is broken.
- `sidecar_request_tok_s` is conservative because every request re-prefills
  the prefix. It is not the final KV-resident target speed.
