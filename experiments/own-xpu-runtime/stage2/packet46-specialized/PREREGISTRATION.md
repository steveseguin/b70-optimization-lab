# Packet46 bounded layer comparison

Registered before compilation or device execution, October 17, 2026.
Parent: packet45-merged3's current selected kernels and arithmetic-v2 oracles.
Source hashes in the completed build receipt freeze that current parent; the
packet45 directory, its binaries, seals and evidence are read-only inputs.

## Question and go/no-go bar

Can static, shape/format-specialized ordinary-GDN and QSA compositions save
**at least 80 microseconds per complete layer** while retaining every current
intermediate and state byte? Baseline launch census: ordinary GDN 35, QSA 41.
Fewer launches are a mechanism check, not a speed result. Descriptor-interpreting
fused device kernels are excluded because the earlier packets measured them
50–100 times slower. No approximate activation, reduction reassociation,
compressed cache or oracle change is allowed.

One B70, **physical card 0 only**, batch M=1, unchanged mixed weight formats,
full BF16 state and KV. QSA timing uses a 4096-position populated prefix,
including the newly appended decode position (position index 4095). This is
not merely 4096 allocated empty slots. GDN has the same fixed decode position
metadata and its complete recurrent history/state. The deterministic synthetic
packed fixture generator is the existing lab mechanism. It is a kernel/layer
microbenchmark, never a model throughput or final-quality headline.

## Exactness windows E1 and E2

Run two fresh native processes with the same sealed binary and fixture seed.
Each current/candidate pair starts from identical saved bytes. Change input
values and route choices across cases; retained records must demonstrate changed
expert **sets**, not just slot permutation. Include active, inactive,
pre-existing sticky-error and finite/special-value cases where the inherited
oracle contract admits them. Exercise QSA position/cache boundaries as well as
the full 4K prefix. A failed case stops the window; there is no automatic retry.

Compare all original outputs, including intermediates hidden by producer
fusion, statuses, residual streams, scratch that the current plan observes,
GDN recurrent/conv history and QSA KV/index state. Use raw byte equality, never
a float tolerance. Retain byte counts and output identities, plus enough input
and first-mismatch metadata to reproduce a failure. An unchanged final layer
output alone cannot pass. Both fresh processes must produce the same complete
output/state identity for the identical case sequence.

CPU tests use the earlier packets' host arithmetic/mocks at bounded geometry.
They test composition/capture/addressing and error behavior. They do not
certify device arithmetic or device launch counts. Production metadata census
must assert the real shapes/layout strides and current baseline selection.

## Timing windows T1 and T2

Timing is admitted only after E1 and E2 pass under the same seal, binary,
device, boot and environment. Use two additional fresh native owners, 10
warmup pairs and 200 measured current/candidate pairs per layer. Alternate
which arm runs first by iteration. Restore state and change inputs outside
timing. Compilation, fixture generation/upload, state copies, route readback
and comparison are outside the timed region.

Use the existing own-runtime method: completed SYCL event `command_start` and
`command_end`, per original/fused class, summed once over the complete layer's
compute events. Keep individual events and launch count. Include every finish,
status and state-update kernel in the layer sum. Do not count an enclosing event
as additional work, use wall time as GPU time, or compare different cards'
timestamp epochs. Record host elapsed time only as a separate diagnostic.

For each fresh owner and layer, calculate the median of paired
`current_gpu_us - specialized_gpu_us`, also retaining each arm's median,
p10/p90, and per-class totals. Both owners must save at least 80 microseconds
for that layer. A slower class remains visible; no selected easy cases or
single lucky owner can establish a win. If only one layer passes, only that
layer may become a later integration candidate. Passing this screen still
requires complete engine oracle/state and cold-suite qualification before
integration or any model-speed claim.

## Ownership, storage and stop policy

Only the coordinator may launch device windows, from an owned systemd user
unit using the command files in the runbook. CPU preparation never performs
device discovery, health probing, model loading or native execution. Existing
host fault/ownership policy still applies; the coordinator records any prior
fault review and supplies the installed runtime library path.

All launches are single-attempt. A new fault, unavailable journal, failed
comparison, invalid event, memory/storage threshold or owner stop invalidates
the attempt. Save evidence first, request cooperative stop once, and retain a
busy child for the coordinator after the drain budget. No group kill, reset,
reboot, server restart or automatic retry. Native receipt must prove safe
teardown; abnormal exit can never pass through a previously written receipt.

Builds and sustained CPU tests are time-gated at 02:55 UTC, nice 19 and cores
4–15,20–31. Serialize packet46 CPU work and use at most two compiler jobs.
Keep only new packet46 lean build artifacts; never delete or modify historical
builds, evidence or `git-archives` to make room. Reserve at least 8 GB free on
the output filesystem. CPU expert measurements use no payload beyond fixtures
and report processed packed bytes, not an inferred hardware-memory bandwidth.
