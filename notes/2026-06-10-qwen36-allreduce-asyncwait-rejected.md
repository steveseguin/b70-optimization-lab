# Qwen3.6 INT8 Async All-Reduce Wait Rejection

Date: 2026-06-10

## Context

I tested `VLLM_XPU_ALLREDUCE_ASYNC_WAIT=1` on the accepted Qwen3.6 INT8
no-prefix runtime.

The intent was to see whether routing XPU communicator all-reduce calls through
`dist.all_reduce(..., async_op=True)` followed by `work.wait()` would reduce
collective overhead without changing model math.

Everything else stayed unchanged:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | no-prefix baseline | async wait |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.0404` | `89.9928` |
| output tok/s end-to-end | `96.7747` | `88.9485` |
| total client tok/s | `194.6544` | `177.8970` |
| mean client TTFT | `77.74 ms` | `77.91 ms` |

Artifacts:

- baseline: `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-asyncwait-graph32k-single-20260610.json`

The candidate regresses corrected single-request decode by about `8.2%` while
TTFT stays essentially unchanged.

## Decision

Reject `VLLM_XPU_ALLREDUCE_ASYNC_WAIT=1` for this Qwen3.6 INT8 runtime.

The accepted no-prefix runtime keeps the default synchronous communicator path
with graph-captured clone-safe custom-op all-reduce enabled.
