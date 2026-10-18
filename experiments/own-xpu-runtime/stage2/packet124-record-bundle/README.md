# Packet124: bundle 8 BASE

One composition: packet118 bundle7 (packet103 + packet109 fusion + packet105b
head split + packet114's fixed 80,128-row prefix). Native sources and both
native binaries are unchanged. The host cooldown now clamps its sleep to zero
if the clock crosses the deadline during the checks.

The four GNU/Intel CPU repeats match the saved packet118 outputs byte for byte.
All eleven chain startup paths run on CPU at real shapes, including KD's host
reference and device-startup arguments. CPU preparation is not a device quality
or speed claim. The required output identity remains `iq3-p49-split32-v1`.
VRAM admission, BF16 KV, target verifier and full target head are unchanged.

The prefix comes from [packet114's copied preregistration](prefix-calibration/preregistration.json),
selected on non-benchmark text. Never retune it from benchmark prompts, output,
acceptance or timing. Submission notes disclose this rule.

[Orchestration](../../ops/packet124-orchestration/README.md) reads packet118's
original smoke and both matched composite brackets for this identical
selection. Its chain success or failure is irrelevant to that readiness rule.
The new output is `build/device-cards01-a`; nothing is launched here.
No manual other-lane pause is required for the fixed chain. The existing
exclusive reservations during timing windows remain required.

CPU preparation uses nice19, CPUs 8–15/24–31, Python `-B`, closed stdin and
at most 8 GiB. Run `cpu_prepare.py reuse_build.py cpu_gate.py prepare_chain.py
full_shape.py startup103.py prepare_packet.py` in this folder under those
restrictions. Only the CPU startup fixtures compile, one at a time through
packet94's compile turn. Runtime binaries are reused byte-identically.
Root must retain 25 GB free; build maximum is 250 MB.

[Disabled extension slots](extension-slots.json) and the orchestration runbook
allow one micro-qualified follow-up composition. No unmeasured lever is enabled.
[Work note](../../../../notes/2026-10-18-own-runtime-packet124.md).
