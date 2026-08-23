# Ornith 1.5 35B-A3B: recurrent concat + state update fusion

Date: 2026-08-22 EDT

Status: **accepted target-only package increment; +2.74% matched serving**

## Qwen-derived state boundary

Ornith 1.5 35B reports architecture `qwen35moe`. Each of its 30 recurrent
layers builds a `[4,8192]` FP32 convolution input by concatenating three old
state rows with one current row, then copies rows 1-3 into persistent state.
The stock path launches one kernel for `CONCAT` and one for the state `CPY`.

This candidate transfers a narrow optimization from the lab's earlier Qwen
work. It still materializes the complete convolution input for the accepted
convolution/SiLU path and writes the same persistent-state destination. The
matcher requires the exact names, types, shapes, strides, non-overlap, expected
convolution consumer, and the state copy as the next real compute node. Any
mismatch uses stock execution.

Enable the complete stack with:

```bash
export GGML_SYCL_FUSED_MOE_ADD_REDUCE=1
export GGML_SYCL_FUSED_ORNITH_CONV_SILU=1
export GGML_SYCL_FUSED_RESIDUAL_RMS_NORM=1
export GGML_SYCL_FUSED_ORNITH_CONCAT_STATE=1
```

The candidate matched 30 boundaries/token, bringing the package stack to 380
removed launches/token.

## Performance

One B70, local SHA-verified GGUF, F16 KV, flash attention, target only.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7` | `111.374584`, `111.670956` | `115.793704`, `115.120218` | **+3.53%** |
| fresh 12-prompt server suite | `106.397958`, `105.136631` | `108.368740`, `108.954675` | **+2.74%** |

The server metric is the conventional median token rate for generated tokens
1-100 after TTFT. All four fresh runs used 12 unique prompts exactly once,
requested 512 tokens, reported `cached_tokens=0` for every row, and passed the
final freshness gate.

## Correctness

- The same-binary forced 128-token greedy comparison was byte-identical. Both
  outputs hashed to
  `d6e037cde42571a97f0a8bd03dba5fbf9a6db32fa7362c973864b1159880f790`.
- The candidate fired 3,810 times in that run, confirming all 30 intended
  recurrent boundaries per evaluated token.
- The candidate server passed 8x repeat stability, arithmetic, exact-copy, and
  JSON-schema canaries.

Promote the complete patch in the Ornith package. Structured summary:
`../data/2026-08-22-ornith35b-concat-state-summary.json`; raw engine/server JSON
and canaries are retained beside it.
