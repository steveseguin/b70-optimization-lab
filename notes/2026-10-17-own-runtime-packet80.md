# Packet80 combined bundle — October 17

The new packet composes packet75's chain with packet76 ordered host cleanup,
packet78 route/norm kernels and packet79 rank0 draft placement. Existing packet,
screen and ops trees are frozen. Work is CPU-only; no services, GPU execution,
host settings, sudo or reboot. The requested note is the sole file outside the
two new folders edited for this task; CURRENT.md stays untouched under that
scope restriction.

Initial git pull --rebase refused because active packet70/75 report files were
dirty. Fetch showed HEAD and origin/main identical (0/0), so nothing was stashed
or overwritten. Other active work is preserved. Root had22GB free. Builds run
nice19, affinity8-15,24-31, closed stdin, an8GiB address-space cap and serial
compilation. No model payload is read by full-shape mocks.

Milestone1: GNU host and Intel SYCL builds pass. Packet80 has16 independent
host/route/norm/HC configurations and four placements; experts=wide64 and
dense=production. Ordered retirement remains rank1-only. Rank0's draft uses
exactly91,392 expanded Q6 head rows. Target arithmetic and packet49 oracle are
unchanged. Exact operator checks, full-shape post-load memory census, native
reverse-handoff and selection-consumer checks are in progress. This is not yet
a ready chain or a speed claim.

Sources: [bundle](../experiments/own-xpu-runtime/stage2/packet80-record-bundle/README.md),
[preparation](../experiments/own-xpu-runtime/ops/packet80-orchestration/README.md).
The helper will select only each packet's own both-lane confirmed exact winner;
missing evidence leaves its choices at production. It prints a chain command,
never launches it. Submission notes disclose all choices and enforce2000 chars.
