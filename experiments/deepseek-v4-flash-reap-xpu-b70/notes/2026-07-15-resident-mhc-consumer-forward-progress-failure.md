# Resident TP4 MHC consumer forward-progress failure

Date: **2026-07-15**

## Outcome

The marker prerequisite passed, but the dependent resident consumer is closed
before model integration. The marker address and epoch arithmetic are correct;
the current Xe/Level Zero scheduler does not provide the cross-queue forward
progress this polling protocol requires.

oneCCL commit `1e00a13` contains the default-off experiment. It submits a
single 256-thread MHC consumer on an auxiliary in-order queue before the
unchanged marker ring. Sixteen subgroups cover the nine active wires across
all four final-writeback stages, perform canonical MHC post, converge, and run
the previously exact MHC pre implementation. XPU-kernel commit `eac8ed6` adds
a non-graph mode to the existing changed-input probe.
The rebuilt normal-priority library SHA-256 is
`e341f098527532d091cd67652a62c68840f0815d6415ab205636b366facdd99c`.

## Exact failure

On every rank and all seven changing iterations, the consumer expected epoch
`N` and initially observed `N-2`. The marker did not advance during a bounded
poll. With a normal-priority auxiliary queue, the candidate took
`294-314 ms` per boundary versus `225-307 us` for the reference. The four
outputs were exact only after the timeout released the polling workgroup and
allowed the ring to run. Exact values after a forced timeout do not validate
the intended overlap protocol.

Giving the resident queue SYCL `priority_low` did not rescue preemption. No
rank made progress for more than 30 seconds after communicator initialization,
and the probe was terminated. The normal-priority source is preserved because
its bounded failure is diagnosable; the low-priority variant is recorded here
and not retained.

## Why the earlier upper bound did not transfer

The earlier MHC-first screen hid `0.612-0.642 ms` using finite independent
kernels. Those kernels retire, so Level Zero can eventually schedule both
queues. A persistent consumer is different: it cannot retire until the second
queue's ring publishes readiness. The scheduler runs the polling workgroup
without guaranteeing the ring queue an execution slot, creating a device-side
forward-progress cycle.

This rejects the resident-polling architecture, not the marker mechanism. The
markers remain a cheap and exact diagnostic primitive at `0.446 us/boundary`.
Do not run a full model or graph replay with the resident hook.

## Next implication

The remaining fusion experiment should avoid cross-queue polling entirely.
The prior in-ring MHC post/pre candidate used a 1024-thread workgroup even
though the 8 KiB ring has only nine active LL256 wires and MHC pre uses 256
threads. Screen a compact 256-thread fused ring/post/pre kernel at the exact
single-boundary gate. It must be exact and save at least `6 us/boundary` before
any server load.

Structured evidence is in
[`../data/tp4-resident-mhc-consumer-20260715.json`](../data/tp4-resident-mhc-consumer-20260715.json).
