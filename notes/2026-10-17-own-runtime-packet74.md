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
