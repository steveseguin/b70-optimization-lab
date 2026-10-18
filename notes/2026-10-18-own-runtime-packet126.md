# Packet126: earlier guessed-token draft, CPU dependency audit

Scope: the owner's 2.5-hour CPU-only task. The immutable starting source is
packet124's bundle8 BASE: bundle7's native runtime with the host drain repair.
Target arithmetic is `iq3-p49-split32-v1`; the draft remains on rank1 with
packet114's fixed 80,128-row prefix and packet105b's target head split.

`git pull --rebase` refused the unrelated dirty orchestration files. After
`git fetch origin`, HEAD and origin/main both were
`8b7394cfb106db3585b54f3766af1da99c4ac9b7`. Those edits remain untouched.
The host is steve-b70s; initial root free space was 35.12 GB, above this task's
25 GB floor. No GPU, service, sudo, power/memory/swap/cache change or reboot is
authorized here. CPU programs use nice19, CPUs8–15/24–31, Python `-B`, closed
stdin and at most8 GiB; no runtime program inherits a resource cap.

The first milestone preserves the accounting method and current source and
trace inputs. Packet108's extractor and packet85's position-join helper are
copied without editing. Only their accounting function ASTs will execute;
their old module-level resource-cap statements will not execute on import.
Both complete packet118 composite candidate summaries are the timing inputs.

Initial source finding: rank0 finishes its speculative half before servicing
the target suffix; rank1 cannot return its verified token until that service
finishes. The suffix service is absent from `rank_trace`, while rank1's wait
for it is inside the target command. Earlier draft execution can only save
rank1 compute-engine time if it fills a real dependency wait; moving serial
draft and head work alone does not remove either cost. Misses must restore
the draft's private mutable state before recomputing with the verified token.
The result and admission decision are recorded below.

[Packet analysis](../experiments/own-xpu-runtime/stage2/packet126-early-draft/README.md).

## Decision

The first milestone was committed as `ce4ec0f45` and pushed immediately.
The finished simulation reproduces all 2,376 recorded intervals. Both lanes
contain 932 hits and 256 misses. Moving the draft without recovering any head
wait leaves hits essentially unchanged and adds about 1.6 ms to misses. That
scenario is **1.9517% slower on A and 1.9622% slower on B**.

The idea needs about **0.43 ms of recoverable head wait per interval** to
clear the requested 0.5% gain, before draft-state backup/restore costs.
The saved traces do not measure that wait. Two different head schedules fit
the same saved command times and give opposite answers. The result is
**inconclusive**, not a proved loss or a proved sub-0.5% lever. I did not admit
a runtime build on an assumed gain.

Both current/proposed hit/miss graphs, finite-window draft boundary, head
partition and prefix distinctions, startup/terminal state hazards, and missing
timing fields are recorded. All 141 existing negative indexes were scanned;
packets79,106/106b,36,71c and123 are addressed explicitly. Packet106b's combined
draft split is slower than its control and head-only view; this proposal does
not repeat its row-placement mechanism.

Eight analysis tests pass. Method copies match their originals; both input
archives verify and the analysis reproduces deterministically. The parent
packet124 drain scan passes. These are not model byte or controller/startup
gates. No runtime was built, no smoke ran, and no v4/v5 proposal was created.
No GPU, service, compiler, sudo, frozen tree, live queue or host setting changed.
Next prerequisite: separately timed head readiness/service/merge work, as
specified in the [closeout](../experiments/own-xpu-runtime/stage2/packet126-early-draft/ANALYSIS-CLOSEOUT.md).
