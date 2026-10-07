# Sampler after 105: measure device work before changing placement

The next useful probe is bounded per-device driver accounting alongside the
existing exact-output workload, followed only if needed by sparse, attributed
sampler transfer/replay timing. Do not simply enable `route_busy_ms` and label its
windows total GPU utilization. Do not choose W3 or a new block split from the
stage-A/stage-B elapsed times: both denoising stages use both sampler cards.

This is an offline source audit and probe proposal. No instrumentation was
enabled, no endpoint or GPU was accessed, and no runtime code changed. The
consumed 104 plan and preparing 105 comparison remain sealed. A later diagnostic
needs its own reviewed, finite admission; this note does not authorize extra
requests against either plan or a reload chain.

## What the existing instrumentation actually measures

In sealed 104 `ltx_graph_capture.py:1251`, the replay path takes a shared capture
lock, obtains its static slot, calls `group.fill`, and then brackets only
`entry.graph.replay()` with `busy_begin`/`busy_end`. Captures are frozen during
scored work. Each sampler thread has its own graph entries and device streams;
the shared replay lock does not intentionally serialize workers against each
other. The unfrozen capture path is exclusive and is not a performance lever.

`staged_move` at line 824 copies a tensor to pinned host memory on its source
stream, records an event, waits for that event on the host, then enqueues a copy
into a newly allocated destination tensor on the destination stream. The other
worker can run during this wait. This path handles activations and the final
return to the primary device. `_staged_cached` also moves per-forward arguments;
some non-tensor objects fall back to the shard mover. The replay windows exclude
these transfers, the existing host wait, allocations, static-buffer fills,
sentries, upsampling and other work outside the graph.

`busy_window_report` queries completion before reading event times, carries
unfinished windows, and merges intervals on each card's own anchor clock. It
does not synchronize a device. But its global queues span both sampler workers
and multiple clips; the drain occurs in the collecting prompt's receipt, not at
a clip boundary. Entries identify device and route, not clip, worker or A/B
stage. Summed windows double-count overlap; union intervals must be merged
across drains. There are 8,192-window and 2,048-segment caps, dropped/error/unplaced
metadata, and gap coalescing that can inflate covered time. Instrumentation can
disable itself without failing inference, so missing timing is not zero work.
Replay intervals can also include contention; they are not isolated kernel cost.

`pipeline_sampler_node.py:566` already drains that clip's streams at worker
completion. Its phase events at line 609 span everything between phase marks,
including waits. `ltx_pipeline.py:220` starts worker service timing when a queued
job is selected; `collect` waits for completion and reports service duration,
not queue residence or an attributed device timeline. After capture freeze,
sampler dispatch clears explicit worker pinning and allows either worker to
pick eligible jobs. A proposed probe must record actual worker identity, not
assume parity assigns a sampler worker.

## Avoid repeating the old occupancy mistake

The [90c result](2026-10-03-packet-90c-results.md) observed roughly 0.2 seconds per
clip / 12% difference with replay timers enabled versus its separate control.
That historical workload and separate processes are not a precise overhead
forecast for today's chained graphs, but they rule out assuming timers are free.
Its 41–45% replay-window coverage was initially called card utilization.
The later [91c driver-counter note](2026-10-04-gpu-budget-from-driver-counters.md)
explicitly retired that interpretation: replay windows missed other work on each
card. Neither historical percentage establishes today's 640×384 W2 utilization.

104 source receipts report timers disabled. The current runtime packet contract
requires `LTX_BUSY_WINDOWS=0`. Turning them on is a reviewed source/contract
successor, not a harmless environment toggle on a live comparison.

## Smallest concrete next probe

1. **Passive accounting first.** For one newly admitted ten-fixture block plus
   its four fills, sample only `/proc/<pid>/fdinfo` at a fixed two-second cadence,
   with a hard 120-second / 64-sample / 128-KiB output budget. Bind PID, start
   ticks, boot ID, source/plan and PCI-to-XPU mapping before collecting. Stop on
   identity change, missing required counters or the campaign fault marker; do
   not touch the device or submit work. Capture raw per-client/per-engine
   counters and sample monotonic times. Analyze only complete intervals inside
   the declared block, excluding fill and verification boundaries. Keep all
   numerical settings, exact four-tensor gates and client durability unchanged.
2. **Review the existing helper before reuse.**
   `scripts/sample-gpu-engine-busy.py` already reads fdinfo and deduplicates
   `(drm-pdev, drm-client-id)`. It is not ready as a bounded probe: it lacks a
   fixed duration, PID-start identity, exclusive output and missing/reset-counter
   validation. It currently uses the compute engine's total-cycle denominator
   for both compute and copy, sums client busy counts against one maximum total,
   and derives seconds from that ratio. Preserve raw counters and validate each
   engine's exposed denominator/capacity semantics before reporting utilization;
   do not turn absent fields into zero. Check child processes and duplicate DRM
   clients explicitly, and report coverage instead of assuming all work belongs
   to one PID. PCI order alone is not an XPU identity proof. None of these fixes
   requires changing model execution.
