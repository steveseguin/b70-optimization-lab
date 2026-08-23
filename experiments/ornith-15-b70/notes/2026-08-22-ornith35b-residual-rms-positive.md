# Ornith 1.5 35B-A3B: residual + RMSNorm fusion

Date: 2026-08-22 EDT

Status: **accepted target-only package increment; +1.37% matched serving**

## Qwen-derived boundary

Ornith 1.5 35B uses the `qwen35moe` architecture. Its decode graph contains
two 2048-wide residual additions per layer: one after attention and one after
the expert block. Each feeds the backend's existing fused
`RMS_NORM -> MUL` kernel, leaving 80 small residual `ADD` launches/token.

The new default-off path recognizes only named `attn_residual-*` and `l_out-*`
chains with exact FP32 shapes and a single-use RMS output. Unlike a normal
single-use fusion, it retains the residual tensor because later skip
connections consume it. The kernel writes and rereads the original residual
buffer through a volatile FP32 pointer, then uses the stock RMS reduction order
and final norm-weight expression.

Enable the complete stack with:

```bash
export GGML_SYCL_FUSED_MOE_ADD_REDUCE=1
export GGML_SYCL_FUSED_ORNITH_CONV_SILU=1
export GGML_SYCL_FUSED_RESIDUAL_RMS_NORM=1
```

The candidate matched 80 boundaries/token, bringing the package stack to 350
removed launches/token.

## Performance

One B70, local directly verified GGUF, F16 KV, flash attention, target only.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7` | `109.849552`, `109.407959` | `111.982239`, `111.670318` | **+2.00%** |
| fresh 12-prompt server suite | `106.162089`, `106.476358` | `107.182326`, `108.369597` | **+1.37%** |

The server metric is the median token rate for generated tokens 1-100 after
TTFT. All four fresh runs used 12 unique prompts exactly once, returned 512
tokens, reported `cached_tokens=0` for every row, and passed the final gate.

## Correctness

- The same-binary forced 128-token greedy comparison was byte-identical after
  excluding only the CLI's dynamic timing footer. Both canonical outputs
  hashed to `0143ca510271d95d859b69427824e56c4c502c9a41ccadac28d5726547e31ce0`.
- The candidate fired 10,160 times in that run, confirming all 80 intended
  boundaries per evaluated token.
- The candidate server passed 8x repeat stability, arithmetic, exact-copy, and
  JSON-schema canaries.

Promote the complete patch in the Ornith package. Structured summary:
`../data/2026-08-22-ornith35b-residual-rms-summary.json`; raw engine/server JSON
and canaries are retained beside it.
