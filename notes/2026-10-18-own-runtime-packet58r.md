# Packet58r: one-card kernel bracket in one load

CPU-only work on main, started October 18 at 12:33 UTC. Pull refused the
unrelated dirty orchestration files. Fetch confirmed HEAD and origin/main at
`2155a0dc90ecaed5d13e8662cfa11576b18bf29b`; ongoing coordinator commits continued
on the shared main. Those files, every existing packet/screen/ops tree and
live queues were left alone.

The new [packet](../experiments/own-xpu-runtime/stage2/packet58r-onecard-v5/README.md)
uses packet58n/58p's tile16-only control and the same packet58j kernel objects.
It copies packet98c's quiescent native switch into the single-owner entry.
Route-fast, rec-both-plus and their combination are selectable. Packet109's
other-fusion kernels/dispatch are absent in this engine, so fusion is explicitly
unavailable and rejected; no unfused placeholder is timed as fused.

After two small K1 fixtures there is one model load, followed by A/B/A/B/A,
twelve prompts at 128 tokens in each view. The proposed B changes route and
recurrence together. Native selection hashes, allocation descriptors and pinned
expert handles remain fixed across recapture. Every request resets its state;
each token is checked against packet49 before generation may continue. Python
independently checks all tokens and all five views after the native drain.
Immutable expert-cache contents may change through ordinary fills/evictions;
the boundary records that traffic separately from zero uploads during switching.
No prompt/KV/response cache reuse is allowed.

Both compilers' byte checks pass against the actual one-card controls, including
rows4-shared recurrence. The inherited NaN payload difference between GNU and
Intel is confined to the existing seeded-NaN cases; each candidate matches its
own unchanged compiler reference byte for byte. Full-size mock binding covers
both miss paths and every selection, including all four views on one allocation
set. Miniature A/B/A/B/A runs compare all retained layer bytes to a fresh
control twice per candidate. A deliberately wrong oracle fails in A0 before B0.
These are CPU proofs, not full-model device equality.

The new wrapper retains whole-host memory admission: 118,308,908,048 bytes
available, including an 8 GiB reserve. Device/backing allowance remains
26,409,219,600 bytes; experts stay pinned at 48,627,712,000 bytes and cache at
18,000,000,000 bytes. Full BF16 KV and target-only decode remain unchanged.
The drain fix is copied. The common teardown helper is adapted to the one-card
owner and tested with real temporary coordination files: a reporting failure
can release only a proven clean, reaped owner and remains an experiment failure.
The generic known-template scanner says NOT_VERIFIED; local integration tests
cover the new wiring rather than claiming a template match.

Preparation corrections were confined to this new copy: the full-size mock's
no-op copy needed a synthetic zero error-readback word; copied tests needed
their original small post-load progress fixture; argument-policy tests need
unlimited virtual address space to exercise the real native-launch cap refusal.
No device fault occurred. CPU-only cap installation stays in CLI processes.

The coordinator proposal is card 0, lane A, with lane B paused and drained for
the entire whole-host gap. Estimate 20–30 minutes including K1 and gaps; the
native/model watchdog is 7,200 seconds, at least 4× the upper estimate.
Both B repeats must beat every A by 0.5%, with control drift no more than 3%.
This is a screen: independent fresh-load repeats, full-chain quality and the
strict 512-token final gate remain pending. No record or public package changes.

Implementation milestone `c557854ee` was pushed immediately. Read-only review
then closed these gaps in the new copy: pin the oracle completion chain;
prove reused GNU/Intel objects by reproducing the frozen parent binaries;
bind each view at both contexts; prove clean teardown before report hashing;
seal the fault-pattern source and install it in each fresh window; enforce
the 25 GB runtime disk floor again after drain waits. Both parent relinks
reproduce exactly. All 79 Python tests, 12 argument paths, 6 native parser
paths with 24 negative cases, 8 full-size binding checks and 6 miniature
reset brackets pass. Final sealing and temporary queue planning follow the
last Intel link, which respects the shared compiler/whole-host guard.

No GPU job, service, sudo, power/memory/swap/page-cache setting, reboot, kill,
live queue edit or external submission was performed. CPU work uses nice19,
cores 8–15/24–31, Python -B and closed stdin. Root stays above the 25 GB stop
floor and the new build below 200 MB.