3. **If accounting still cannot locate the delay, use one sparse source-bound
   sampler trace.** Select at most one observed job from each of the two actual
   sampler workers, with explicit clip ID, worker/thread, route, device, A/B
   stage, operation and byte-count labels. Around `staged_move`, separately
   record CPU enqueue/host-wait durations and same-device event pairs around the
   D2H/H2D copies. Around `group.fill` and graph replay, distinguish static-input
   copy from replay windows. Record only existing transfer/replay calls; never
   add, skip, reorder or repeat an operation. Read event durations after the
   existing per-clip stream drain; add no new synchronization. Never subtract
   timestamps from different device clocks. A host wait includes preceding
   queued source work, not just D2H copy time. The fallback mover and other GPU
   work remain explicitly outside this sparse trace unless separately covered.

For the sparse trace, preallocate bounded host bookkeeping, cap records/events
and declare truncation/errors in the diagnostic receipt. No tensor copies for
profiling, per-event file writes, profiler stacks or global locks in the replay
path. Preserve the existing sentries and all source/fault/durability checks.
Instrumentation failures should invalidate attribution without retrying or
changing arithmetic. Require exact outputs on the instrumented clips. Keep
instrumented throughput separate from speed results and compare a matched
uninstrumented block to expose perturbation; if service/interval distributions
shift materially, use the trace only to locate categories, not to estimate a
production speed ceiling. A two-second passive sample is likewise not a
zero-overhead assumption or fine-grained transfer timeline.

The result should choose one next change: investigate transfer/static-copy
traffic if that dominates, host submission gaps if device accounting leaves
large unexplained intervals, or a specific sampler kernel/route if device work
dominates. Compute and copy engines overlap, so their times cannot be added into
a critical path. No decoder-graph lane, worker-count sweep or blind placement
sweep is needed to obtain this evidence.

## Authorized idle-process counter availability snapshot

At 2026-10-07 19:13:57.769705 UTC, one read-only snapshot inspected only fdinfo
for descriptors whose symlink target was an actual `/dev/dri/renderD*` node.
PID 3311653, start ticks 27195355 and boot
`10192010-9700-4915-ac6c-980d6b74afa0` matched before and after the scan. No second
snapshot or utilization measurement was needed. No observer was added to 105.

| FD | Render node | PCI device, also verified through sysfs | DRM client | CCS busy cycles | BCS busy cycles | Both engine total cycles |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 10 | renderD131 | 0000:27:00.0 | 15375 | 2159191404 | 1283432906 | 5267216439224 |
| 11 | renderD130 | 0000:23:00.0 | 15376 | 2637600720 | 2210964378 | 5267185031952 |
| 12 | renderD129 | 0000:47:00.0 | 15377 | 4751816422 | 2514495980 | 5267194156650 |
| 13 | renderD128 | 0000:43:00.0 | 15378 | 5417612106 | 3635378771 | 5267195552609 |
| 19 | renderD131 | 0000:27:00.0 | 15379 | 0 | 0 | 5267216586406 |
| 20 | renderD130 | 0000:23:00.0 | 15380 | 0 | 0 | 5267185141447 |
| 21 | renderD129 | 0000:47:00.0 | 15381 | 0 | 0 | 5267194227771 |
| 22 | renderD128 | 0000:43:00.0 | 15382 | 0 | 0 | 5267195586778 |

All eight report driver `xe` and distinct DRM client IDs. `drm-cycles-ccs`,
`drm-cycles-bcs` and their respective `drm-total-cycles-*` fields are present;
the two engine totals happen to match within each individual snapshot.
`drm-engine-capacity-vcs` and `vecs` are 2; no explicit CCS/BCS capacity field
appeared. Availability is established, but counter semantics, deltas and stable
XPU-index mapping still require the planned admission checks. These cumulative
numbers are not idle-period utilization, and node-number order is plainly not
PCI order. Four zero-busy secondary clients must remain distinct from duplicate
file descriptors referencing the same DRM client.

## Source pins

Sealed packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-client-compare-104`,
manifest `49892a00ece1cf4a7d84ce5d03e6a9c2290ffc3af9b2822ba4866e72cfa2e93a`.
Actual source SHA-256 values matched that manifest:

| File beneath packet | SHA-256 |
| --- | --- |
| `source/scripts/ltx_graph_capture.py` | `3a9a99954cb4877829c4407eb74306f6b409864002dfcccf3562fd0c98380400` |
| `source/scripts/pipeline_sampler_node.py` | `ae4af44f9315b01a2b8d684a046d6fda741cea4d35f52a2b72ea04f268adb0a3` |
| `source/scripts/ltx_pipeline.py` | `5c2b36efa1ef3fcc9f865e841063ac15da9a1db765fc9d8e2d608fd1a622db58` |
| `source/scripts/ltx_layer_shard.py` | `9caaec0aeb68e9f391fab5ae9b6a63e464aa62a99e1ffc449775b3687d2149b2` |

Historical note `2026-10-03-packet-90c-results.md`:
`fed9df3a3f435f4083a551ebd5f39a447eb4fabe8d30108bd4c57db8eda82d2b`.
Later driver-counter note `2026-10-04-gpu-budget-from-driver-counters.md`:
`fe7103f9bcff1675cc6f40ee2d9e9172b2d12d412e5d7bc910e683b026cbbfba`.
Author `recovery/20261007-resolution-runtime/runtime_packet.py` at audit time:
`5c0d693f898eb5a233734abe56c9ae3be133fd8fb1884a83dba3c01b6ff5a39a`.
Existing fdinfo helper:
`3a1f1d450f35e1d2d536f012b95fe77da7f3c4bad398f4f1453fe1055ee68d2d`.
The helper is a research starting point, not an endorsed runnable measurement
recipe until its bounded identity and counter-accounting requirements are met.
