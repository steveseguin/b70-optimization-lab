# Qwen3.6 Safe In-Place All-Reduce Source Filters

Date: 2026-06-10

## Context

The earlier broad safe in-place all-reduce pass was quality-safe and improved
single-request p512/n512 speed, but it regressed c48 aggregate throughput. This
follow-up added an opt-in source filter to split the rewrite by producer type
without changing model weights, quantization, dtype, context length, or serving
API.

Patch artifact:

- `patches/vllm-xpu-safe-inplace-allreduce-20260610.patch`

New filter:

- `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=any`
- `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=not_embedding`
- `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=add`
- `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=gemm`

Accepted control for comparison:

- Restored accepted p512/n512:
  - corrected after-first output tok/s: `98.5468`
  - e2e output tok/s: `97.3130`
- Prior accepted c48 p512/n256:
  - wall output tok/s: `1700.89`
  - from-first-text output tok/s: `1727.50`

## Not-Embedding Filter

Runtime:

- Session: `qwen36-tp4-noprefix-safeinplace-notembedding-32k`
- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplace-notembedding-32k-noprefix`
- Env delta:
  - `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE=1`
  - `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=not_embedding`

Generated-cache inspection:

- `36` `all_reduce_inplace.default` occurrences across `20` files

This matched the broad candidate count, so the initial embedding-like
collective is no longer identifiable as `embedding` by the post-grad pass.

Single p512/n512:

| metric | value |
| --- | ---: |
| corrected after-first output tok/s | `99.0258` |
| e2e output tok/s | `97.7833` |
| mean client TTFT | `75.80 ms` |

Quality:

- First run had one repeat-stability outlier.
- Warm rerun passed exact checks, repeat stability, long-context recall, and
  baseline parity.

c48 p512/n256:

| metric | value |
| --- | ---: |
| wall output tok/s | `1500.90` |
| from-first-text output tok/s | `1515.69` |
| mean TTFT | `1.5925 s` |

Decision: reject for production. It improves single-request speed, but it
still carries the broad candidate's high-concurrency regression.

Artifacts:

- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-notembedding-single-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-notembedding-frontdoor-quality-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-notembedding-frontdoor-quality-rerun-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-notembedding-c48-20260610.json`

## Add-Only Filter

Runtime:

- Session: `qwen36-tp4-noprefix-safeinplace-add-32k`
- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplace-add-32k-noprefix`
- Env delta:
  - `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE=1`
  - `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=add`

Generated-cache inspection:

- `16` `all_reduce_inplace.default` occurrences across `16` files
- Pass logs showed:
  - `rewrote 0 ... skipped_filter=1` on single-collective partitions
  - `rewrote 1 ... skipped_filter=1` on two-collective partitions

Single p512/n512:

| metric | value |
| --- | ---: |
| corrected after-first output tok/s | `98.8500` |
| e2e output tok/s | `97.6140` |
| mean client TTFT | `75.69 ms` |

Quality:

- Failed exact arithmetic canary: returned `58`, expected `60`.
- Repeat stability passed.
- Long-context recall passed.
- Baseline parity failed on arithmetic normalized output and hash.

Decision: reject. The speed is useful, but the arithmetic canary failure is a
hard quality regression.

Artifacts:

- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-add-single-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-add-frontdoor-quality-20260610.json`

## GEMM-Only Filter

Runtime:

- Session: `qwen36-tp4-noprefix-safeinplace-gemm-32k`
- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplace-gemm-32k-noprefix`
- Env delta:
  - `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE=1`
  - `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=gemm`

Generated-cache inspection:

- `16` `all_reduce_inplace.default` occurrences across `16` files
- Pass logs showed the same narrow rewrite count as add-only, but on GEMM
  sources instead of add sources.

Single p512/n512:

| metric | value |
| --- | ---: |
| corrected after-first output tok/s | `97.6825` |
| e2e output tok/s | `96.4864` |
| mean client TTFT | `75.17 ms` |

Decision: reject at the speed gate. It is slower than the restored accepted
control, so I did not run the full quality suite or c48.

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-gemm-single-20260610.json`

## Decision

Do not promote any source-filtered safe in-place all-reduce variant.

Current standing:

- `any` / broad: quality-safe, single-request win, c48 regression.
- `not_embedding`: effectively broad, quality pass on warm rerun, c48
  regression.
- `add`: single-request win, quality regression.
- `gemm`: quality untested, speed regression.

The accepted runtime remains the no-prefix TP4 32K profile without
`VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE`.

## Next Leads

The useful lesson is that the collective boundary matters, but the safe
in-place rewrite is not the right production path as implemented. Better next
directions:

- inspect why the add-only rewrite changes the arithmetic canary while the
  broad rewrite does not;
- look for a non-mutating way to reduce allocation/copy overhead around the
  add-output collective;
- focus on scheduling, graph-boundary, or kernel-level changes that preserve
  out-of-place semantics.
