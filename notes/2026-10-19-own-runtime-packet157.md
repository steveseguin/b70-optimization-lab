# Packet157: where rank 1 spends its draft time

The packet is being prepared on CPU only, on steve-b70s, for a two-card run.
The starting HEAD matched origin/main after fetch; pull refused unrelated edits.
All existing packets and operations files are frozen, except the four new
proposal filenames. No device, service, model payload or full-shape read is
part of this preparation.

Packet154 measured draft_issue at 1.571 ms/cycle and rank0 reply wait at 1.573.
That is the reason for decomposing the draft, not evidence for a particular
kernel optimization. Packet157 keeps bundle8 and the 80,128-row head prefix.
It vendors the packet136 source closure and packet154 harness, disables the
latter's duplicate work, and tags existing events outside capture. See the
packet README and v5/analyze.py for clocks, group boundaries and refusal rules.

Milestone 1: instrumentation and analyzer implemented. Five analyzer tests
cover conservation, top-two ranking, paired overhead, missing/empty/incomplete
streams, unmatched/duplicate/overlapping events and control contamination.
Native builds and the full preparation/entry/queue seal are still being checked.
No measured top-two ranking, output equality or overhead is claimed yet.
