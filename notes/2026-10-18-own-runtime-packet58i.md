# Packet58i: what slows the one-card run

The saved run spends about 7.83 milliseconds per token maintaining its expert
cache and copies 65.46 MB of expert weights. About 93% of selected experts are
already cached. The timer includes host bookkeeping and waits, so it cannot
all be counted as transfer time that another engine could hide. The receipts
do not contain separate device times or enough route detail to recover every
layer's hit rate.

No new runtime is justified by this packet. Hiding the estimated copy service
predicts 26.11 tokens per second, below the required 26.774. A larger cache
predicts about 25.9 and still needs proof that its memory fits the original
host budget. Copying after the router might do better, but its missing wait
and overlap measurements decide the outcome. The next useful evidence is a
short, separately admitted one-card trace of those stages, with route IDs.
Nothing was built or queued.

[Attribution, estimates and reproduction](../experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/ATTRIBUTION.md),
[JSON](../experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/ATTRIBUTION.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/CLOSEOUT.md).

The work was CPU-only on low-priority allowed cores. Existing evidence and
trees stayed frozen; this note is the explicit requested exception to the new
folder boundary. No GPU, service, sudo, host setting, memory block, fence or
reboot action occurred. The initial `git pull --rebase` refused the existing
dirty tree; fetching confirmed HEAD and origin/main were identical, so no
other work was stashed or changed.
