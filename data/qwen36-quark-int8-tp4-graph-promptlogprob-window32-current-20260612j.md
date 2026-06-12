# Qwen3.6 Prompt-Logprob Verifier Bucket Probe

This is a sidecar verifier proxy. It uses the accepted Quark INT8 model
through `/v1/completions` with token-id prompts and `prompt_logprobs=1`.
It does not use vLLM speculative scheduling and does not reuse KV.

- base URL: `http://127.0.0.1:18080`
- baseline JSON: `data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json`
- cases: `2`
- window sizes: `[32]`

| Case | Window | Control | Requests | All rank-1 | Accepted / draft | Mean ms | p90 ms | Sidecar request tok/s |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `natural_latency_plan` | 32 | `perfect_draft` | 1 | 0 | 14/32 | 371.20 | 371.20 | 86.21 |
| `repetitive_kernel_notes` | 32 | `perfect_draft` | 1 | 0 | 5/32 | 353.92 | 353.92 | 90.42 |

Interpretation:

- `perfect_draft` rows should be all rank-1. If not, the teacher-forced
  sidecar verifier is not semantically aligned with accepted greedy decode.
- `mutated_first_token` rows should accept zero prefix tokens. If not, the
  rejection rule is broken.
- `sidecar_request_tok_s` is conservative because every request re-prefills
  the prefix. It is not the final KV-resident target speed.
