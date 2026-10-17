# Packet 74: read dense weights in packed GGUF form

CPU preparation started October 17 on steve-b70s. No GPU use. Packet70 sources
and v4-lanes wrappers are frozen inputs; only new packet74 files and proposed
queue files will be added. Target arithmetic remains iq3-p49-split32-v1 and
packet49 is the oracle. CPU tasks use nice19, CPUs8-15,24-31, Python-B, closed
stdin, at most8 GiB address space and serial compiles. Build budget <1 GB.

## History milestone

Expansion was a measured optimization, not just a convenience. Packet10's
[format and measured results](../experiments/own-xpu-runtime/stage2/packet10-kopt5/README.md)
explain it: cache signed integer codes and exact F32 subscales at load time,
removing planar bit extraction, repeated half conversion and scale work from
GEMV. Keep separate scale×code, weight×input and accumulator-add rounding.
Q6 uses338 resident bytes per256 weights (320 fetched); GGUF uses210.
Q8 uses38 resident bytes per32 (36 fetched); GGUF uses34.

Measured historical operator sequences on card3, October11:

| Sequence | GDN ms | QSA ms | Head + final HC ms |
| --- | ---: | ---: | ---: |
| Packet9 / round4 packed, fused experts | 1.14 | 1.07 | 5.47 |
| Packet10 expanded SG32 | 0.89 | 0.77 | 2.19 |
| Packet10 expanded split4 | 0.78 | 0.77 | 3.27 |

These are complete synthetic operator sequences, not isolated head timings
or full-model throughput. Receipts are in packet9/receipts-card3-20261011 and
packet10/receipts-card3-20261011. They show that blindly restoring old packed
kernels loses. They do not isolate an ALU, alignment or vector-load cause.

[Packet7 analysis](../experiments/own-xpu-runtime/stage2/packet7-kopt2/README.md)
identifies short staging bursts, barriers followed by serial unpacking, and
large whole-row SLM allocations (Q6 QKV8448 B/group; Q8 HC43520 B/group).
Those are plausible bottlenecks, not measured hardware counter attribution.
[Packet25 negatives](../experiments/own-xpu-runtime/stage2/packet25-gemv/DO-NOT-REPEAT.md)
close the R6 SLM pair/packed pipeline at2.34/2.60 ms versus0.298 ms; that is
routed-expert work, not a dense Q6 result. It must not be repurposed as evidence
against every packed dense implementation. Later names such as p27.packed64
refer to wide loads from expanded rows, not original GGUF residency.
Stage1/stage2 notes and DO-NOT-REPEAT records were searched for packed/expanded
Q6/Q8 paths; no later measured exact packed dense replacement of packet70 was
found. Packet24 already lists an exact packed-head alternative as a future
mechanism; packets67/69/72 establish the current expanded-byte bottleneck.

New mechanism: no whole-row SLM, no decode scratch launch, aligned word loads
of the GGUF block planes, unpack in registers, and the current eight-elements
per-lane traversal plus adjacent SG32/split4 reduction. Preserve every FP32
rounding boundary. Q6 block alignment alternates modulo4 (210-byte stride),
so aligned word extraction must handle that explicitly without overreads.
Q8's34-byte stride has the same issue. Performance is unknown until device
microbenchmarks and matched screens; fewer bytes alone do not prove a win.

Operational observations: git pull --rebase was attempted first and refused
because the coordinator's tracked orchestration log is dirty. Fetch showed
HEAD and origin/main equal (0/0); the log was left untouched. Root had28 GB
free. The explicit task's <1 GB budget governs this CPU preparation; no old
artifacts are cleaned. Packets71b/73 are being prepared by other workers.

## Kernel milestone

GNU and Intel each pass two fresh CPU fixture runs:60 cases and5,657,600
decoded values per run. FP32 lane accumulators, BF16 row outputs and attention
stream-combine bytes match. Fixtures exercise both block alignments,17 rows,
SG32 and split4, signed zeros, subnormal and maximal finite half scales.
[Byte evidence](../experiments/own-xpu-runtime/stage2/packet74-packed-dense/evidence/cpu-byte-identity.json).
Both engine builds pass, as does the coordinator-only microbenchmark compile.
The microbenchmark uses full248,320 × 2,560 head and10,240 × 2,560 QKV shapes,
one timed launch, matching SG32 arithmetic, separate FP32 device equality,
alternating control/candidate samples and event plus submission/wait timing.
It has not run. Initial compile caught a missing dependent-template keyword;
fixed before its successful build.

The head-only view preserves the draft's existing expanded arithmetic/kernel
by keeping only its91,392-row expanded prefix in a separate allocation.
Therefore net resident saving is8,944,640 bytes, not317,849,600: claiming the
latter would omit the prefix. Target-head traffic still falls34.375 percent.
The dense view covers QKV, Z, Q-gate, K/V, attention output, PLE projections
and shared down where their type is Q6_K/Q8_0. Fused HC and small-FFN tuples
retain their expanded storage and kernels; raw F32/BF16 routers cannot be
converted to GGUF Q6/Q8 without changing weights. No full-model speed or
device quality is claimed. Seals and coordinator screen plans follow.

## Sealed screen milestone

All four views are sealed around one engine binary. The copied v4 wrapper
passes 79 mock checks. All 14 possible screen plans pass (five A screens and
three possible three-screen B sandwiches); only the winning B sandwich will
execute. Both proposed queue files pass the existing lanequeue planner on a
private copy. Live queues and frozen packet/screen trees were not edited.

Dense packing saves661,749,760 resident bytes on rank0 and673,382,400 on
rank1 by calculation. Combined saves661,749,760 and 682,327,040, including
the separately retained expanded draft prefix. Measured peak VRAM is pending.
The coordinator's B job requires all five A screens exact and picks the best
candidate only if it beats both controls. No win means no B launch. All
13 original exact requests, masking, leases, shared drains,90-second gaps and
release before reporting remain. Screens stay diagnostic at 128 output tokens.

[Handoff and queue proposals](../experiments/own-xpu-runtime/stage2/packet74-packed-dense/WINDOW.md),
[final CPU verification](../experiments/own-xpu-runtime/stage2/packet74-packed-dense/evidence/final-validation.json),
[preparation closeout](../experiments/own-xpu-runtime/stage2/packet74-packed-dense/CPU-PREPARATION-CLOSEOUT.md).
The retained build is 125,278,746 logical bytes; engine compiler peak RSS
726,688 KiB, fixture315,576 KiB and microbenchmark356,388 KiB. Root remains
at 28 GB free. No GPU, model, service, privileged operation, setting change or
cleanup of another job's artifacts ran. Device execution stays with the
coordinator; device parity, determinism, actual memory and speed remain open.

## Lane-A admission repair (October 17, 21:02 UTC)

Packet 74 now registers `screen` as an exactness window. Planning and live
reservations call the same lane/window policy; a regression test removes that
registration and confirms planning refuses before inputs or a lease. All 82
CPU wrapper tests pass. `seal_and_plan.py` runs the packet CPU seal tools and
regenerates all 4 selection seals, preserving the previous receipts and
checking every engine artifact, selection, dispatch, placement and arithmetic
source against its existing hash. Parent-wrapper provenance is refreshed only
for the adopted v4 repair. No binary was rebuilt.

All 5 lane-A screen plans and the proposed lane-A queue pass; both packets
also pass together in a temporary queue. No live queue, GPU, model, service,
sudo or host setting was touched. Packets 69 and 72 were left to their other
job. [Repair receipts, plans and prior seals](../experiments/own-xpu-runtime/stage2/packet74-packed-dense/evidence/admission-repair/).
