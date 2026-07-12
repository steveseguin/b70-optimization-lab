# 2026-07-12 Cycle Timeline Tooling

The reusable cycle-timeline tooling is:

- `scripts/profile-qwen27-cycle-timeline.sh`: guarded normal-run entry point;
- `scripts/summarize-qwen27-cycle-timeline.py`: result, server-log, graph, and
  optional `sycl-trace` parser.

The runner refuses to touch a GPU unless `CONFIRM_GPU_USE=1` is set. Normal
mode runs one strict no-spec or MTP3 profile through the existing identity and
cold-suite harness. Trace mode is deliberately not automated as a throughput
run: tracing perturbs execution and must be limited to one short diagnostic
request.

## Existing MTP3 Evidence

The parser was validated without GPU use against the Phase 0 strict MTP3 row.
It reconciles 12 request streams with 12 server decode records and reports:

- median request wall time: about `3947.32 ms`;
- median TTFT: about `1179.02 ms`;
- median server prompt time: about `1163.86 ms`;
- median server decode time: about `2768.98 ms`;
- median streamed inter-cycle gap: about `59.63 ms`;
- median streamed burst: `3` emitted tokens;
- aggregate draft acceptance: `964 / 1649 = 58.46%`;
- median reported accepted length: `2.73`.

The request clock is therefore internally consistent with prompt plus decode
time. The stream evidence also makes the immediate bottleneck concrete: an
MTP verification/draft cycle is roughly `60 ms`, producing a median of three
tokens. To reach `100 tok/s` with the same burst size, that cycle must approach
`30 ms`; merely reducing HTTP emission gaps within a burst cannot do it.

## Available Tracing

Installed:

- `/opt/intel/oneapi/compiler/2026.0/bin/sycl-trace`;
- Unified Runtime call tracing via `--ur.call`;
- Level Zero call tracing via `--level_zero`.

Not found in the current environment: `unitrace`, `onetrace`, or `ze_tracer`.
`xpu-smi` and `intel_gpu_top` are present, but neither provides the
per-kernel occupancy/bandwidth timeline needed for exact attribution.

The optional trace parser counts UR/Level Zero API calls and consumes duration
fields when the selected trace format emits them. Call traces can identify
submission, synchronization, allocation, and copy-call density. They cannot,
by themselves, establish kernel bandwidth, occupancy, or memory-stall causes.

## Interpretation Limits

- The 1 ms stream-burst boundary is a documented heuristic, not a device
  timestamp.
- llama.cpp `eval time` includes target work, draft work, target verification,
  state management, sampling, synchronization, and host coordination.
- `sycl-trace` measurements are diagnostics and may not be compared directly
  to the strict headline throughput.
- Exact kernel attribution still requires either native event profiling added
  around selected queues or a Level Zero hardware-counter profiler.

## Graph-Off Measurements On GPU 0

The current AOT binaries were measured again with both SYCL graph replay and
the executable-graph cache disabled. These are normal, untraced strict-suite
runs and may be used as throughput controls:

| profile | median tok/s, tokens 1-100 after TTFT | p10 | median TTFT | strict gate |
| --- | ---: | ---: | ---: | --- |
| no-spec | `25.9370` | `25.7327` | `1146.50 ms` | pass, all 12 requests `cached_tokens=0` |
| MTP3 | `48.9233` | `42.2890` | `1178.54 ms` | pass, all 12 requests `cached_tokens=0` |

Normal-run artifacts:

- `data/qwen27-cycle-timeline/no-spec-normal-20260712T160033Z/`;
- `data/qwen27-cycle-timeline/mtp3-normal-20260712T160205Z/`;
- raw server/run evidence under
  `/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/cycle-timeline/` with the
  matching directory names.

The no-spec timeline measured a `38.88 ms` median stream gap, always one token
per burst. MTP3 measured a `59.21 ms` median inter-cycle gap and a median burst
of three tokens. MTP3 accepted `966 / 1647 = 58.65%` of draft candidates with
a median reported accepted length of `2.76`. Median request time minus the
server's prompt-plus-decode clocks was `18.98 ms` for no-spec and `13.93 ms`
for MTP3. These are aggregate clock-reconciliation residuals, not a newly
identified host-overhead bucket.

## UR And Level Zero Call-Trace Diagnostic

Two matched diagnostic requests used prompt `x`, 16 generated tokens,
`cache_prompt=false`, Q8 KV, graph off, and cache size zero. The trace window
starts at llama-server's `processing task` marker and ends at its final
`eval time` marker, so it contains the one-token prompt and 16-token decode.
Tracing perturbs execution and its timing is not headline performance.

