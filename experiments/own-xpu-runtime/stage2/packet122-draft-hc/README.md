# Packet122 exact draft HC schedule

CPU preparation from packet118 bundle7. The only runtime selector is
`choices.draft_hc_schedule=production|p122`. The candidate keeps each BF16
weight and input, p59's eight-lane chain/reduction, gate BF16 store, sigmoid,
product, ordered four-stream sum and final BF16 store. It assigns a column's
four streams to one subgroup, distributes the independent sigmoid products,
and removes the shared-memory barrier. The original exceptional-value serial
expression is retained. Packet117's target HC work supplied that fallback
lesson; this is a different BF16 draft layout and subgroup mapping.

GNU and Intel pass all 16 cases twice, including NaN/Inf, signed zero and
subnormal values. Both compilers produce the same 409,600 checked bytes.
These are CPU checks, not device or model-speed claims.

The fresh budget is in [the separate immutable probe](../packet122-draft-budget/README.md).
[Lever ranking](../packet122-draft-budget/LEVER-RANKING.md) and
[47-class byte model](../packet122-draft-budget/ROOFLINE.md) retain the rationale.
The candidate micro replays that complete draft with actual captured inputs,
alternating production/candidate order at 128 and 4096 context. It compares all
mutable bytes each pair and keeps ten warmups plus forty measured pairs at
each context. Each changed HC gate and their sum must be <=0.8 production in
both orders, both contexts, and both fresh processes. No selected easy subset.

Coordinator proposals (never edit live queues here):
- `../../ops/lane-queue/proposed-p122-draft-hc-micro-B.txt` — two fresh micros;
- `../../ops/lane-queue/proposed-p122-v5-B.txt` — conditional one-load bracket.

The bracket cannot launch before the hash-bound two-process micro gate passes.
It rereads the native receipts and timings rather than trusting a saved boolean.
Expected micros: about 2 minutes each,1,200-second watchdog. Bracket: about 15
minutes,3,600-second watchdog. Durations are estimates, not measurements.
Physical card 2 is the isolated micro device; v5 uses the normal B rank pair.

CPU preparation, each from this directory with
`nice -n19 taskset -c8-15,24-31 python3 -B` and stdin `/dev/null`:
`build_cpu.py`, `build_budget.py`, `test_micro_gate.py`, `queue_plan_budget.py`;
then the v5 steps in its README. Build caps are only in CPU entry processes;
the device wrappers check unlimited, unchanged resource limits before exec.
The shared drain sleep is clamped. Frozen parents are read-only.

[Source provenance](source-copy-provenance.json), [focused runtime delta](runtime-delta.patch),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [retention](RETENTION.md).
