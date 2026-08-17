# Qwen3.8 27B Q8 TP2 local-ready event elision

Date: 2026-08-16

Status: active on the two-ASRock-B70 reference host; do not duplicate
unchanged.

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
