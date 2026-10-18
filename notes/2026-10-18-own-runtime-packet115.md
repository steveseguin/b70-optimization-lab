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
