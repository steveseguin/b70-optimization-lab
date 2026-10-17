# Packet 57: measure the remaining draft work inside the engine

This is CPU-only preparation on `steve-b70s`, starting from packet 56's
unchanged target and 91,392-row draft head. Packet 56's submitted two-card
record remains **46.962697 tok/s** (`cmvcf84kb06r2le0174bgk16l`). Packet 57 is
a diagnostic, with no performance or quality claim before the coordinator's
device run.

All preparation uses nice 19 and cores 4–15,20–31. Python runs with `-B`;
compilation is serial. Packet 55's route work on cards 2+3 and all sealed
parent packets remain protected. This task does not launch a GPU program,
touch a service, change host settings, read model payloads or create an oracle.
The coordinator must admit the later cards-0+1 window against actual host
memory and ownership; different cards alone do not make concurrent runs safe.

## Why this measurement comes next

Packet 53b/54's operator savings transferred only partly to the full engine.
Packet 56's smaller head transferred much more directly. Future choices are
therefore ranked by their cost and critical-path effect inside the engine.
An operator microbenchmark alone cannot justify the order of work.

The real draft's routed expert path uses INT8: `mtp.hpp` sets
`w.int8=routed&&!e.a.mini`, then requantizes the publisher's FP8 expert
weights. The target's packed-IQ expert optimizations do not cover this path.
This is the existing packet 56 draft arithmetic, not a new quantization.
Every proposed token still needs the unchanged full target verifier.

The old KD site/timing files contain no draft profile. The native request
receipts retain host-clock command boundaries, which support a useful
pipeline reconstruction, but do not establish individual GPU kernel costs.
Packet 57 adds those observations without changing numerical kernels.

## What the retained engine receipts show

The analysis covers all twelve prompts: 1,524 emitted-token intervals, with
1,197 hits and 327 misses. Rank 0 finishes last in 1,411 of the 1,512 cycles
that contain both target halves (**93.32%**). The packet 56 hit/miss figures
are reproduced at **18.219585 / 33.043510 ms** using the earlier
median-of-request-means definition.

Individual-cycle hit medians are D **1.9030 ms**, S **16.1467 ms**, and B
**15.9551 ms**. Miss medians are D **1.8890 ms**, rollback **1.6111 ms**,
corrected rank-0 half **14.7547 ms**, S **16.7567 ms**, and B **16.1034 ms**.
Rank 0 has about **1.97 ms** outside host command envelopes on hits; rank 1
has about **15.08 ms** on misses. These are host observations, not measured
GPU idle. The large miss gap waits for corrected state.

All 92 retained site files checked across KD, WS, WS128x and WS128 are empty.
There are no measured boundary-layer costs to use for a reliable split
forecast. Average-half sensitivity instead gives **−0.53% for 22/26** and
**−3.75% for 24/24**. With the stated rank-0 assumptions, 22/26 breaks even
only if the moved layer costs less than **0.52526 ms** on rank 1. Packet 57
will measure boundary layers 22 and 23 rather than treating averages as
individual-layer measurements.

Moving the draft to rank 0 has no inherent hit benefit under the current
model and loses draft/correction overlap on misses: even the optimistic
unchanged-cost case is **−1.86%**. Removing 1 ms from D has a conditional
**+3.82%** rate sensitivity. These calculations are neither speed claims nor
forecasts of the class-balanced record metric.

## Diagnostic design

The narrow chain is **K0 → KD → W57-control → W57-attribution**. It inherits
the sealed packet 56 operator and handoff proofs, then checks the new binary
and draft before two fresh rank pairs run the complete twelve-prompt suite.
Both arms retain the 128-token cap and compare against the existing packet 49
target oracle. The instrumented arm records GPU events at generated indices
9–16 for the full draft and target layers 19/22 on rank 0 and 23/24 on rank 1.
The four target layers cover QSA and GDN on each rank.

Control preserves packet 56's existing deferred draft-event checking. The
new event recording uses existing drains without adding kernel barriers;
profiling and bookkeeping still perturb overlap. The report pairs both cycle
and draft wall times, requires complete sampled classes and both hit/miss
coverage, and labels scaled costs as estimates. Sparse target events cannot
measure complete GPU idle; direct bulk snapshot copies remain outside the
new event breakdown and inside the measured command envelopes.

The planned window is **5,265 seconds (about 88 minutes), including
cooldowns**, with an eight-hour cooperative outer deadline. This is a planning
budget; no packet 57 device duration has been measured.

## Evidence and handoff

- [Timeline and limits](../experiments/own-xpu-runtime/stage2/packet57-attribution/TIMELINE.md).
- [Ranked next levers](../experiments/own-xpu-runtime/stage2/packet57-attribution/LEVERS.md).
- [Coordinator window](../experiments/own-xpu-runtime/stage2/packet57-attribution/WINDOW.md).
- [Independent review](../experiments/own-xpu-runtime/stage2/packet57-attribution/REVIEW.md).

Timeline implementation and receipts were committed and pushed as
`a962cdeac`. The independently reviewed instrumentation, analysis and window
implementation was committed and pushed as
`07ff6be275c356186de2f197bd4ec20ca88cc80b`.

The final GNU host and SYCL builds pass. Four fresh host-only miniature Engine
runs (packet 56 control, packet 57 control, and two instrumented repeats)
match all 24 target tokens, draft proposals, hit/miss counts and 96 retained
layer fixtures per run. Five recorder/admission checks, seven timeline checks
and seven paired-analysis checks pass. The latter include incomplete/zero
events, wrong-rank or missing samples, and excluding partial cancelled layers
from complete-layer costs. The CPU plan-only coordinator inspection also passes.

The independently rechecked final seal is
`dcbbb5594f120a73e6ae34898472c939098a38ef442aca0883658283f3e0631b`,
binding 27 binaries and 496 source files. Retained build files total
**336,332,092 bytes**, below the 1 GB cap. Cleanup removed only this packet's
58,593,368 bytes of regenerable compiler objects. The final read-only storage
check admits the future 3 GB diagnostic output budget while retaining the
8 GB free-space floor; admission must be checked again at launch.

No device executable was run. Packet 56 and its seal remain unchanged, and
concurrent packet 55 changes were excluded from this task's commits.
Target-oracle equality, actual class costs and instrumentation perturbation
remain device-run gates. [CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet57-attribution/CPU-PREPARATION-CLOSEOUT.md).
