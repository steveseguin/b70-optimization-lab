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
