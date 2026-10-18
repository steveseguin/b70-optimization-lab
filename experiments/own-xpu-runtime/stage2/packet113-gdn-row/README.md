# Packet113: one subgroup per independent GDN state row

CPU-only preparation. No device speed or device exactness is claimed.
[Work note](../../../../notes/2026-10-18-own-runtime-packet113.md).

This copies packet110's complete current GDN layer harness, retaining its
synthetic weights, surrounding operators, state snapshots and timing boundaries.
Only the recurrence changes. Frozen packet97 objects supply unchanged operators;
the candidate is compiled from this packet's source. Packet103 selects the same
`rec-both-plus` recurrence. No record or model runtime is integrated here.

Candidate: 6,144 one-subgroup workgroups instead of 1,536 four-subgroup groups.
Each owns a complete independent value row, with the same four-products-per-leaf
and adjacent 32-leaf tree. It duplicates normalization/gates and eliminates SLM
and workgroup barriers. This is a barrier/local-state experiment, not an assertion
that production lacks enough workgroups. No inter-token FP32 state carry.

Kill gate: both fresh lane-B processes must have recurrence time at most 0.6 of
current, at contexts 128 and 4096 and in each alternating order. All state and
output bytes must match; failures close the arm. No integration before this gate.
GNU/Intel exceptional CPU checks and complete layers precede device admission.

[Proposed B jobs](../../ops/lane-queue/proposed-p113-micro-B.txt): two fresh
processes, expected 240 seconds each, watchdog 1,200 seconds each. The native
micro checks 768 full-state recurrence cases before timing, then four serial
complete layers and 100 alternating timing pairs with complete state equality.
Only the coordinator launches devices; CPU preparation does not install a queue.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md),
[build/retention instructions](RETENTION.md), [evidence seal](seal.json).
After both device windows, `python3 -B qualification.py` recomputes the gate
from hash-bound raw transcripts and event endpoints. Missing windows are pending;
failed bytes, identity changes and incomplete data cannot qualify.
