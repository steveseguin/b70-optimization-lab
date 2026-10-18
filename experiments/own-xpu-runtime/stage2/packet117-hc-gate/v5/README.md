# Packet117 conditional one-load HC bracket

This private runtime copy starts from packet111 after the 111r decision
(`9b49c03e7`). The split target head and other fusion stay enabled. Only the
selected HC gate implementation changes: `hc_gate=production|p117`. Production
means packet111's existing `wide` implementation. Both values retain the same
wide mixture geometry, low/norm stages, weights, allocation sizes and draft.
The candidate schedules independent sigmoid products on two lanes of each existing subgroup
then adds products in the original stream order. Any nonfinite product uses
the original scalar mixture expression, preserving its NaN payload decisions.

The five views are production, candidate, production, candidate, production,
with one loaded rank pair. Each switch drains, restores all mutable state and
checks that allocation identities and immutable weights stay fixed. Each
request starts after reset, checks every token against the retained oracle and
must report no cached tokens. Acceptance remains separate per prompt and arm.
The device bracket is diagnostic and cannot publish a record.

The coordinator may queue the proposal only after the two fresh-process
micro gate passes byte identity and the 0.70 production-time limit for both
HC classes, both layers and both orders. `bracket_job.py` rereads that gate
and the CPU seal before admitting any device work. A pending `--plan` is
explicitly ineligible to launch. Expected duration is 15 minutes; the watchdog
is 60 minutes.

CPU preparation builds GNU-host and Intel device binaries without opening a
device. Selected-view full-shape startup/switch checks preserve the real parser,
allocations and captures while mocking payload storage. Separate miniature
reset and IPC checks prove transport/state behavior; they are not operator
arithmetic evidence. The seal also binds the independent GNU/Intel byte gate,
source closure, native binary and inherited-limit pre-exec guard. Native
launches refuse finite address-space limits and any limit change after import.

Run CPU scripts with `nice -n 19 taskset -c 8-15,24-31 python3 -B` and stdin
from `/dev/null`. CPU caps are installed only by CLI processes. Compilation
uses packet94's serial lock. Frozen parent packets and live queues are unchanged.
