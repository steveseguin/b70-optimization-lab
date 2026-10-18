# Packet134 — rank-0 submission-stall attribution, October 18

The reported gaps do not justify command replay. Almost all of the observed
compute gap is before the target kernels start, while the host prepares the
token. On misses, correction repeats that preparation. The enqueue loop stays
ahead of the GPU in this trace.

The separate gap between host commands mostly covers waiting for rank1's draft
command and servicing the target-head suffix. The short explicit draft-publication
wait had hidden the earlier pending-command wait in the high-level reading.

The [packet and source audit](../experiments/own-xpu-runtime/stage2/packet134-submission-stalls/README.md)
and [numeric report](../experiments/own-xpu-runtime/stage2/packet134-submission-stalls/ATTRIBUTION.md)
retain the exact distinction. Hit means: 1.594 ms before the speculative
sequence, 0.085 ms inside it; 1.276 ms of the host command gap overlaps rank1's
draft command. Misses add 2.046 ms before correction. Current halves submit
564 kernels. All 84 sampled cycles were used, and the original budget rows
reproduce exactly to the declared tolerance.

Packet128b failed its timing-overhead gate at 51.475 tok/s. These are diagnostic
observations, not normal-run critical-path estimates or predicted gains. No
optimization is adopted and the record is unchanged. Packet34's old replay
test was also neutral; prepared argument blocks and pure-spin waits already
exist in the current source.

Milestone 1, committed and pushed as `bcfe38026`: added the CPU-only analyzer,
70 pinned inputs, per-cycle report and source explanation.

Milestone 2: all 16 adversarial clock/continuity/identity tests pass. The full
report reproduces; a falsely passed overhead gate, altered source/symlink and
missing correction receipt are rejected. The retained validation used 73,624
KiB peak RSS, left 39.115 GB free on root, and created no build. The
[analysis seal](../experiments/own-xpu-runtime/stage2/packet134-submission-stalls/evidence/analysis-seal.json)
binds the artifacts without granting device admission. All 182 packet124c
symlinks are unchanged. The [closeout](../experiments/own-xpu-runtime/stage2/packet134-submission-stalls/CLOSEOUT.md)
and negative-result index record the decision and concrete reopening condition.
No runtime build or device proposal is justified under the brief's conditional branch.

`git pull --rebase` refused unrelated dirty work. `git fetch origin` confirmed
HEAD and origin/main matched at entry (`34e2603b0b2c5879e59867c8e57543cd29c75b49`).
Another worker advanced main during analysis; no existing edits were staged.
All work runs nice19 on CPUs 8–15/24–31, Python `-B`, stdin `/dev/null`, with
an 8 GiB cap installed only by CPU entrypoints. Root remained about 37 GB free;
no build was made. No GPU, service, sudo, live queue, frozen tree, or host setting
was changed. Commits use explicit paths and are pushed immediately.
