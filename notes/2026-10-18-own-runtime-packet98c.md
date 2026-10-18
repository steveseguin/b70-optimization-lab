# Packet98c: native kernel-only v5 switching

CPU preparation in progress. The isolated engine and wrapper are in
`experiments/own-xpu-runtime/stage2/packet98c-v5-native/`.
The engine starts from packet97's bundle sources; the wrapper is a copy of v5.
Frozen trees, live queues and active record work remain untouched.

The source audit admits route, recurrence, production/wide HC gate and draft
attention switching. Experts, packed heads and all other choices stay fixed.
The proposed first device job will be a route-only A/B/A on lane B, planned
on a temporary queue. Device execution is outside this CPU-only task.
See the packet's `LAYOUT-AUDIT.md` for exact load/dispatch boundaries.

The initial `git pull --rebase` refused pre-existing shared edits. Fetch showed
main equal to origin/main. No stash/reset was used. Commands use nice19,
cores 8-15,24-31, python3 -B and closed stdin. Compiles use packet94's shared
compile turn, 8 GiB address-space limit, one compiler and a 300 MB build cap.
No GPU, service, sudo, settings or secret reads are needed.

Build, full-shape, byte identity, refusal, protocol and seal results are pending.
No device exactness or performance claim is made.
