# Ornith 1.5 35B-A3B: direct recurrent gather + concat/state fusion

Date: 2026-08-22 EDT

Status: **accepted target-only package increment; +1.12% matched serving**

## Qwen-lineage transfer, narrowed for Ornith

Ornith reports architecture `qwen35moe`, so the lab's earlier Qwen recurrent
state work is a useful candidate map. It is not assumed to be graph-equivalent:
this matcher requires Ornith's exact one-row, 3-by-8192 FP32 persistent state,
single index, shape-view chain, `[4,8192]` concat, convolution consumer, state
destination, node order, names, strides, element counts, and non-overlap.

The accepted parent fusion still launched `GET_ROWS`, then fused `CONCAT` with
the persistent-state `CPY`. This increment skips the gather too. One work-item
owns each channel, loads all three old state values before any overlapping
write, and materializes every graph-visible result:

- the original gathered state;
- the complete four-row convolution input;
- the shifted persistent state `[old1, old2, current]`.

`SSM_CONV` remains separate and continues through the already-validated
convolution/SiLU kernel. This avoids the in-place state race and broad graph
bypass that made the earlier direct-state experiment correctness-negative.
Any matcher failure uses the accepted parent path.

Enable the complete stack with:

```bash
export GGML_SYCL_FUSED_MOE_ADD_REDUCE=1
export GGML_SYCL_FUSED_ORNITH_CONV_SILU=1
export GGML_SYCL_FUSED_RESIDUAL_RMS_NORM=1
export GGML_SYCL_FUSED_ORNITH_CONCAT_STATE=1
export GGML_SYCL_FUSED_ORNITH_CONCAT_STATE_DIRECT=1
```

The candidate matched 30 boundaries/token, replacing the parent concat/state
kernel and the stock gather. The complete package now removes 410 launches per
decoded token.

## Performance

One B70, local SHA-verified GGUF, F16 KV, flash attention, target only.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7` | `113.744265`, `115.373665` | `116.710918`, `116.925465` | **+1.97%** |
| fresh 12-prompt server suite | `110.034817`, `111.257298` | `111.431476`, `112.333550` | **+1.12%** |

The serving result is the conventional median token rate for generated tokens
1-100 after TTFT. All four fresh processes used 12 unique prompts exactly once,
requested 512 tokens, reported `cached_tokens=0` on every row, and passed the
final measurement gate. Candidate mean serving rate is `111.882513 tok/s`.

## Correctness

- The same-binary forced 128-token greedy comparison was byte-identical. Both
  canonical transcripts hashed to
  `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
- The candidate fired 3,810 direct fusions; the parent concat/state counter was
  zero, confirming all 30 intended recurrent boundaries per evaluated token.
- After adding an explicit gather/concat non-overlap gate, the rebuilt binary
  still produced the same hash and 3,810 hits.
- The candidate passed 8x repeat stability, arithmetic, exact-copy, and JSON
  schema canaries.

Promote the new complete patch. Structured summary:
`../data/2026-08-22-ornith35b-concat-state-direct-summary.json`; raw mirrored
engine/server JSON and canaries are retained beside it.
