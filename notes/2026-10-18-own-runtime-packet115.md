# Packet115: expert-only module-wide LARGE register file

CPU preparation on steve-b70s, October 18. Time box: two hours. No device,
service, power, memory, swap or page-cache operation is authorized here.

`git pull --rebase` refused unrelated dirty orchestration/evidence files.
`git fetch origin` confirmed main and origin/main both at
`9b49c03e7b7c07b8433d5c70fcc04888ecf634fc`, including packet103x
`932df6642`. Existing packets and queues remain frozen.

## Capability milestone

Installed icpx is 2026.0.0 (2026.0.0.20260331), ocloc 26.18.38308.1.
The module-wide `-options "-ze-fp32-correctly-rounded-divide-sqrt
-ze-opt-large-register-file"` is accepted by offline ocloc for `bmg-g31`;
generated assembly reports `numGRF=256`. This is not the rejected per-kernel
`SPV_INTEL_maximum_registers` property. No compiler or driver changed.

[Compile-only probe and commands](../experiments/own-xpu-runtime/stage2/packet115-large-grf/evidence/probe.json).
This establishes option support only, not expert spill freedom or device speed.

## Preregistered gates

Revive E3 next-block, IQ4 byte-pair SLM and V4 batch2/shared, and implement E5
shared gate/up scheduling. Copy from frozen packets; baseline is packet103
after103x, half-cache gate/up and tile16 down. Expert images alone receive
LARGE; retain default production and LARGE production as separate controls.

1. Every admitted kernel has an explicit zero-spill offline register report.
2. The real-route device micro is coordinator-only. Two fresh processes,
   both orders, all output bytes exact, candidate time at most 0.85 times
   both controls. Synthetic weights/inputs remain diagnostic.
3. Prepare the one-load v5 bracket in parallel, runtime `expert_kernels`
   switching only. No bracket admission before the micro passes. Seal only
   startup paths for actual views; retain `iq3-p49-split32-v1` output gates.

All compilation uses packet94's copied `compile_turn.py`, nice19, CPU affinity
8–15/24–31, Python `-B`, closed stdin and an 8 GiB CPU-only cap. Stop below
25 GB root free; keep the new build at most 250 MB. No live queue edits.

## Zero-spill and micro milestone

All four expert designs now have zero scratch allocations, zero scratch
instructions and zero predicate spills in the linked LARGE image. Production's
separate image uses 128 GRFs; LARGE uses 256. The image kernels have distinct
names to prevent merging with each other or inherited runtime kernels. The
exact prepared-command overlay is preserved across the shared-library boundary.

E5 initially spilled three flag stores and six flag loads even at 256. Its
common output epilogue fixes that while preserving independent V8 chains and
trees. The rejected source and assembly remain in `evidence/e5-first`.

GNU and Intel each pass two fresh runs per view (20 runs total), with 19
whole-output/status cases, 110,592 raw-chain and 3,456 raw-tree checks per run.
All output byte streams share the same SHA256. Exhaustive IQ2 grid/sign and
IQ4 code/half-scale tests pass. The linked register census and CPU bytes are
separate gates; neither establishes device speed.

The new [micro proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p115-micro-B.txt)
contains two fresh-process jobs. Both passed the coordinator planner on a
temporary queue. Each uses all 384 captured route vectors, both orders, default
and LARGE production controls. Matched-route medians must be at most 0.85 in
each order/control/process. Raw per-route ratios remain visible; there is no
single-noisy-pair veto or route selection. Ten gate/refusal tests pass.
Expected budget is 180 seconds per process, watchdog 900 seconds; actual
duration is unmeasured. The frozen packet100b route identity is rechecked.

[Image report](../experiments/own-xpu-runtime/stage2/packet115-large-grf/evidence/images.json),
[CPU identity](../experiments/own-xpu-runtime/stage2/packet115-large-grf/evidence/cpu-byte-identity.json),
[temporary plans](../experiments/own-xpu-runtime/stage2/packet115-large-grf/evidence/micro-queue-plan.json).
