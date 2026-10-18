# Packet58h: one-card MTP does not clear feasibility

October 18 UTC / October 17 Toronto, 2026; CPU only on the four-card host.

**Decision: do not build this arm.** The existing evidence predicts about
24.62 tokens per second, below the required 28.8. The most generous device-only
calculation reaches 28.86 but leaves just 0.12 ms per cycle for omitted work;
the existing rejection-weighted restore cost alone removes that margin.

Both draft placements fit the device accounting. Sharing the target head adds
zero weight bytes. The draft's own expert weights still add 3.146 GB, whether
on the card or in the pinned host pool. Keeping the existing allowances and
8 GiB reserve requires about 121.65 GB of available host RAM, 1.12 GB more than
the WS128x admission snapshot and 0.73 GB more than the best saved snapshot.
This is a budget failure for this design, not a claim that one-card MTP can
never fit or become faster.

The saved 58g receipts specify zero-copy misses with later cache fills. Its
24.0128 tok/s WS128x number is diagnostic timing from an exactness window;
this analysis does not promote it or replace it with the running WS128 result.

A passive check found blocks 53–56 offline and block 57 online. Only four 2 GiB
blocks were offline, differing from the brief's stated 10 GiB exclusion. No
memory setting was changed, and that difference is not counted as permission
to use more RAM.

[Full analysis and byte tables](../experiments/own-xpu-runtime/stage2/packet58h-onecard-mtp/FEASIBILITY.md),
[recomputed JSON](../experiments/own-xpu-runtime/stage2/packet58h-onecard-mtp/feasibility.json),
[reproduction command](../experiments/own-xpu-runtime/stage2/packet58h-onecard-mtp/README.md),
[closeout](../experiments/own-xpu-runtime/stage2/packet58h-onecard-mtp/CLOSEOUT.md),
[DO-NOT-REPEAT](../experiments/own-xpu-runtime/stage2/packet58h-onecard-mtp/DO-NOT-REPEAT.md).

The CPU analyzer recomputes the result from retained, hash-checked compressed
inputs. The original input files and frozen source hashes also match. A
separate read-only review checked the memory and timing arithmetic. Peak RSS
was about 35 MB; the complete packet is under 1 MB and no fixture scratch or
compile was needed. Root free space remained above 12 GiB. No GPU, model
payload, service, sudo, signal, reboot, power/memory/swap/page-cache change,
live queue edit, publication or submission occurred. Existing packet trees,
screen tooling and ops were not edited. The conditional build, seals and
coordinator launch are not produced after a failed feasibility gate.

The initial `git pull --rebase` refused unrelated live edits. A fetch confirmed
HEAD equaled origin/main, so no stash, branch, worktree or rebase was needed.
Only this packet, this note and the new CURRENT entry belong to the commit.
The next prerequisite for this arm is a faster complete M2 verification path
and a host budget with demonstrated margin; repeating this composition is
closed. Feasibility completed within the 45-minute limit.
