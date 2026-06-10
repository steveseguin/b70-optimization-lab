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
- `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=source_name:<needle>`
- `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=input_name:<needle>`

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

## Rewrite Diagnostics

I extended the opt-in pass with decision logging:

- Env: `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_LOG_REWRITES=1`
- Patch artifact:
  `patches/vllm-xpu-safe-inplace-allreduce-20260610.patch`
- Diagnostic runtime:
  `qwen36-tp4-safeinplace-diag-32k`
- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplace-diag-32k-noprefix-20260610`
- Log:
  `/tmp/qwen36-quark-int8-tp4-safeinplace-diag-32k-noprefix-20260610.log`

The broad diagnostic compile rewrote these producer families:

| source | rewrite log count |
| --- | ---: |
| `where.self` | `4` |
| `int8_gemm_w8a8.default` | `16` |
| `add.Tensor` (`add_92`) | `8` |
| `add.Tensor` (`add_53`) | `8` |

The diagnostic single p512/n512 sample stayed in the same tier as the prior
broad safe-inplace result:

| metric | value |
| --- | ---: |
| corrected after-first output tok/s | `98.9875` |
| e2e output tok/s | `97.7466` |
| mean client TTFT | `75.79 ms` |

Artifact:

- `data/qwen36-quark-int8-tp4-safeinplace-diag-single-20260610.json`

## Where-Only Exact Filter

The diagnostic census showed the initial post-embedding-like producer is
`where.self`, not `embedding`, so I screened an exact source-name filter:

- Session: `qwen36-tp4-safeinplace-where-32k`
- Env delta:
  - `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE=1`
  - `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=source_name:where`
  - `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_LOG_REWRITES=1`
- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplace-where-32k-noprefix-20260610`
- Log:
  `/tmp/qwen36-quark-int8-tp4-safeinplace-where-32k-noprefix-20260610.log`

Rewrite census:

| decision | source | count |
| --- | --- | ---: |
| rewrite | `where.self` | `4` |
| skip | `int8_gemm_w8a8.default` | `12` |
| skip | `add.Tensor` (`add_92`) | `8` |
| skip | `add.Tensor` (`add_53`) | `4` |

Single p512/n512:

| metric | value |
| --- | ---: |
| corrected after-first output tok/s | `98.0598` |
| e2e output tok/s | `96.8293` |
| mean client TTFT | `76.55 ms` |

Decision: reject at the speed gate. This exact filter removes the aggregate
risk from GEMM/add mutations, but it also removes the single-request gain.

Artifact:

- `data/qwen36-quark-int8-tp4-safeinplace-where-single-20260610.json`

## Scheduler Full-ISL Reservation Screen

I also screened a non-math scheduler flag after the collective branch:

- Session: `qwen36-tp4-noprefix-noreservefullisl-32k`
- Env: accepted no-prefix runtime
- CLI delta: `--no-scheduler-reserve-full-isl`
- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix`
- Log:
  `/tmp/qwen36-quark-int8-tp4-noreservefullisl-32k-noprefix-20260610.log`

The server loaded the accepted AOT graph cache directly, so this isolated the
scheduler behavior from graph/codegen changes.

Single p512/n512:

| metric | value |
| --- | ---: |
| corrected after-first output tok/s | `98.7119` |
| e2e output tok/s | `97.4206` |
| mean client TTFT | `78.89 ms` |

Decision: reject. The flag is quality-neutral by construction but did not
improve single-request speed and worsened TTFT in this sample.

Artifact:

- `data/qwen36-quark-int8-tp4-noreservefullisl-single-20260610.json`

## Decision

Do not promote any source-filtered safe in-place all-reduce variant.

Current standing:

- `any` / broad: quality-safe, single-request win, c48 regression.
- `not_embedding`: effectively broad, quality pass on warm rerun, c48
  regression.
- `add`: single-request win, quality regression.
- `gemm`: quality untested, speed regression.
- `source_name:where`: speed regression.
- `--no-scheduler-reserve-full-isl`: quality-neutral but no speed win.

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
- focus on graph-boundary or kernel-level changes that preserve out-of-place
  semantics. The simple full-ISL scheduler flag is not a single-request win.
