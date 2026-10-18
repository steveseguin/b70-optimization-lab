# Packet91 record bundle 3 — CPU preparation

Packet91 copies packet84's sources and starts from its chained selection,
including parallel recurrence. The running packet84 tree is untouched.
Route-fast reuses packet84's binary by hash. Rec-both-plus composes and reuses
packet82b's independently pinned existing binary, so no compilation is needed.
Both changes together are a separate matched-screen view. Packet90 has an empty
expert/HC extension slot; no unmeasured winner is admitted.

The initial `git pull --rebase` refused existing uncommitted work. Fetch showed
HEAD equal to origin/main; no other work was stashed or moved.

First CPU milestone: both binary/source identities verify, fresh complete-state
recurrence checks pass twice each under GNU and Intel, all eight real full-size
startup checks pass, and 23 new composition/submission/orchestration tests pass.
The submission collector now supplies exact lane-admission bytes to replay and
notes distinguish a rank1 shared head from a rank0 private prefix. Notes stay
under 2,000 characters. The inherited temporary-ops hashing failures are fixed
only in packet91's copy, consistent with the frozen packet84 rule.

Final CPU gates pass: 172 tests plus 12 subtests, all four seals, all eight
full-size startup checks, and all thirteen jobs planned on temporary queues.
Five selection rehearsals cover the baseline, each change, both together and
baseline restoration; each plans all eleven chain windows and both screen lanes.
Device correctness, acceptance and speed remain pending; no GPU or service ran.

Proposals (repository-relative):
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p91-A.txt`
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p91-B.txt`
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p91-B-grid.txt`

[Bundle and proof scope](../experiments/own-xpu-runtime/stage2/packet91-record-bundle/README.md).

The first milestone was committed and pushed as `7434a116d`. Final orchestration
passes its CPU dry run, chain seal, input check, storage precheck and queue plan.
`ready.json` has `preparation_passed=true`, `ready=false`, and refuses launch
until packet91's own screens finish. The packet84 baseline is restored. No
historical p78/p84s or independent p82b speed is borrowed for selection.

Both device binaries are unchanged: packet84 `8b615a0c74db57ab3ceab3cd4a56524d07bc9cf1cb78da2178a947e3918e294a`
and packet82b `3d633037c78943efa44783ef9cfab59ee18b7ae536755a807d7dd64b1592fcb5`.
There was no compilation. All copied parent source inputs still match their
recorded hashes. Total logical bytes in the new packet/helper trees, even
counting shared hard links repeatedly, are about 366 MB; root free was 19.32 GB
at final verification. Own gate and pytest scratch was removed. The coordinator
must recheck chain space after packet84 finishes.

Read-only review caught and fixed per-view external symlinks (the shared wrapper
requires paths inside each view) and repeat creation of immutable seals. Hard
links reuse the same binary bytes, and reselection verifies existing views.
Broader tests also updated inherited defaults to this packet's registered
baseline. Complete source/evidence and restore details are in the
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet91-record-bundle/CPU-PREPARATION-CLOSEOUT.md)
and [final verification](../experiments/own-xpu-runtime/stage2/packet91-record-bundle/evidence/final-verification.json).