| request-window UR call | no-spec | MTP3 |
| --- | ---: | ---: |
| `urEnqueueKernelLaunchWithArgsExp` | 38,831 | 19,522 |
| `urQueueFinish` | 591 | 993 |
| `urEventWait` | 146 | 232 |
| `urEnqueueUSMMemcpy` | 928 | 638 |
| `urUSMGetMemAllocInfo` | 12,800 | 5,600 |
| `urEventRelease` | 39,761 | 20,162 |
| all parsed UR calls | 98,240 | 49,572 |

The diagnostic no-spec request reported `582.68 ms / 16` decode tokens; MTP3
reported `367.73 ms / 16`, accepted `9 / 17` candidates, and reported mean
accepted length `2.50`. The useful attribution is call density: MTP3 roughly
halves kernel launches for this accepted-token sequence, but performs
substantially more explicit queue finishes and event waits. This supports
prioritizing complete speculative-cycle replay and synchronization removal,
not only projection bandwidth.

Trace artifacts:

- no-spec:
  `/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/cycle-timeline/no-spec-sycl-trace-short-gpu0-20260712T160515Z/`;
- MTP3:
  `/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/cycle-timeline/mtp3-sycl-trace-gpu0-20260712T160436Z/`;
- each directory contains `trace.log`, the exact request and response,
  `timeline-summary.json`, and `request-window-counts.json`.

The installed `sycl-trace` accepted `--ur.call --level_zero`, but emitted no
Level Zero API records and no call-duration fields. An explicit smoke with
`ZE_ENABLE_TRACING_LAYER=1` and `SYCL_TRACE_ZE_ENABLE=1` also emitted zero
Level Zero records. A separate `--print-format=verbose` smoke on the small DUP
backend test emitted thread IDs and call arguments but still no timestamps or
durations. Consequently, the trace proves UR launch/synchronization counts but
cannot time those calls or split queue gaps into kernel, memory, barrier, and
host components. Exact millisecond attribution remains blocked on native event
instrumentation or a working Level Zero timestamp/hardware-counter collector;
it must not be inferred from the call counts above.

## Guarded Native Event Timing

The working llama.cpp tree now has opt-in native timing under
`GGML_SYCL_CYCLE_TIMING=1`. The environment variable is read while the DPCT
queues are created, adding `enable_profiling` only to diagnostic-process
queues. With the variable unset, queue construction and graph execution retain
their original properties and no marker events, waits, or timing logs are
created.

For each `graph_compute` invocation the diagnostic submits an in-order marker
before the work and another after it, waits for the ending marker, and emits one
`[SYCL-CYCLE]` row. Fields distinguish:

- `host_work_submit_us`: host time through normal kernel or graph submission;
- `host_marker_submit_us`: cost of submitting the ending timing marker;
- `host_sync_us`: the diagnostic wait for the ending marker;
- `host_total_us`: the complete instrumented host interval;
- `device_queue_us`: device-clock interval from the end of the starting marker
  to the start of the ending marker, including kernels, copies, barriers, and
  queue gaps inside that graph invocation;
- `graph_queue_us` and `graph_exec_us`: command-graph event submit-to-start and
  start-to-end intervals when the path submits an executable graph.

The row also identifies `ordinary`, graph creation/update/recreation, direct
cached replay, cache-full fallback, and unsupported-graph paths. The timeline
summarizer parses these rows and reports distributions by field and path.

This mode deliberately forces a synchronization at every `graph_compute` and
therefore must only be used for short attribution diagnostics. Its throughput
is not a headline or regression measurement. `device_queue_us` is an exact
queue interval, but it is not a sum of kernel busy time; per-kernel events or a
hardware-counter collector are still required to split compute from memory
stalls within that interval.

### First native measurements

For steady no-spec M=1 decode (`3846` nodes), eight-token diagnostics measured
approximately 12.2-12.5 ms of host work submission and a 37.0-37.1 ms device
marker interval. The roughly 24.5-24.9 ms after host submission is queued
execution and synchronization; it is not another unexplained framework-only
bucket.

For deterministic MTP3 after warmup, the repeating cycle was visible directly:

- one `4278`-node target verifier graph took about 42.5-45.8 ms, including
  roughly 14-15 ms of host submission;
- four `55`-node draft/state graphs normally comprised one short ~0.7 ms graph
  plus three ~3.0 ms graphs, about 9.7 ms total;
- the combined measured device cycle was roughly 52-56 ms, consistent with the
  uninstrumented ~59.2 ms stream-cycle median after server/host coordination.

The target verifier is therefore the largest MTP3 cost, followed by repeated
draft/state passes. Large fusion and a materially stronger multi-token verifier
remain necessary; generic command-graph replay did not shorten these intervals.
