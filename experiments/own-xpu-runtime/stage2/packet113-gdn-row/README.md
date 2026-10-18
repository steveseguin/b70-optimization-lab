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
