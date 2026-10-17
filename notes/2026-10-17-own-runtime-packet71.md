# Packet 71 — dependent depth-two engine

The owner requested a CPU-only engine packet, with device windows owned by the
coordinator. Frozen packet64–70, screen and ops trees are read-only inputs.

Design milestone: [design](../experiments/own-xpu-runtime/stage2/packet71-depth2-engine/DESIGN.md).
The updated optimistic cost model reaches +8% at H2/H1 <=1.56037; allowing one
extra draft/repair step tightens that to approximately 1.42. Neither is a speed
measurement. Serial fallback, causal state gates, device commands and copied
packet68c integration remain in progress.

Initial free space was 17 GiB. `git pull --rebase` refused the coordinator's
dirty ops log/readiness files. `git fetch origin main` confirmed HEAD and
origin/main identical (0 ahead/0 behind); no stash or edit of those live files.
No GPU, service, model load or host-setting change was run.

Serial fallback milestone: GNU host and Intel device compilation pass without
opening a device. Three small synthetic four-layer prompts (8, 11 and 32 output
tokens) match the packet64 executable with all three acceptance cases forced.
All **1,854** final plan/spare-bank byte comparisons pass, including the QSA
extent boundary. The recursive draft path also emits the parent target tokens.
This is small-engine correctness evidence; full-model device identity is pending.

The first controller overlaps rank0's proposed pair with rank1's current row,
then drains to resolve the pair. It is screenable but carries extra copying and
bubbles, so the optimistic two-token pipeline model must not describe its speed.
The copied packet70 wrapper releases drained lane leases before reporting.
Smoke and matched control/candidate/control jobs are in the packet README.
The control uses packet64's sealed `1-draft-hc-batch` view: its top-level screen
seal is stale after the record bundle was selected. That failed CPU plan is
retained and no device ran. Build is approximately 93 MiB; free disk about 17 GiB.
