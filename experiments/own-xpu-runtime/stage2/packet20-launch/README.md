# Packet 20: reduce the cost of issuing decode kernels

**CPU preparation only. No device ran. No issuing method has won a speed test.**
The host FAULT HALT remains binding. This packet leaves packets13–19, the parked
process, GPU services, `CURRENT.md`, the stage index and scoreboard unchanged.

The target is arithmetic `iq3-p17-detmath-v2`, with the same operations,
reduction trees and rounding points. Packet18 frozen parallel counts **2,445
physical kernels/token**. Packet16 card3 measured 3,619 launches/token on its
older integration; these are different identities. Packet15 measured a
14-launch non-GEMV sequence at 0.461 ms device span / 0.612 ms wall, despite
individual elementwise kernels taking only 3–7 us. These are motivation and
historical measurements, not measurements of packet20.

At an assumed 30 us per issue, 1,100 launches would consume 33 ms before useful
work. Beating the supplied 28.49 tok/s reference therefore needs replay as well
as fusion unless a future measurement overturns that issuing cost. The 5–10×
target applies to issuing overhead, not a promised model speedup. Fusion cannot
make the measured GEMV time disappear. A graph can reduce host submissions
without reducing its internal kernel count.

## Decision table awaiting the device window

Each method runs N=100/1,000/4,000, five repeats, on two workloads: BF16
2,560-value elementwise with 17 pointer arguments, and a small GEMV-like loop.
All explicit-event methods wait once per chain; `explicit_wait_each` is an
extra diagnostic control, not the current runtime default. The fusion8 arm
performs the same N operations using ceil(N/8) launches (13 at N=100).

| Issuing method | CPU preparation | Wall/device ns per launch | Decision after measurement |
| --- | --- | --- | --- |
| Explicit dependencies, in-order | Compiled; unrun | Not measured | Reference for current owner pattern |
| Explicit dependencies, out-of-order | Compiled; unrun | Not measured | Does queue ordering add avoidable issue cost? |
| Explicit event + wait per kernel | Compiled; unrun | Not measured | Diagnostic synchronization cost |
| In-order, discard returned event | Compiled; unrun | Not measured | Separate event retention from submission cost |
| In-order `discard_events` | Compiled; unrun | Not measured | Does avoiding events improve issue cost? |
| SYCL graph record/finalize/replay | Compiled; unrun | Not measured | Prefer if changed-input exact and substantially cheaper |
| Raw Level Zero regular list replay | Compiled; unrun | Not measured | Compare graph lowering against native replay |
| Raw Level Zero immediate list | Compiled; unrun | Not measured | Compare issuing per kernel at native API |
| Eight operations per kernel | Compiled; unrun | Not measured | Measure fusion alone at unchanged total work |

Graph setup/finalization and raw module/list construction are reported separately
from replay. Five replay inputs change through a small device token-state block;
its one H2D copy is outside recording and outside the timed span. Output reset
and verification are also outside timing. Both are reported so these small
measurements cannot be presented as whole-token latency. The dynamic-parameter
API has a separate compile/link probe; pointer-stable device state is the
implemented replay arm. See [issuing implementation](issuing/native.cpp),
[build evidence](issuing/build-receipt.json) and [window](WINDOW.md).

For methods without kernel profiling events, the device-clock envelope includes
host issue gaps and completion observation. It is not summed kernel execution
time. Use the row definitions and matched timing fields; do not compare unlike
columns as though they measured the same thing. For fusion8 compare total
chain wall time or `wall_ns/N`, not per-physical-launch time. The window writes
a 54-row median summary from its five repeats, without declaring a speed winner.

## Fusion count and exactness

Calculated minimum launch counts under the stated legal schedules (not
measurements or an integrated implementation):

| Frozen dispatch scope | Current | (i) non-GEMV chains | (ii) adjacent GEMV fusion/siblings | (iii) indexed routing |
| --- | ---: | ---: | ---: | ---: |
| Ordinary GDN, layer 0 | 49 | 41 | 20 | 20 |
| GDN + PLE, layer 1 | 59 | 45 | 23 | 23 |
| Upgraded GDN, layer 2 | 47 | 39 | 20 | 20 |
| QSA, layer 3 | 55 | 44 | 20 | 20 |
| Whole token, including legal boundary joins | **2,445** | **1,971** | **926** | **926** |

The whole-token schedule joins 48 additional non-GEMV boundaries, including
initial stream expansion, 46 same-owner interlayer edges and final norm. The
two-card boundary stays explicit. R5 totals are **1,707 / 876 / 876** under the
same rules (baseline 2,181). These are separate dispatch identities.

Rule(iii) moves the exact top-10 normalization into an already scheduled
consumer, so distributed ranking needs no additional launch in the minimum
design. The implemented standalone route prototype keeps a separate finish
launch: that constructive schedule is **974 frozen / 924 R5**, before any
performance claim. Removing redundant gather mainly saves copies; it does not
magically eliminate another GEMV. The minimum frozen count is about **2.64×**
lower, so a 5–10× cut in issuing cost still depends on replay measurements.

See the generated [dependency DAG](fusion/dag.json), [fusion plan](fusion/README.md)
and [CPU gate](fusion/build-receipt.json). The plan includes every site, input,
output and per-layer special case, retains physical multi-pass GEMV counts,
and distinguishes a legal fusion schedule from a fast implementation.

The prototype copies packet17 v2 kernels into this packet. Consecutive phases
run with a real whole-phase barrier by using one work-group. This is a
correctness prototype: serializing every original group may cost more than it
saves. The separate routing prototype distributes exact probability ranking
and removes repeated hidden-row copies. Its new expert-input interface is a
design only; this packet does not edit any GEMV kernel or integrate the full
model. Device fusion parity and full-model fresh-process equality remain open.

The fixture gate compares every retained output/state byte against the unfused
v2 core under GNU and Intel host compilers, with two fresh processes each.
All four runs pass **72 operator fixtures, six multi-site chains, eleven
additional BF16 boundaries and eight control cases**, with identical output
hashes. The harness passes **23 CPU-only protocol tests**, including the full
270-row mock. Native fusion compiles and links with precision flags on both
lines. CPU
parity cannot establish device parity. Details and hashes are retained locally.

## Reproduce the preparation

From repository root:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 \
  python -B experiments/own-xpu-runtime/stage2/packet20-launch/build.py
```

This builds with at most two compilation jobs, executes only host programs,
runs mocked admission/fault/coverage tests, checks link flags and loader
resolution, and seals the future window. It never invokes a device program,
even for help or discovery. Scratch is removed; prepared build artifacts stay
under ignored `build/`. [REPLAY.md](REPLAY.md) covers dynamic model state,
context growth, exact masking, graph memory and two-card boundaries.
[Independent review](review/INDEPENDENT-REVIEW.md) records the fixes and limits.
