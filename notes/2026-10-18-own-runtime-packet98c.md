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

Both native compilers pass. Twenty full-size starts and 100 view resets pass:
each admitted dimension on both ranks, with a fresh selected capture for
comparison. All 240 native refusal checks pass before mutation. Four fresh
miniature poison tests restore every mutable allocation, including pinned
buffers, and preserve all weights. All 125 Python wrapper checks pass.

The capture audit exposed missing HC-capacity and small-GEMV-shape fields in
the inherited CPU serializer. The local test helper now records both. The
full-shape fixture rebuilds only the two CPU submit objects needed to expose
those fields; production arithmetic objects stay unchanged. Failed logs remain.
Generated full-shape files were archived and every member rehashed before
scratch removal. The build currently occupies about 73 MiB, below 300 MB.

The first protocol attempt matched output/state bytes in completed cases but
stopped when a concurrent scratch archive removed a file during the size census.
The census now tolerates a disappearing scratch file. The complete protocol
comparison is rerunning against the final binary; seals and queue plans follow.
No device exactness or performance claim is made.
