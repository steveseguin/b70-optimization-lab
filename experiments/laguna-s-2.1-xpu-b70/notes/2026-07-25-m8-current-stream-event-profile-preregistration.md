# Laguna M8 current-stream event-profile preregistration

Date: 2026-07-25 America/Toronto

Status: **host-only design frozen; no XPU or model execution authorized yet**.

## Purpose

The current approved record is the exact persistent-attention-metadata graph
stack at `94.92003934159611 tok/s`, LocalMaxxing
`cmrzrd4tf001ipa013xpx4kid`.

Existing in-process telemetry attributes median replay-host submission time to
146 graph calls, 97 collective boundaries, and 48 eager attention boundaries.
The metadata candidate removed about `4.000 ms` of attention-host work but
improved whole replay by only `0.406 ms`; the later persistent KV-view
candidate removed another `0.314 ms` of view preparation but improved whole
replay by only `0.086 ms` and regressed fresh generation. Host timings
therefore no longer identify the device-completion critical path.

The next diagnostic records one current-XPU-stream timestamp interval around
each existing replay callback. It changes no model operation, tensor,
arithmetic, kernel argument, graph, collective, or boundary order.

## Frozen source base

- main repository parent:
  `dcc769ed0` (`Record persistent KV-view diagnostic stop`);
- vLLM parent:
  `5da4a8ccdde0abe77d2dd2abda7b6a12bc74c01a`;
- production candidate functionality remains parent
  `ef334233deabeaeedb607056a2db1c90edb3887c`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- target and DFlash models remain the hash-frozen internal-NVMe copies below
  `/mnt/fast-ai/llm-models/laguna-s-2.1`.

Any implementation and runtime harness must be separately committed and
audited before an XPU action.

## Event-profile contract

The profiler is default-off and requires a new owner-private internal-NVMe
output root. The controller must create the root with mode `0700`, verify it is
empty before launching workers, and pass the already validated path to every
rank. Worker-side validation permits only safe `rank0.json` through
`rank3.json` siblings because one rank may publish before another first enters
the profiler. Each rank must publish only its own file with `O_EXCL`; the
analyzer requires exactly all four files and no others.

The profiler is mutually exclusive with:

- the existing host replay profiler;
- raw Laguna evidence;
- PTI/unitrace temporal control; and
- attention-subgraph capture.

On exactly the first audited M8 replay per rank:

1. require the existing `146 graph / 97 collective / 48 attention / 0 other`
   ordered topology;
2. freeze the current XPU stream identity;
3. create one timing-enabled XPU event before the first callback and one after
   each of the 291 callbacks;
4. record every event on that same explicit stream;
5. perform no per-boundary synchronize, wait, host copy, tensor hash, or
   profiler call;
6. perform exactly one `torch.xpu.synchronize` after the final event;
7. convert the 291 adjacent event intervals to integer nanoseconds; and
8. write one exclusive rank-local JSON file, then return permanently to the
   ordinary uninstrumented replay path.

The result must fail closed on a missing/extra callback, kind/order drift,
stream drift, non-finite or negative duration, unsafe root, duplicate file,
second instrumentation or write attempt, or incomplete four-rank closure.
After the one successful write, subsequent ordinary replays must bypass the
profiler rather than fail.

## Interpretation limit

This is a rank-local **current-stream interval profile**, not a proven global
TP4 critical path. `torch.xpu.Event` timestamps work recorded on one stream,
whereas final `torch.xpu.synchronize` drains all streams. A collective interval
may undercount work issued on an internal XCCL queue unless source/runtime
evidence proves that completion is dependency-joined to the recorded stream.

The analyzer must therefore emit:

```text
global_critical_path_validated=false
collective_cross_stream_completion_validated=false
diagnostic_only=true
not_benchmark_or_submission_evidence=true
```

Attention and graph intervals may guide a later candidate only after the
analyzer validates the exact topology and chooses the slowest rank by total
start-to-end event time. It may not add per-category maxima from different
ranks into a fabricated total.

## First execution ladder

Before any model or XPU action:

- implement CPU-only fake-event tests for ordering, explicit-stream recording,
  one final synchronization, schema, output exclusivity, and every failure
  branch;
- run the focused Breakable graph tests, Ruff, formatting, whitespace, and
  relevant vLLM pre-commit checks;
- commit the exact vLLM source;
- construct a separate fail-closed two-arm controller and analyzer;
- freeze every source, model, runtime-library, kernel-binary, environment, and
  command identity; and
- obtain independent read-only approval of the complete packet.

Only then may one fresh canonical q1 teacher process and one fresh graph/event
process each perform one 272-token generation. Both must report
`cached_tokens=0`, finish by length, and match token IDs and text bitwise.
All four rank profiles, worker-cleanup reports, and strict pre/post idle checks
must pass. No retry, endpoint campaign, benchmark payload, network access, or
LocalMaxxing submission is authorized by this preregistration.

## Decision rule

- If current-stream attention intervals dominate, design a separate
  arithmetic-identical eager-FA2 submission candidate. A fully capture-time
  prebound thunk is currently forbidden because `max_seqlen_k` is a changing
  host scalar passed into the actual FA2 operation.
- If graph intervals dominate, investigate only replay-plan submission
  overhead without changing graph coverage or arithmetic.
- If collectives appear dominant, first prove current-stream/XCCL completion
  joining. Direct collective capture and collective coalescing remain terminal.
- If no category has a material non-overlapped interval, stop host-side
  micro-optimizations and return to a materially different device-kernel lane.
