# Laguna M8 replay trace retry: terminal PTI failure

Date: 2026-07-24 America/Toronto

Status: **terminal negative for full-model PTI kernel-submission tracing**.

## Sealed roots

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-replay-trace-retry-2ba49c7d9-7118fa20d-20260724T231905Z
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-replay-trace-retry-2ba49c7d9-7118fa20d-20260724T231905Z-supplemental
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-post-pti-failure-idle-20260724T233700Z
```

Supplemental parent PTI file:

```text
unitrace.483846
SHA256 b8262f4aefb30a400af9038d10f0264fced6dd15be0e5b9a85ede024c8992f2d
```

## Result

The repaired temporal-control acknowledgement passed and eager model
initialization completed. When the single generation began, the combined
unitrace `--host-timing --device-timing --kernel-submission` instrumentation
made the first sampling RPC exceed vLLM's five-minute worker timeout. PTI
repeatedly reported:

```text
[ERROR] Unable to query event for timestamps
```

The EngineCore then failed with:

```text
TimeoutError: RPC call to sample_tokens timed out.
```

No `driver.json` was produced, no 128-token output completed, the graph arm
never ran, and no performance or correctness claim is allowed. PTI remained
wedged while finalizing orphaned worker event state after the engine had
already died. The exact failed process group was terminated, the runner exited
status 143, and a fresh post-failure idle snapshot passed on all devices.

## Disposition

Do not retry the unchanged full-model combination of host timing, device
timing, and kernel-submission tracing. It is too invasive for one Laguna M8
forward under the production multiprocess RPC timeout.

The authorized replacement is default-off in-process telemetry around the
already existing Breakable replay loop:

- `perf_counter_ns` around the static guard, offloader sync, 146 graph replay
  calls, 97 collective eager calls, and 48 attention eager calls;
- one device synchronize only after the complete replay;
- no per-boundary synchronize, device copy, tensor hash, profiler, subprocess,
  or distributed control;
- 31 consecutive steady replays retained in memory per rank and written once
  after the sample window;
- fresh q1, DFlash eager, and DFlash graph processes whose greedy token IDs
  must all match exactly.
