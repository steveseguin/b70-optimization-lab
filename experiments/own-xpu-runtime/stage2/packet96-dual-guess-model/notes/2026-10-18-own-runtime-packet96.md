# Packet 96: a second guess does not pay for itself

The CPU model says to keep one guess. Choosing when to try two guesses from
the draft's own uncertainty does not reach the required 1.5% gain. Even the
favorable cost case chooses to leave the second guess off when fitted on half
the prompts. That choice stays at the supplied 55.69 tok/s reference on the
held-out prompts. These are predictions, not measured speeds.

The source has 256 unique positions, not 512. Its second choice would rescue
28 of 58 misses, but finding those positions from the draft's logits means
paying for too many unsuccessful second guesses. The extra state fits in
memory. The extra work is the problem. Today's complete runtime also has no
guarantee for this new two-branch state path, even though earlier individual
two-row kernels preserve their arithmetic.

[Decision and all assumptions](../DECISION.md), [JSON](../DECISION.json),
[complete threshold sweep](../thresholds.json), [closeout](../CLOSEOUT.md),
[DO-NOT-REPEAT](../DO-NOT-REPEAT.md).

Only the new packet96 folder was written. This dated note lives inside that
folder to respect the brief's frozen-tree restriction. No GPU, service, build,
sudo, host setting, reboot or model-weight read was used. Python ran with
nice 19, the specified CPU affinity, `-B`, and stdin from `/dev/null`.

The opening `git pull --rebase` refused pre-existing unstaged work. Fetch
confirmed local main equaled origin/main, so no stash or rebase was needed.
Other operators' files were preserved. The packet's next action is its focused
commit and push; no candidate seal or queue job is warranted. Verification
passed: byte-identical JSON recomputation, all 210 threshold policies, input
hashes, matching placement census, delayed-cost/rescue dependency and local
document links. Each retained artifact is below 1 MiB.
