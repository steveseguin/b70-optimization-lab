# Packet148: sharing a two-card miss correction

The study closes without a design brief. None of the examined graphs has
enough supported saving and enough memory to pass the requested 2% gate.
The 58.798 two-card record stays unchanged.

The saved record needs 1.574 ms removed from each miss. Splitting output rows
across the cards gives about 1.04% in the favorable model that prices transfers
by payload size, or 1.32% if every message is charged as only 5 KB. Moving
whole attention heads reaches 1.91% only after granting free state sharing.
Actual state transfers would cost more. One whole boundary layer needs
1.129 GB including its state and scratch; rank1's arena has only 0.786 GB left.
Computing the next token's first half earlier has no direct benefit when the
other branch stays fixed. Any extra benefit through the output-head wait is
unmeasured; even granting the old diagnostic wait for free gives only 1.86%.

The analysis distinguishes these new graphs from packet144's existing
miss-path mechanisms and records separate reasons to reopen each one. A new
proposal needs evidence that it shortens the current correction by at least
1.574 ms after transfers and fits all weights, state and scratch. No runtime
copy, build, device proposal or readiness marker was made.

Started at about 21:58 UTC on steve-b70s, with a 75-minute limit. The initial
pull refused unrelated dirty orchestration files. Fetch confirmed main and
origin/main both at `9cc135c735a774e54a11bad557097125a859387c`.
All analysis ran at nice19 on CPUs 8–15/24–31, Python -B, closed stdin,
with a 4 GiB process address-space cap. Peak RSS was about 148 MiB.
There were no model payload reads, GPU launches, services, sudo or settings
changes. Existing packet trees, screen code, ops and live queues were untouched.
No live host state changed, so CURRENT.md was left unchanged.

The calculator checks all source hashes, the saved record's twelve successful
cache-zero requests, 1,188 interval identities, the exact class-balanced rate,
transfer counts, memory numbers and the reproduced analysis. Its source input
archive is about 1.73 MB intentionally: the old transfer logs and full run
summaries need to remain reviewable after cleanup. The large existing record
archive is referenced by hash rather than copied. Packet128b's already-dirty
budget was captured as observed diagnostic evidence and was not edited or
committed by this task.

Final review at about 22:14 UTC: all 75 captured inputs still matched their
source hashes, all 27 local Markdown links resolved, and the replay and diff
checks passed. Repository hygiene reported zero errors; its one large-file
warning is addressed by the archive's retention and restoration instructions.
A pre-commit fetch found shared main and origin/main both at
`b32810fa30153391b44cb2e6db3e7fd4377e8b6b`. Only the six new packet files and
this note belong to this commit; unrelated ongoing edits remain with their
owners.

[Full analysis](../experiments/own-xpu-runtime/stage2/packet148-correction-graph/ANALYSIS.md),
[calculator and saved values](../experiments/own-xpu-runtime/stage2/packet148-correction-graph/analysis.json),
[do-not-repeat entries](../experiments/own-xpu-runtime/stage2/packet148-correction-graph/DO-NOT-REPEAT.md),
[closeout](../experiments/own-xpu-runtime/stage2/packet148-correction-graph/CLOSEOUT.md).
