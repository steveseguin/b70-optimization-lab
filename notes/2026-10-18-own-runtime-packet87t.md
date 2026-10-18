# Packet87t — price the head-split transport

CPU preparation only. The small two-process microbenchmark compiles (about
2.6 MB build), and the single lane-B proposal passes planning in a temporary
queue. No GPU, model, service, sudo, host setting or live queue was touched.

[Packet and sources](../experiments/own-xpu-runtime/stage2/packet87t-transfer-micro/)
and [proposed job](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p87t-micro-B.txt).
The proposal is shipped immediately after compilation and plan validation;
remaining CPU report/guard tests follow in a focused commit.

The coordinator job uses cards 2 and 3, v4 lane reservation, fault review,
memory admission before the lease, passive process/device checks, and the
shared drain permit. Each rank opens only its assigned card. It measures the
5120-byte hidden vector, 8/16-byte return, and 20480-byte pipeline stream
handoff using copies of packet97's owner/queue/wait/mailbox primitives.
Each idle/compute case gets 200 repetitions, alternating order, after ten
discarded tiny-buffer initialization repetitions. No model prompts are used.

Device receipts and measured-cost gains are pending. The report will evaluate
packet87's original equations, retain the corrected measured control baseline,
and use +0.5% as the design threshold. No zero-cost transfer is called measured.
The pipeline stream and mailbox calibration do not include full target work;
the separate 4-byte token upload is outside that calibration.

`git pull --rebase` was attempted first and refused because other work was
dirty. A fetch showed no incoming main commits. Existing dirty work and frozen
packet trees are preserved. The new build uses packet94's unchanged serial
compiler turn, nice19, cores 8–15/24–31, Python -B and closed stdin.

CPU closeout: the first proposal was pushed in `11a13504c`, immediately after
its compile and temporary queue plan. The final build includes the pipeline's
separate queued 4-byte token upload, host-vector/shared staging and observed
compute-pending flags. Its native and CPU scratch total about 4.5 MB, below the
200 MB cap. The copied source files remain byte-identical to their parents.

All **19 CPU tests pass**, including receipt mutation refusals, both modeled
decision branches, the memory floor and memory admission before reservation.
The actual micro control flow also passes **1,800 samples in two CPU processes**
with a host-backed device substitute, poisoned destinations, token/stream checks
and graceful drain. Those CPU timings are discarded. Both original packet87
optima reproduce exactly, and the final proposal passes a fresh temporary plan.
[Validation receipt](../experiments/own-xpu-runtime/stage2/packet87t-transfer-micro/evidence/cpu-validation.json).

The model uses measured idle transfer costs when receipts arrive: A/B/D already
charge compute. Busy-queue totals are retained as contention sensitivities;
charging that outstanding synthetic compute again would falsely close a split.
The copied queues are in-order, so a transfer cannot bypass its own card's
compute. The job records pending-compute observations instead of asserting
unproved overlap. Median and p90 remain pending until the coordinator runs it.

The earlier note's token omission describes the first shipped build. The final
calibration includes the token upload; full model acceptance/state checks remain
outside this tiny transport diagnostic. No GPU, service, live queue, frozen
packet, settings or pre-existing dirty file was changed by this preparation.

Git provenance: `944963d2c` contains the final packet87t validation, but another
agent staged 128 additional packet102/related paths between the scoped staged
review and commit. The shared-index commit therefore also captured that work.
This task did not edit those files. The commit was already pushed; no published
history was rewritten and no other agent's files were reverted. The follow-up
provenance commit is restricted with `git commit --only` to this task note.
