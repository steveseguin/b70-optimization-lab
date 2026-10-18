# Packet92: rank-1 reply before host reporting

## Attribution milestone

The next draft waits for rank1 accept, so sending a half reply before doing the
same bookkeeping is insufficient. The candidate will retain result waits,
ordered retirement, profiling safety checks and resource snapshots, then move
receipt formatting/output after the next asynchronous draft submission. All
remaining fields will be frozen at the half boundary. Errors in deferred work
must refuse the next half. [Ordered source audit](../experiments/own-xpu-runtime/stage2/packet92-rank1-reply-first/ATTRIBUTION.md).

`git pull --rebase` refused unrelated unstaged running-chain work. Fetch showed
HEAD and origin/main equal; no stash, reset or frozen-tree mutation was used.
Host is steve-b70s; root initially had 19 GB free. No compiler was active.
CPU only, low priority, cores 8-15,24-31, 8 GiB process limit and serial compiles.
No GPU, service, sudo or host setting change. Device savings remain unknown.

## Candidate and gates complete

The new candidate carries one report past accept, submits the next draft, then
finishes reporting before another half. All target kernels, operations, result
copies, completion checks, ordered retirement and profiling guards stay in place.
Resource snapshots and mutable counters are frozen at the original boundary.
The new host timer row measures result-ready-to-reply and the reporting bucket
with two clock reads each, in both views. A failed deferred report aborts the
mailbox and poisons the next-command gate.

GNU and Intel each pass two mock state/token runs and nine negative cases.
Four complete GNU miniature runs match packet84 tokens, 96 layer files,
proposals and final draft state, preserving every original half receipt field.
Four full-size startup mocks pass, including post-load banks, prepared commands,
snapshots and draft construction. Two bad extents and two bad host selections
refuse. Both views capture identical operations and device allocation totals.
All four memory checks and 87 Python checks pass. [CPU closeout and receipts](../experiments/own-xpu-runtime/stage2/packet92-rank1-reply-first/CPU-PREPARATION-CLOSEOUT.md).

Both views are sealed to the unchanged shared v4 wrapper. Both A-grid/B-confirm
and B-grid/A-confirm proposals pass planning in a temporary queue directory.
No live queue, existing packet, screen tree, service or GPU was changed.
The build is 138,053,853 logical bytes; root remained above 17.5 GiB free.
Fixture scratch is removed; compact raw evidence and generated startup code
remain. The coordinator's device screens, actual savings and full-chain
qualification remain pending. [Handoff and proposed files](../experiments/own-xpu-runtime/stage2/packet92-rank1-reply-first/WINDOW.md).
