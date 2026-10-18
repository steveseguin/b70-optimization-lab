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
