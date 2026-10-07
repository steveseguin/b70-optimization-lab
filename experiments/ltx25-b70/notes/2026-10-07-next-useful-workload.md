# Next useful LTX workload after the narrow control

The owner requests continuous speed and reliability improvement without quality
loss. The current 256×256, 25-frame w93c lane remains an exact regression control;
its independent-clip generation rate is not a continuous-video frame rate.

First complete the current-upstream arithmetic control, then the bounded 20/28
placement test and, if headroom and occupancy justify it, one W3 scheduling test.
Do not turn small gains into a broad layout grid. After those decisions, qualify
one useful-resolution workload before further low-level kernel work.

## Bounded resolution screen

Use 640×384, B1, W1, 25 frames with the qualified current source, original BF16
arithmetic and 8+3 schedule. Independently recompute three distinct same-size native
references; compare all four tensors, finite/layout checks and actual samples.
Only after parity passes, measure ten distinct clips, labeled preliminary.
Record sampler/decode service times, completed-clip intervals, queue waits and
peak memory. Obtain new memory/storage admission; historical W1 estimates are
not reservations. Keep w93c as a separate small-shape regression gate.

Existing larger packet 98 arms explicitly bypass the oracle. Replica equality
and captured/eager equality alone do not prove quality relative to an unchanged
same-size calculation. Do not relabel those speed-only arms as qualified.
The [resolution probe](2026-10-06-resolution-cost-probe.md) measures decoder cost
rising from 0.52 s at 256² to 1.66 s at 640×384; transformer scaling and 13–16 fps estimates
remain unmeasured. The larger shape may change the bottleneck and best schedule.
See [packet98 build](2026-10-06-packet-98-build.md) and
[packet97 negatives](2026-10-06-packet-97-results.md).

## Longer coherent video

Continuation needs a separate native reference and seam/identity/audio review.
The existing CPU anchor/delivery machinery is not a qualified video result.
The upsampler drops the first-stage mask, so both stages require explicit
anchoring; audio alignment remains unresolved. Count 24 new frames after the
one-frame overlap, not 25. Preserve the
[continuation source-boundary requirements](continuation-source-boundary.md).
Do not substitute buffered unrelated clips for continuous-video delivery.

This is a read-only evidence synthesis and next-work decision, not a launch
preregistration, measured improvement or quality qualification. No model or
GPU request was made for the review.
