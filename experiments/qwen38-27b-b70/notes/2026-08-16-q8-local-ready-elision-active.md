# Qwen3.8 27B Q8 TP2 local-ready event elision

Date: 2026-08-16

Status: closed as performance-neutral; do not repeat unchanged.

## Trace-driven hypothesis

A bounded accepted-stack `unitrace -d -s -v` diagnostic around
`llama-bench -p 0 -n 1` completed after the reboot. The profiler emitted one
`Unable to query event for timestamps` warning and slowed the token from about
27 ms to 44.578 ms, so its rates are not benchmark results. Its relative
kernel and submission census is still useful:

- fused reordered-Q8 pair: 256 calls, 46.924 ms summed device execution,
  2.944 ms submission interval;
- standalone reordered-Q8: 512 calls, 31.846 ms summed device execution,
  29.575 ms submission interval;
- fused recurrent quad: 192 calls, 19.456 ms summed device execution;
- fused attention triple: 64 calls, 5.564 ms summed device execution;
- collective kernels themselves were only a few milliseconds of summed
  device work.

The raw trace is
`/mnt/fast-ai/bench-results/qwen38-q8-unitrace-postreboot-20260816/unitrace-p0-n1.174122.txt`,
SHA-256 `24427b67f747fb4aa21da9df7c5c154941aa6d102c1bedeb269c2cd40e789f7e`.
It contains model-load traffic as well as decode and is diagnostic only.

At each of the 128 TP2 boundaries, the accepted collective submits signal
events to both queues (`ready0`, `ready1`), then submits the vec4 reduction to
queue 0 with both events as dependencies. The backend's default queues are
created with `sycl::property::queue::in_order`. Queue 0 therefore already
orders its reduction after its own projection. Its `ready0` event is a
redundant local dependency. Queue 1's `ready1` is the necessary cross-queue,
cross-device readiness edge.

## Contract

- same accepted Qwen3.8 Q8 source, model, TP2 selector/split, F16 KV, flash
  attention, batch 1024 / ubatch 256, and target-only operation;
- one default-off same-binary door;
- treatment removes only the queue-0 `ext_oneapi_submit_barrier()` and makes
  the reduction depend on queue 1's event;
- queue 1 event, peer memory ownership, vec4 FP32 expression/order, root
  reduction, residual, RMS, multiply, register-direct Q8 handoff, and all
  output stores remain unchanged;
- log liveness once and include a defensive runtime assertion that queue 0
  has the SYCL `in_order` property; fail closed to the accepted two-event path
  otherwise;
- normal fixed completion must be byte-exact; a treatment-scoped delay/poison
  reach control must prove the branch is live without being benchmarked;
- bounded same-binary position-balanced screen before any endpoint work;
- promote only after a repeatable gain plus two complete 12-prompt cache-zero
  suites, exact output hashes, semantic canaries, long-context needle, and
  healthy Xe audit.

Build no more than two jobs under the established 8 GiB host-memory cap. Stop
on any device-lost, reset, hang, timeout, or output mismatch.

## Implementation and liveness

The candidate added one default-off door,
`GGML_SYCL_COMM_ELIDE_LOCAL_READY=1`, and a treatment-only poison door. It
verified `q0` had `sycl::property::queue::in_order`, omitted only `ready0`,
and retained `ready1` as the reduction dependency. The live log was:

```text
SYCL lab door | collective local ready: requested=1 q0_in_order=1 active=1 poison=0
```

The normal fixed 128-token completion was byte-exact against control. Its
content SHA-256 was
`0344292357c81000d67624607cd4f156c503ce6383d12c5d1dfd134ea087bc57`.
The treatment-scoped poison changed the completion (content SHA-256
`2f3cb8f196d1ae6f24251981056959210d3cb881390369f254365cb243d448d3`),
proving the new branch was live. No SYCL verification mismatch was reported.

The fresh candidate build was kept under the 8 GiB host-memory cap and
advanced through 59 of 104 steps. To avoid needlessly recompiling identical
SYCL translation units on this 16 GiB host, unchanged objects were imported
from the accepted build and the candidate-generated final device link was run
under the same cap. This was only a local build acceleration; a reproduction
should apply the incremental patch and perform a clean bounded build.

## Position-balanced result

Same-binary fresh-process `llama-bench -p 64 -n 256 -r 3`, order A-B-B-A:

| Position | Arm | Decode tok/s |
| --- | --- | ---: |
| A1 | control | 36.780649 |
| B1 | treatment | 36.796113 |
| B2 | treatment | 36.797580 |
| A2 | control | 36.794881 |

- control mean: `36.787765 tok/s`;
- treatment mean: `36.7968465 tok/s`;
- relative delta: `+0.024686%`.

The A2 prompt-evaluation sample was a position outlier (`363.207 tok/s`
versus roughly `382 tok/s` elsewhere), but decode stayed in-family. Prompt
evaluation is not used to decide this decode-path experiment.

The decode delta is below resolution. The candidate is therefore closed as
performance-neutral, the 12-prompt gate was intentionally skipped, and the
accepted stack remains unchanged. The post-reboot health audit found both
B70s normal with no Xe compute fault, reset, or hang.

Artifacts:

- structured result:
  [`2026-08-16-q8-local-ready-elision-neutral.json`](../data/2026-08-16-q8-local-ready-elision-neutral.json);
- incremental patch:
  [`q8-local-ready-elision-neutral-20260816.diff`](../patches/q8-local-ready-elision-neutral-20260816.diff);
- incremental patch SHA-256:
  `8bb5ec9ee80f950f3d1ed72d2e1f41ae45e68419ec77cd9fa692e600865d1b3a`;
- candidate `libggml-sycl.so.0.19.0` SHA-256:
  `2a6b0f9da87d24fedc41f477c406552cec2c346861f7f4afd1c6b73256b42f1b`;
- candidate `llama-bench` SHA-256:
  `5ad7c26b123d41194a72f127052c50414a58a558a120548f17f11d54dba61abb`;
- candidate `llama-server` SHA-256:
  `71972859c1f8132efafa5fd722c0f66d7b23cfeb8f9a1c567578032006cd695e`.
