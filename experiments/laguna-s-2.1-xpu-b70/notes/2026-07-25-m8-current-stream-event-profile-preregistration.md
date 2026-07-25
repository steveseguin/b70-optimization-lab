# Laguna M8 current-stream event-profile preregistration

Date: 2026-07-25 America/Toronto

Status: **completed exact diagnostic stop; no benchmark or submission
authorized**.

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

## Committed implementation packet

The default-off runtime implementation is frozen at vLLM
`fcc2506f7da3a9fd142928af9275d25b9687342a`. Its focused Breakable-graph
suite passes `36` tests with `11` expected CUDA-only skips, and the complete
two-file vLLM pre-commit set passes, including Ruff, formatting, mypy,
forbidden-import, and new-device-API checks.

The dedicated two-arm packet is:

- `tools/run_laguna_m8_current_stream_event_arm.py`;
- `tools/run_laguna_m8_current_stream_event_diagnostic.sh`;
- `tools/laguna_m8_current_stream_event_contract.py`;
- `tools/analyze_laguna_m8_current_stream_event.py`; and
- `tools/test_analyze_laguna_m8_current_stream_event.py`.

The analyzer's focused CPU suite passes nine tests, including an explicit
anti-fabrication fixture where the slowest total, largest attention sum, and
largest collective sum occur on different ranks. The selected decision still
uses only the slowest rank's own category sums. The controller, driver,
analyzer, shell syntax, Ruff, formatting, and whitespace checks must all remain
clean at the packet commit. No XPU or model process was run
while constructing this packet.

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

## Executed result

The one authorized execution completed at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-current-stream-event-f42f55690-fcc2506f7-20260725T052434Z
```

The root is sealed mode `0500` and its files are mode `0400`. The exact source
identity was main `f42f5569029480b7e253c4996c188db6efe14254`, vLLM
`fcc2506f7da3a9fd142928af9275d25b9687342a`, and kernels
`4772f727590c51b72add79350b913d098cf67872`.

Exactly two fresh processes each made one generation call. Both q1 and
graph-event arms reported 55 prompt tokens, 272 completion tokens,
`cached_tokens=0`, and finish reason `length`. Their token arrays matched
bitwise, with token SHA-256
`ee44dfe987c199b248cfe8f752f5fa8600a34291815894c5fb6502ffd5187cee`;
their text SHA-256 was
`d41518e5781b3adafb966c1b9a91e46d4d23b1a1ef40d8992ccde9a55920e55f`.

All four rank profiles contained the exact preregistered 292 events and 291
intervals: 146 graph, 97 collective, and 48 attention. The rank-local total
durations were:

| Rank | Total ns |
| ---: | -------: |
| 0 | 122,850,884 |
| 1 | 123,062,992 |
| 2 | 124,614,464 |
| 3 | 123,328,348 |

Rank 2 was therefore selected before inspecting category dominance. Its own
category sums—not cross-rank maxima—were:

| Category | Duration ns | Share |
| -------- | ----------: | ----: |
| graph | 80,297,412 | 64.436671% |
| collective | 34,930,532 | 28.030881% |
| attention | 9,386,520 | 7.532448% |

The frozen analyzer emitted `exact_event_profile_stop`, selected `graph`, and
authorized only `replay_plan_submission_research_only`. It explicitly emitted
`global_critical_path_validated=false`,
`collective_cross_stream_completion_validated=false`,
`diagnostic_only=true`, and `not_benchmark_or_submission_evidence=true`.

An independent read-only audit recomputed the closure hashes, exact-output
comparison, idle/worker evidence, per-rank totals, slowest-rank selection, and
category arithmetic without discrepancy. The audit retained the same caveat:
these are rank-local current-stream intervals, and the collective intervals do
not prove XCCL auxiliary-stream completion.

No retry, endpoint campaign, network access, benchmark payload, or
LocalMaxxing submission occurred. Continue only with an arithmetic-identical
replay-plan/submission-overhead **source audit**; do not infer that an
attention fusion is the primary next lever from this result.

## Post-run source-audit interpretation

The required replay-plan source audit closed a pure Python replay-loop
candidate before any benchmark. The adjacent XPU events are enqueued on the
same current stream, so their elapsed times measure device work issued by each
callback; they do not include the host gap spent calling the callback. The
earlier exact in-process host telemetry already bounded all 146 Python graph
replay calls at `2.097430 ms` median and `2.306479 ms` p90 per whole M8
replay. Therefore the `80.297412 ms` graph-event sum is not evidence of
`80 ms` of replay-list or Python submission overhead.

The source-verified topology is a two-interval prefix, 48 identical six-
interval decoder-layer bodies, and one final graph tail. For layer `L`,
`s = 2 + 6L`:

| Interval | Kind | Source-level range |
| -------: | ---- | ------------------ |
| `s` | graph | input RMSNorm/residual, QKV projection, Q/K RMSNorm, RoPE |
| `s+1` | attention | paged-attention body |
| `s+2` | graph | attention gate/softplus/materialization and local O projection |
| `s+3` | collective | O-projection fixed-address BF16 all-gather |
| `s+4` | graph | post-attention RMSNorm/residual and local dense/MoE work |
| `s+5` | collective | dense down-projection or MoE-combine all-gather |

The prefix is input/embedding graph work followed by the embedding all-reduce;
the tail is final RMSNorm and downstream graph work. On selected rank 2, the
three repeated graph classes measured:

| Repeated graph class | Count | Total ns | Mean ns |
| -------------------- | ----: | -------: | ------: |
| pre-attention | 48 | 25,393,732 | 529,036 |
| post-attention/local O | 48 | 23,700,404 | 493,758 |
| post-attention/local MLP | 48 | 30,126,720 | 627,640 |

The local-MLP class is the largest repeated graph class. It contains
post-attention RMSNorm/residual and, for MoE layers, replicated routing plus
FusedMoE dispatch/expert/local computation. The event profile does not resolve
individual kernels inside that segment, so it does not by itself prove that
one expert GEMM or router kernel dominates.

Merging graph replays is not available because the graph intervals are
causally separated by attention and collective callbacks; the known failed
attention capture and terminal collective capture/coalescing lanes remain
closed. A native replay trampoline or prebound tuple iteration is deferred as
a low-ceiling host micro-optimization rather than promoted to a record
campaign.

The next lane is an isolated, arithmetic-identical M=8 local-MoE device
candidate: first inspect persistent workspace/address churn and current expert
W1/W2 dispatch/tile headroom, then change only one lever while preserving
router top-k ordering, grouped-GEMM reduction traversal, BF16 materialization
points, graph topology, and fixed all-gather order. Pure layout/copy/indexing
fusion is permissible only if every arithmetic boundary remains identical.
