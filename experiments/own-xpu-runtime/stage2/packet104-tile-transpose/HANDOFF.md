# Packet104 handoff

The new proposed job is `ops/lane-queue/proposed-p104-micro-B.txt`, relative to
`experiments/own-xpu-runtime/`. The CPU-only wrapper plan and temporary
lanequeue plan pass. No live queue or device was touched by preparation.

The micro's nine kernels use packet100's copied sources and exact selected
baseline dispatch. Forty pairs alternate order per stratum. Target and draft
expert arms consume all 384 supplied packet100b target-route vectors; draft
is explicitly a replay diagnostic. Shared and HC kernels use eight fixed
input strata. Target shared Q6 and F32 router arms each time the full selected
tuple and use eight input strata. Every timed arm first passes device
FP32/BF16/status or output-guard checks.
Require at least 15% lower kernel time overall, in each order and every stratum.

After a qualified micro, compile and qualify only the winning runtime views
in `views/`. Every view composes with `down-tile16`. The half-cache candidate
requires its separate half-cache control; do not mix the cache change into
the transpose comparison. `integration-plan.json` explicitly leaves all
full model gates false. No model seal or screen proposal is supplied yet.

Required next CPU evidence is GNU and Intel byte identity, then every actual
chain-window startup: K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs, WS128x, WS128.
Use the real parser, native argv and host-reference paths, as packet97e does.
KD needs both startup paths and exact draft identity against each resident
view. The prepared `draft-host-reference.json` retains draft choices and
removes resident-only target layouts. It still needs the full startup check.
Then actual allocation/VRAM admission and seals, followed by fresh B
control/candidate/control and A confirmation. Record chains belong on A.

Read [the task note](../../../../notes/2026-10-18-own-runtime-packet104.md),
[boundaries](DO-NOT-REPEAT.md) and [retention](RETENTION.md). No CPU success is
a device speed or full-model exactness result.
