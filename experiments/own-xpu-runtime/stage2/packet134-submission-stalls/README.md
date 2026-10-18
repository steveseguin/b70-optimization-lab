# Packet134: rank-0 submission stalls

**Decision: close command replay for this evidence.** The sampled rank-0
compute gaps are concentrated before target submission, not inside its enqueue
loop. No runtime candidate, build, smoke, bracket or queue proposal is warranted
by these receipts. This is the brief's conditional attribution closeout, not a
claim that the lane is finished or that an uninstrumented run cannot stall.

The [reproducible attribution](ATTRIBUTION.md) uses all 84 complete packet128b
cycles (66 hits, 18 misses), without choosing prompts or outcomes. The
[machine-readable report](evidence/attribution.json) retains each cycle,
transition totals, means, medians and the explicit failed overhead gate.

## What the gaps actually contain

For a hit, **1.594 of 1.679 ms** of observed compute gaps is the single
`snapshot.capture.flat → begin.0` boundary. Only **0.0848 ms** is between
the speculative target's kernels, plus 0.0007 ms inside the suffix head.
For a miss, 1.471 ms precedes speculation and another **2.046 ms** is
`rollback.restore.flat → begin.0` before correction. The speculative and
correction sequences each contain about **0.085 ms** of internal gaps.
The current speculative half issues **564 kernels**, not the historical
one-card count of about 1,790. Its host enqueue loop averages **2.860 ms**
on hits while its target kernels occupy **11.363 ms** of compute time.
These durations overlap; removing the whole enqueue duration would not save it.

The source region between snapshot completion and the first target kernel
contains position admission, history readback, token upload and
`prepare_token()`. That function reads the embedding/PLE rows on the host,
decodes them and uploads their results before the loop. Its measured host
duration averages **1.527 ms** on hits; correction preparation averages
**1.942 ms** on misses. The sampled halves report **2.455 major faults/hit**
and **3.333 major faults/correction**. This is evidence consistent with
lookup residency pressure, not a measurement of time spent servicing page
faults. The receipts cannot separate lookup reads, CPU decoding and H2D wait
within preparation. A compute-only recording cannot remove those operations.

The **1.885 ms host command gap** on a hit is a different quantity:

- **1.286 ms** occurs before speculative-half entry. **1.276 ms** of that
  overlaps the rank1 draft command on the shared host clock. In
  `native_controller::run`, rank0 first calls `b.wait(1)` for the pending
  draft, then hands over the prior hidden state and starts rank1's target
  half. Only then does it measure the explicit draft-publication wait.
  Thus the separately reported **0.0073 ms publication wait does not mean
  rank0 never waits for drafting**. The overlap includes draft host
  preparation/submission; it is not all draft GPU execution.
- **0.598 ms** occurs after the speculative half and before accept. The
  controller services its suffix head and waits for rank1's verified reply
  in this region. On misses this is **0.602 ms before rollback**. It is
  useful head/transfer/controller work as well as any wait, not an empty
  host enqueue interval. Rank0's measured wait for rank1's hidden-state
  publication is only **0.0012 ms** in this instrumented sample.
- On misses, the pre-speculation command gap is **1.305 ms**, of which
  **1.293 ms** overlaps rank1's draft command. The remaining correction and
  accept command boundaries total 0.0027 ms.

All host overlaps use same-request `steady_clock` intervals from the two
processes. No host timestamp is subtracted from a GPU timestamp, and no copy
timestamp is used as a compute timestamp. Explicit publication wait is inside
the command gap; these are not additive costs.

## Evidence limits

Packet128b measured **51.475451 tok/s**, below its own **52.2 tok/s** overhead
threshold. Its 63-interval diagnostic is not a qualified speed result. The
sampled speculative halves report **5.211 ms of profiling work on hits**
after submission. Instrumentation can delay suffix service and change which
peer is ready first. The findings describe the observed trace only; no
whole-suite causal ranking, expected speed gain, or ordinary bundle7 stall
percentage is inferred. The 201 excluded discontinuous compute boundaries
include missing-ID and fixture transitions, not measured zero gaps.

