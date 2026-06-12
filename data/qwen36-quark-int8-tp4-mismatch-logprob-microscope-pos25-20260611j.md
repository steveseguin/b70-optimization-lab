# Qwen3.6 Mismatch Logprob Microscope

- case: `natural_latency_plan`
- position: `25`
- expected token: `198` `'\n'`
- streaming token: `271` `'\n\n'`

| Probe | Top token | Expected rank/logprob | Streaming rank/logprob |
| --- | --- | --- | --- |
| streaming-input | `271 '\n\n'` | rank 2, logprob -0.797245 | rank 1, logprob -0.672245 |
| accepted-decode | `198 '\n'` | rank 1, logprob -0.737163 | rank 2, logprob -0.737163 |
| rolling-refill-next | `271 '\n\n'` | rank 2, logprob -0.936827 | rank 1, logprob -0.561827 |
| prompt-logprob-refill | `198 '\n'` | rank 1, logprob -0.720617 | rank 2, logprob -0.720617 |

Interpretation:

Accepted decode and prompt-logprob refill put the expected newline and streaming double-newline on an exact logprob tie, while streaming-input and rolling re-prefill both rank the double-newline first. This points at tie/order or resident-state divergence, so an external replay sidecar is still not acceptable as an exact-token verifier. The next quality-safe speed path should use the accepted request state directly, for example in-engine copy-on-write KV/request forking.
