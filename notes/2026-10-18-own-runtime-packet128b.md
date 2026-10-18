# Packet128b — sampled in-engine attribution, October 18

The every-token recorder was too expensive: packet128's retained lane-B run
measured **42.211168 tok/s**, or **0.727779 × 58.0** and **0.724034 × 58.3**.
Its overhead gate failed. The new packet samples tokens **9–16** of each
request. Its device overhead is **not yet measured**; the coordinator owns that
run. This is diagnostic preparation, not a model speed result or promotion.

## What changed

[Packet128b](../experiments/own-xpu-runtime/stage2/packet128b-attribution/README.md)
is a new symlink-preserving copy of packet128. All **84 symlinks** match the
parent's `find -type l` inventory. The existing trees, shared screen wrapper,
ops files and live queues remain untouched. Old device receipts were excluded
from the new evidence directory. Parent source/configuration hashes and the
[copy audit](../experiments/own-xpu-runtime/stage2/packet128b-attribution/copy-symlinks.json)
are retained.

The recorder keeps all 48 layers on both ranks for each sampled token,
regardless of hit/miss. Unsampled tokens bypass the added event-record/report
work. Existing event ownership, draft timing and profiling behavior remain.
Only the engine entry is rebuilt; arithmetic objects, target weights, verifier,
BF16 KV, bundle7 selection, 24/24 placement and draft prefix stay unchanged.

The analyzer separates compute, automatic-copy and explicit BCS-copy routes,
and accepts additional identified queues. Physical automatic-copy engine IDs
are unavailable and are not invented. Queue busy time uses interval unions.
Compute gaps use only compute events with continuous observed IDs in the same
sampled fixture; no cross-rank or cross-route timestamps are subtracted.
Many copies in the retained old run have zero duration and a timestamp outside
the compute timeline. These are labeled unresolved rather than measured zero.
SnapshotFlat and batched snapshot kernels are correctly labeled compute.

Prediction cycles need both fixture k on rank0 and k−1 on rank1, so only cycles
**10–16** enter the budget: **84 complete sampled cycles** across twelve prompts.
Each cycle must cover all 48 layers; the sample must include hits and misses.
Unobserved cycles are never filled with zero costs. The analyzer builds no
ranking, including JSON, until throughput reaches **52.2 tok/s**, the requested
≥0.90 ratio to 58.0. Both baseline ratios are reported. Historical comparison
and sample cost projections remain explicitly limited diagnostics.

## CPU verification

- Host and device-target compilation pass; no GPU binary was executed. All
  compiles use packet94's serial turn, with one compiler at a time. The build
  waited for a coordinator whole-host reservation rather than bypassing it.
- Parent/control/two fresh sampled host-only miniature runs match all **24
  tokens, 96 target-layer fixtures, draft proposals and draft final state**.
  One-load control / sampled / control resets also match.
- Full production-shape startup and memory admission pass on both ranks.
  The actual worker input/oracle/selection path reaches both intercepted native
  argv; those arguments also pass the host-only production-shape native parser.
- **27 Python tests** cover overlapping and nested intervals, extra queues,
  copy-clock isolation, zero-copy timing, missing events/layers, sampling
  boundaries, failed exactness, threshold behavior, the real 12 × 64 worker
  flow, drain races and post-release report ordering. The actual C++ recorder
  separately passes token-boundary, all-layer and disabled-mode tests.
- Both actual intercepted rank exec boundaries preserve all inherited getrlimits.
  The finite-address-space negative control is refused. Its first test version
  reached the worker's cleanup path; the scratch-only audit blocked the attempted
  shared lock write. The test now exits directly at the intercepted refusal.
  No shared lock or protected file was written by that test.
- The all-window gate covers the **one window registered by this view**,
  `attribution-B`: all twelve worker requests and both ranks. The real lane queue
  loop and CPU plan run on a temporary proposal copy, testing success and failed
  child/no retry. Scheduler state and native replies are explicitly synthetic.
  Copied historical eleven-window chain commands are not registered here.
- CPU replay of packet128's intrusive trace now handles overlapping queue routes
  and retains all 84 sampled cycles. It still rejects the old throughput and
  produces no ranking. Queue labels in this replay are inferred and sampling is
  post-hoc; this is not packet128b device evidence.

The build is **128,711,121 bytes**, below 250 MB. The final check records actual
root headroom above 25 GB. All parent files in the source manifest remain
unchanged. CPU caps are confined to CPU-only main processes; the small positive
launch-limit probe intentionally retains the native launch environment.

## Coordinator handoff

Exactly one new proposal:
[proposed-p128b-attr-B.txt](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p128b-attr-B.txt).
One lane-B model load, **12 prompts × 64 tokens**, every token exact to the
registered oracle, no retry. Expected duration **4–6 minutes**; worker deadline
**1,440 seconds**, at least four times the upper estimate, with the inherited
3,600-second supervisor watchdog. Normal live admission remains required.

After successful drain and lane release, `run_screen.py` automatically invokes
`analyze.py` in a separate nice19, pinned CPU-only process. It writes
`BUDGET.md` and `evidence/budget.json`. Report failure surfaces without another
model load. The final source/argument/limits/queue checks are linked below.

**Pending:** actual sampled-device equality, measured throughput and overhead
ratio, both-outcome sample coverage, and any defensible class ranking. No GPU,
service, sudo, reboot, power/host-memory/swap/page-cache change or live-queue edit
was performed in this preparation.

[Final check](../experiments/own-xpu-runtime/stage2/packet128b-attribution/evidence/final-check.json),
[CPU tests](../experiments/own-xpu-runtime/stage2/packet128b-attribution/evidence/python-tests.log),
[argument gate](../experiments/own-xpu-runtime/stage2/packet128b-attribution/evidence/argument-gate.json),
[queue gate](../experiments/own-xpu-runtime/stage2/packet128b-attribution/evidence/queue-gate.json),
[limits gate](../experiments/own-xpu-runtime/stage2/packet128b-attribution/evidence/launch-limits.json),
[old-trace regression](../experiments/own-xpu-runtime/stage2/packet128b-attribution/evidence/parent-reanalysis.json).
