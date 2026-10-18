# Packet128: fresh bundle7 attribution

CPU preparation of one diagnostic lane-B load. No GPU was used here.
The coordinator runs 12 registered prompts once, 64 tokens each. Every token
must equal `iq3-p49-split32-v1`. There is no separate incident prompt: the first
suite request supplies the 64-token incident check. One load, 13 resets including
the final drain boundary, 3,600-second watchdog (four times the 15-minute estimate).

This copies packet124b, including its K2 projection and drain fixes. Selection,
all arithmetic kernel objects, 24/24 placement, 80,128-row draft prefix, target
head split and BF16 KV are unchanged. The only rebuilt runtime object is the
engine entry containing observation hooks. [Parent hashes](parent-manifest.json)
and [inherited object hashes](evidence/object-identity.json) bind that claim.
Packet77 supplies the event-recorder approach, extended to every layer and every
generated token. No new kernels or synchronization barriers are inserted.

Events include every target class, draft classes, prefix and suffix heads,
transfers, snapshot capture and restore. Completed events are queried before
retirement. JSON is buffered per request and flushed outside its timed work.
Explicit head waits use the host clock. Native traces retain draft publication
waits and command envelopes. Device timestamps are compared only within a rank,
with the compute-only head selection required. Missing event IDs break gap
accounting rather than silently converting unobserved work into idle time.

The copied worker retains v4 admission, closed environment, selected-card
monitoring, faults, locks and graceful drain. `teardown.py` clamps the shared
wrapper's cooldown sleep, including the deadline-crossing race. `screen128.py`
is a byte-for-byte copy of the pinned v4 screen except for its evidence-output
namespace predicate: new receipts stay inside packet128 instead of the frozen
screen tree. A CPU test enforces that exact one-line difference. No shared wrapper
or live queue was edited. Runtime entrypoints never install CPU resource caps.

## Coordinator command

Use the single job in [the proposed B queue](../../ops/lane-queue/proposed-p128-attr-B.txt).
It must be copied into a temporary queue directory for planning, never directly
run from this CPU preparation session. The actual job remains coordinator-owned.
No automatic retries or second model load are registered.

After the device window releases its lease:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet128-attribution/analyze.py </dev/null
```

This writes [BUDGET.md](BUDGET.md) and `evidence/budget.json`. The first section
compares the class-balanced 63-interval rate with historical bundle7's
58.0–58.3 tok/s. At less than 90% of 58.3, instrumentation is intrusive and the
lever ranking is withheld. This historical comparison has a different response
length; it is a diagnostic distortion check, not a paired causal overhead claim.

The budget separates both ranks and hits/misses, includes all classes and queue
gaps, and retains the named waits. Work is assigned to the prediction it serves,
including correction on a miss. That semantic assignment is not an exact wall-time
partition: draft launches cross cycle boundaries. Host waits overlap GPU work.

Ranked critical-path figures are ideal removable-work limits. The 20% compute
reduction scenario and >=0.5% gain bar are explicitly optimistic projections;
unknown exposure and overlap require a subsequent matched engine experiment.
Transfers, rollback and queue gaps remain visible with unknown recoverability.
No output-changing optimization or speed headline is adopted here.

## CPU verification

`cpu_prepare.py` installs CPU-only limits in its main process: nice19,
CPUs 8–15/24–31, at most 8 GiB, closed stdin. `build_engine.py` uses packet94's
serial compiler turn and waits out whole-host reservations. Root requires 25 GB
free and build files are capped at 250 MB. GNU host and Intel device-target
compilation do not initialize a GPU.

- Parent, control and two fresh instrumented miniature runs compare all 24 tokens,
  96 layer fixtures, draft proposals and draft final state. Miniature tests use
  default choices because production-only split-head layouts require real shapes.
- A one-load control / instrumentation / control test checks reset equivalence.
- Full production-shape mock startup checks both ranks' real selection consumers,
  allocation census, head split and draft prefix without reading weight payloads.
- `argument_gate.py` follows packet124b's intercepted-execution pattern. It drives
  the real worker through oracle/selection/placement checks to both native argv,
  then parses those arguments in a host-only full-shape fixture. Monitor admission
  and native priority are explicitly synthetic; original argv is retained.
- Analysis tests reject missing layers, zero-duration compute, incomplete tokens,
  failed exactness and intrusive timing. Worker tests check exactly 12 × 64 and
  reproduce the old cooldown failure as a negative control.

The full model's device equality, measured overhead and class budget are pending.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md),
[final source and queue checks](evidence/final-check.json),
[retention and reconstruction](RETENTION.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet128.md).
