# Ornith 1.5 35B-A3B: recurrent alpha-gate fusion

Date: 2026-08-22 EDT

Status: **accepted target-only package increment; +2.04% matched serving**

## Qwen-derived boundary, validated on Ornith

Ornith reports architecture `qwen35moe`. Its 30 recurrent layers each execute
the following 32-element FP32 chain during single-token decode:

```text
alpha + ssm_dt.bias -> softplus -> multiply by ssm_a
```

The stock SYCL backend already fuses `SOFTPLUS -> MUL`, but leaves the preceding
`ADD` as a separate launch. The new default-off path recognizes only the exact
Ornith node names, types, shapes, layout, source ordering, consumer counts, and
three-node adjacency. It writes and rereads the original ADD destination
through a volatile FP32 pointer before using the backend's existing softplus
expression. Any mismatch falls back to the prior stack.

Enable the complete stack with:

```bash
export GGML_SYCL_FUSED_MOE_ADD_REDUCE=1
export GGML_SYCL_FUSED_ORNITH_CONV_SILU=1
export GGML_SYCL_FUSED_RESIDUAL_RMS_NORM=1
export GGML_SYCL_FUSED_ORNITH_CONCAT_STATE=1
export GGML_SYCL_FUSED_ORNITH_CONCAT_STATE_DIRECT=1
export GGML_SYCL_FUSED_ORNITH_ALPHA_GATE=1
```

The increment removes one launch from each recurrent layer, or another 30
launches per decoded token. The complete package now removes 440 launches per
token.

## Performance

One B70, local SHA-verified GGUF, F16 KV, flash attention, target only. All
measurements used the final library SHA-256
`3887af763ac560ca277dd224ded611b083798dd27f149b7caf886c831460f637`.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7`, pooled mirrored runs | `118.216793`, `116.266630`, `116.228967`, `115.917604` | `118.014641`, `118.093770`, `118.739004`, `117.311448` | **+1.18%** |
| fresh 12-prompt server suite | `112.636416`, `111.423065` | `113.951740`, `114.676800` | **+2.04%** |

The fresh-server candidate mean is `114.314270 tok/s`; both candidate runs
exceeded both controls. The serving metric is the conventional median token
rate for generated tokens 1-100 after TTFT. Every process used 12 unique
prompts exactly once, requested 512 tokens, reported `cached_tokens=0` on every
row, and passed the final measurement gate.

## Correctness

- The same-final-binary forced 128-token greedy comparison was byte-identical
  after removing the dynamic timing footer. Both canonical transcripts hashed
  to `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
- The candidate fired 3,810 alpha-gate fusions, exactly 30 per evaluated token
  after prompt processing.
- The candidate passed 8x repeat stability, arithmetic, exact-copy, and JSON
  schema canaries.
- The complete patch applies cleanly to pinned llama.cpp base
  `9fee29e9435f865ec0b811a783a6471a136d9317`.

Promote the new complete patch. Structured summary:
`../data/2026-08-22-ornith35b-alpha-gate-summary.json`; raw mirrored engine and
server JSON, exactness, and canaries are retained beside it.
