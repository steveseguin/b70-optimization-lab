# Packet58ag: remaining one-card target ports

CPU preparation, bounded to three hours from 2026-10-18 23:06 UTC. No device
execution, service, live queue edit or performance claim. Packet58ab is copied
with symlinks preserved; existing packet trees remain frozen.

HC fusion remains enabled in both controls and candidates. The new runtime
dimensions default to production: `hc_geometry=production|hc-wide`,
`experts=production|wide64|wide64+halfcache`, `other_fusion=production|fused`,
and `retirement=production|ordered-foreground`.
The inherited bracket token `p60fusion` names the full composition in this
packet only; it does not mean HC fusion is off in its production controls.
The smoke runs 12 × 64. The combined five-view bracket runs 12 × 128 per view,
one load: control/candidate/control/candidate/control. A0 must be exact but is
excluded from drift and speed comparison under the packet58wb rule.

The halfcache port uses an exhaustive 65,536-entry exact FP32 half-decode
table (262,144 device bytes), rather than packet90's larger packed weight rows.
This preserves the one-card cache's weight layout, expert pointers, tile16,
capacity and fill policy. It is an adaptation, not the original layout.
The fused router includes route-fast as an inseparable part of packet109's
implementation; there is no repeat of packet58r's standalone route arm.

Packet76 retirement checks the two in-order foreground queue terminals.
It still synchronizes both foreground queues and propagates asynchronous
errors. The maintenance queue keeps separate ownership through final drain.
Pending work refuses retirement and dimension changes; no event or allocation
is released based on the wrong queue's terminal.

All output must match `iq3-p49-split32-v1`. CPU bytes, device exactness and
speed remain separate gates. READY is written only after all CPU checks,
shared entry/report rehearsal, seals and temporary queue plans pass.

The composed plan submits 1,057 commands per half versus 1,345 for the
baseline. No timing is inferred from that count. Full-shape mocks exercise
each dimension and the composition at contexts 32 and 4096, with serial and
overlap maintenance and unchanged arenas. Both compilers compare real-shape
intermediate, output and status bytes in two fresh processes. The retirement
proof separately exercises pending work on both foreground queues and
maintenance ownership; it changes scheduling only.

The half table is charged by dividing the existing 1 GiB workspace budget
into 1,073,479,680 workspace bytes and 262,144 table bytes. The conservative
device bound remains 29,963,128,848 bytes and cache capacity 21,552,729,600
bytes. Host admission increases by 524,288 bytes to 98,990,252,032. These are
allocation budgets, not changes to host settings or proof of physical fit.

Build with `build_engine.py`; it uses `ops/compile_turn.py` and reuses an
object only when its exact command, dependency bytes and object hash match
the preceding receipt. `hc_gate.py`, `ports_gate.py` and `retirement_gate.py`
retain GNU/Intel byte and ownership proofs. Other gate scripts retain parser,
reset, capacity, asynchronous ownership, drain, launch-limit and report
checks. Use nice 19, affinity 8–15/24–31, Python `-B`, closed stdin and the
packet's CPU memory limits. Full-shape mocks reserve sparse address space
but do not read model files; they also enter the shared timing/compile gate.

The vendored archives above 1 MiB preserve the original source closure and
are necessary to rebuild. `frozen_inputs.py` restores their exact members;
`retention.py` retains historical extracted manifests under lineage so they
are not mistaken for active source pins. Build outputs are ignored, capped
at 300 MB, and reproducible. Immutable historical binary links are hash-bound
by the local admission manifests. Do not edit frozen parent trees.

See [audit](AUDIT.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md) and
[work note](../../../../notes/2026-10-18-own-runtime-packet58ag.md).