## Ledger checked before choosing a lever

- [Packet22](../packet22-replay/backend-notes.md): prepared both recording
  designs, but native closure ABI, lifetime and pool ownership require their
  own proof. H2D and host work remain outside captures. Exporting a graph's
  compute list alone omits event/reset state.
- [Packet34 actual device receipts](../packet34-replay-bench/receipts-card3-20261012-r1/README.md):
  1,142 real kernels on synthetic resident data, direct 19.82 ms, one graph
  19.86 ms, layer graphs 20.11 ms; 420/420 byte comparisons pass. Recording
  worked but did not speed up that different workload. Its 3–5 microsecond
  smallest-kernel times were device dispatch, not removable host delay.
  This is supporting history, not a matched packet124c control.
- [Packet35](../packet35-hostpath/README.md): prepared argument blocks already
  exist and are used here. `Engine::prepare_commands()` captures them for
  both state-bank parities; `issue_site()` issues them without rebuilding
  per-kernel arguments. Reintroducing that mechanism would duplicate it.
- [Packets61/61x](../packet61x-spin-hcfusion-wait/WAIT-AUDIT.md): mailbox,
  completion and draft-progress waits already use the pure-spin policy with
  bounded cancellation and periodic yield. An old sleep-policy assumption
  would be wrong. Current `enqueue_family_ms` is null because this was
  attribution timing, not class timing; no family times are invented.
- [Packet70](../packet70-record-bundle/DO-NOT-REPEAT.md): record-bundle and
  postprocessing history; it is not a second command-graph speed result.

Source anchors: packet124c [half boundary](../packet124c-record-bundle/rank.hpp),
[controller](../packet124c-record-bundle/native_controller.hpp),
[token preparation and prepared enqueue](../packet124c-record-bundle/main.cpp),
[suffix service](../packet124c-record-bundle/p105_runtime.hpp), and packet128b
[command-gap recorder](../packet128b-attribution/rank.hpp). Exact source hashes
and all 182 unchanged packet124c symlinks are in [input-pins](input-pins.json).

## Reconstruction and gate scope

From the repository root, with the retained packet128b receipts available:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet134-submission-stalls/analyze.py </dev/null
```

The analyzer verifies 70 pinned inputs, including all 24 original-budget
hashes for the twelve native results and twelve rank0 event files. It
reproduces four original budget rows' means and medians within 1e-9 ms and
checks every speculative/correction half's 564 launches and 24-layer coverage.
Input pin creation is a one-time operation and refuses to overwrite a pin file.
The original dirty packet128b `BUDGET.md` is read and pinned, never edited.

No arithmetic, runtime, controller, reset, drain, launch environment, native
argument or queue code changed. GNU/Intel byte gates, mock hit/miss/rollback,
reset, full-window argument/queue gates and device seals are therefore **not
run and not claimed** for a new candidate. No executable candidate exists.
If a future implementation opens, it must pass the brief's entire gate list,
12 × 64 smoke and then a matched bracket; this analysis cannot qualify it.

Only this new packet, its work note and `CURRENT.md` are task writes. No GPU,
service, sudo, host setting, live queue or existing packet was changed. No
compilation was needed, so no compiler turn was taken. Build bytes: zero.
CPU entrypoints cap their own address space at 8 GiB; imports install no cap.
The root-space threshold remains 25 GB. No model weights or secrets are read.

The next useful work is to split token preparation into lookup/decode/copy
durations with low overhead and compare exact residency/transfer approaches
under current memory admission. A separate draft-startup timing should retain
the pending-command wait, not just publication polling. Neither follow-up
changes host page-cache settings or bypasses output checks.

[Work note](../../../../notes/2026-10-18-own-runtime-packet134.md).
