# Packet58aj: resident lookup copies on the full one-card composition

CPU preparation started 2026-10-19 01:17 UTC; 60-minute time box. Nothing is
queued, launched or submitted. The original packet58ah, packet58t, packet58u,
all other packet trees and live queues remain unchanged.

The question is whether complete anonymous copies of the two packed lookup
tensors keep fresh record windows at the warm decode rate. Packet58ah chain a
was exact but WS128 was 30.050 tok/s, with 3,736 major faults versus 124 in
WS128x. The cause of eviction is unproven. Packet58t was exact and warm-neutral
(-0.162%) on the older tile16 line; this is a new composition and stability
test, not a claim that packet58t improved warm throughput.

The private packet58ah copy retains the full packet58ag composition and adds
`lookups=mapped|resident`. Packet58t's resident storage implementation copies
all rows of both original packed tensors, checks source/copy SHA256, and makes
the copies read-only. It introduces no cache advice, pre-read, pinning, sparse
fallback, settings change or arithmetic change. A five-view process retains
the copies for its entire lifetime, including mapped controls. That load warms
source pages and cannot recreate the original cold-file condition.

Production accounting, every model window: 48,627,712,000 pinned expert bytes,
29,321,610,240 anonymous lookup bytes, 4,001,477,120 remaining file allowance,
565,325,824 measured process overhead, 4,294,967,296 shadow margin,
3,587,987,968 cache/metadata/staging allowance and 1,236,992 observed increment.
Total host bound is 90,400,317,440 bytes; adding the unchanged 8 GiB reserve
requires 98,990,252,032 bytes available. This extends packet58u's 95.401 GB
18 GB-cache admission with packet58ah's existing larger-cache allowance.
The 21,552,729,600-byte device cache is unchanged. Actual RssAnon is charged
in full; resident bytes replace the matching file allowance, never double-counted.
K1 keeps its separate 4 GiB bounded fixture and 12 GiB admission.

The smoke and bracket will be proposed on lane A, card 0, whole host, after
p153 and p151 complete their lane-B work. The one-load order is mapped,
resident, mapped, resident, mapped. A0 remains exact and reported as warm-up;
only A1/A2 count as warm controls. Both resident rates must be within inclusive
±0.5% of both warm controls. Exactness is required against iq3-p49-split32-v1.
The later seven-window chain freezes Codex only from WS, uses unit
`packet58-onecard-58aj-a`, and writes fresh `evidence/card0-58aj-a`.

Compilation waits behind the two-card preparation markers and then uses
`ops/compile_turn.py`. All preparation uses nice19, helper cores, Python -B,
closed stdin and a 4 GiB cap where runtime-limit interception is not required.
No model/GGUF payload is read. Source/build copies preserve links; the new
engine copy retains only its transitive headers and pinned object dependencies.
Parent provenance snapshots remain under lineage. Binary outputs are ignored
and restorable from pinned inputs plus the retained build commands.

Milestone 1: source integration and production memory arithmetic prepared.
Builds, new exactness gates, seals and final readiness remain pending.
