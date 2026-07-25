# Laguna M8 in-process replay: 272-token protocol preregistration

Date: 2026-07-25 America/Toronto

Status: **preregistered; not yet run**.

This revision changes only the diagnostic generation length and arm-record
schema after the 128-token campaign failed closed with insufficient replay
samples. It is not benchmark, endpoint, or LocalMaxxing evidence.

## Frozen identity and protocol

- vLLM: `8cf58ed0f3679245053b6f298b4bf1ccd13906ed`;
- kernels: `4772f727590c51b72add79350b913d098cf67872`;
- models, caches, temporary files, logs, and artifacts remain on internal
  NVMe/ext4 below `/mnt/fast-ai`;
- three fresh processes run sequentially: canonical q1 target eager with its
  original async scheduler and experimental M8 selectors disabled;
  synchronous optimized DFlash eager; then synchronous optimized DFlash
  audited Breakable graph;
- each process performs exactly one uncached greedy 272-token generation from
  the same prompt, with `ignore_eos=True`; there is no warmup request, retry,
  cache/history reuse, or second generation;
- q1, eager, and graph token IDs, text hash, and finish reason must all match
  bitwise;
- only the graph arm enables the existing 31-replay telemetry.

DFlash depth 7 can emit at most eight target-verified output tokens per target
transaction. Producing 272 tokens therefore requires at least
`ceil(272 / 8) = 34` target transactions. One transaction may lazily capture
the M8 graph. Conservatively allowing an initial M1 transaction and a final
partial transaction still leaves at least 32 eligible full-M8 replay
transactions after capture. This exceeds the fixed 31-sample requirement
without adding a request or retry.

The telemetry fields, 146-graph/145-boundary topology contract, four-rank
closure, maximum-rank reduction, output checks, source/model/binary identity,
strict idle and worker gates, and fail-closed behavior remain exactly as
preregistered in
`2026-07-24-m8-inprocess-replay-telemetry-preregistration.md`. After the 31st
sample, remaining transactions use the uninstrumented replay path.

The lane fails closed on insufficient samples, topology/order drift, any output
mismatch, extra generation, cache use, worker survival, device-idle failure,
USB path, identity drift, or missing rank file. Diagnostic wall time and
instrumented replay timing cannot be compared with the 92.164 tok/s record.
