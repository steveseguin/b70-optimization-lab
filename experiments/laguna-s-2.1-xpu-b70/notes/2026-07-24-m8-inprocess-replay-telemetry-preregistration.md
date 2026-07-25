# Laguna M8 in-process replay telemetry preregistration

Date: 2026-07-24 America/Toronto

Status: **preregistered; not yet run**.

This diagnostic replaces the terminally invasive full PTI trace. It is not
benchmark, endpoint, or LocalMaxxing evidence.

## Frozen identity and protocol

- vLLM: `8cf58ed0f3679245053b6f298b4bf1ccd13906ed`;
- kernels: `4772f727590c51b72add79350b913d098cf67872`;
- models and all artifacts remain below `/mnt/fast-ai`;
- exact production selector stack is unchanged;
- three fresh processes run sequentially: canonical q1 target eager without
  speculation and with its original async scheduler plus experimental M8
  selectors disabled; synchronous optimized DFlash eager; then synchronous
  optimized DFlash audited Breakable graph;
- each process performs exactly one uncached greedy 128-token generation;
- the shared prompt is used only for bitwise cross-arm verification;
- q1, eager, and graph token IDs, text hash, and finish reason must all match.

Only the graph arm enables telemetry. Lazy capture/materialization is excluded;
the first 31 actual replays are sampled. Each rank must emit one owner-private
record with identical descriptor and segment-order digests, exactly 146 graph
segments, 97 collective boundaries, 48 attention boundaries, zero other
boundaries, and 31 complete rows.

Each row records:

- static-signature collection and comparison;
- debug-address guard if active;
- offloader dependency wait;
- host-call spans for every existing graph/collective/attention callable;
- total host time through the final replay submission;
- one post-replay device synchronize;
- whole replay completion time.

The only queue perturbation is the single synchronize after the complete
replay. It is diagnostic and cannot be compared to the 92.164 tok/s record.
There is no per-boundary synchronization, PTI, tensor copy/hash, compiler,
arithmetic change, cache reuse, warmup request, or retry within an arm.
After the 31st sampled replay is sealed, any remaining replay in the same
generation returns to the normal uninstrumented path: it performs no boundary
timing and no diagnostic device synchronize.

The lane fails closed on insufficient samples, topology/order drift, any
output mismatch, extra generation, cache use, worker survival, device-idle
failure, USB path, identity drift, or missing rank file.
