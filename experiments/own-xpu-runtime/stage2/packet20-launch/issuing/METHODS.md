# Launch microbenchmark implementation

Compilation is CPU-only. Nothing in this packet has been executed on a device.
The native executable is deliberately not used even for `--help` or a mock.

The nine issuing arms are `explicit_in_order`, `explicit_out_of_order`,
`explicit_wait_each`, `implicit_in_order`, `discard_in_order`, `graph`,
`raw_regular`, `raw_immediate`, and `fusion8`. Each has two surrogate workloads,
N=100/1000/4000, five repeats: 270 timing rows. The explicit arms retain an
owner-style event map and explicit preceding-event dependency. The implicit
arms rely on an in-order queue and retain no per-kernel event. `discard_events`
compiles but IntelLLVM 2026.0 marks it deprecated. Fusion8 issues ceil(N/8)
kernels, with four operations in the last kernel when N=100. BF16 conversion
occurs after **every** operation, including within fusion8.

The elementwise workload uses 17 USM pointers and 2,560 BF16 elements; the
GEMV-like workload uses 32 independent scalar products per element. Neither is
a model kernel or quality oracle. A persistent device state block selects
positive/negative increments, and arg0 is reset before each repeat. H2D state
and reset copies occur outside recording and timing. All 2,560 outputs are
copied back outside timing and compared with the CPU BF16 recurrence before
`output_verified=true` is emitted. Alternating sign makes inert graph replay
observable. These device checks are prepared, not yet passed.

`wall_ns` starts after a global-timestamp query and ends immediately after the
completion poll. `profiled_span_ns` is first-kernel-start to last-kernel-end for
explicit SYCL and raw Level Zero, and the executable graph event interval for
graph. It is null for implicit/discard arms, which do not retain events.
`device_envelope_ns` uses Level Zero global timestamps surrounding issuance
and completion, including host issue gaps and the timestamp calls. This is
explicitly a device-clock **envelope**, not summed device kernel execution.
`setup_ms` separately records graph recording/finalization or raw module/list
construction. One raw closed list is replayed five times, never concurrently.
Dynamic-parameter binding/update compiles and links in `dynamic_probe.cpp`,
but is not a timed arm: one device-state upload avoids N graph-node updates.

The regular raw list uses `ZE_COMMAND_LIST_FLAG_IN_ORDER`; immediate uses
`ZE_COMMAND_QUEUE_FLAG_IN_ORDER`. Flags and timestamp queries compile. Driver
support is untested; no silent unordered fallback is allowed. No-graph-aspect
is emitted as unavailable before recording; other runtime API rejection holds
the process conservatively for the supervisor rather than retrying a launch.

## Ownership and failure handling

The benchmark extends the Stage1 `Backend` interface locally. Stage1 Device
and Arena remain the owners; no raw context/device handle is exposed to
callers. The benchmark backend owns its SYCL context and primary queue. Native
context/device handles are borrowed with `get_native`, never destroyed as
native handles. Its private raw lists/queue/module/kernel/events are created
in that same context. No `get_native(queue)` variant is assumed to be a raw
regular queue. Raw completion event **and** raw list/queue synchronization are
polled before reset/replay, before SYCL readback, and before destruction.

SYCL case queues and executable graphs use explicit destruction on success.
On an error they remain allocated while `hold_for_supervisor` retains the
backend, Arena, persistent H2D sources and process. Raw handles likewise are
not RAII-destroyed during error unwinding. A completed raw case destroys list,
events, event pool, kernel, module and regular queue before returning its final
Stage1 event. Graphs are destroyed before the case returns. Then ordinary
Stage1 shutdown drains, releases Arena allocations, completes its idle marker,
releases events, queue and context. The async error slot is mutex protected.

Explicit USM allocation is 17 * 5,120 = **87,040 device bytes**. Driver/runtime
command buffers, JIT storage and graph pools are opaque and are not covered by
that number. This packet cannot certify their aggregate is below 64 MB before
a device measurement. One graph exists at a time; it is destroyed before the
next chain is recorded. Runtime/JIT calls themselves cannot be forcibly
time-bounded safely. Admission stops at 50 seconds; completion polling has a
900 ms bound and failures retain the process. Expected normal runtime is
20–50 seconds; a hard <60-second guarantee would require unsafe termination
and is not asserted. No device result or speed decision is available yet.
