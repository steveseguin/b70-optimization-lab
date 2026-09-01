# Qwen3.8 Flash-Next TP4 full-decode XPU graph component preregistration

Date: 2026-08-31

Status: frozen before device execution

## Question

Can XPU graph replay preserve and accelerate the exact TP4 collective used 97
times per Flash-Next target token? A positive is the minimum prerequisite for
a materially different endpoint graph arm using compilation mode `NONE` and
`FULL_DECODE_ONLY`. Unlike seven historical PIECEWISE attempts, that endpoint
design would perform no Dynamo/Inductor compilation and therefore would not
reproduce their host-memory failure mechanism.

## Frozen probe

Run four local XCCL ranks, one per B70. Each rank operates on the production
BF16 `[1, 2560]` tensor (5,120 bytes). Compare ordinary XCCL with an
`XPUGraph` containing exactly one in-place all-reduce. Change every rank's
input on every replay and require the exact CPU-computed sum, an identical
eager/graph hash sequence, and more than one unique output hash. This prevents
a stale buffer, omitted collective, or no-op replay from passing.

The probe is component-only: no checkpoint, server, model forward, endpoint
quality, or throughput claim. Any exception, timeout, mismatch, device event,
or surviving process is a negative. A positive only authorizes static design
of a compilation-free `FULL_DECODE_ONLY` endpoint arm with the complete
quality battery; it does not authorize promotion.

The current health-gated reuse policy applies. No reboot is required or
authorized for this probe.
