# Packet98c: native kernel-only v5 switching

CPU preparation is complete and sealed. The isolated engine and wrapper are in
`experiments/own-xpu-runtime/stage2/packet98c-v5-native/`.
The engine starts from packet97's bundle sources; the wrapper is a copy of v5.
Frozen trees, live queues and active record work remain untouched.

The source audit admits route, recurrence, production/wide HC gate and draft
attention switching. Experts, packed heads and all other choices stay fixed.
The proposed first device job is a route-only A/B/A on lane B, successfully
planned on a temporary queue. Device execution is outside this CPU-only task.
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
comparison passes against the final binary for all five configurations, twice
each: 46 switched miniature requests and 20 fresh single-selection references.
Every request matches its reference tokens and 212 state-file hashes. The
parent and new binaries are compared under the same selection. Miniature
geometry is synthetic; production-size allocation/capture tests separately
prove that each selection binds the intended kernels.

The final **130 wrapper tests pass**, including all 24 kernel-only combinations,
every non-switchable field, incomplete-smoke refusal, cold requests, changed
outputs/acceptance, and a mean-only apparent gain that fails the fastest control.
One new synthetic test initially scaled its fake rates in the wrong direction;
its corrected fixture passes. No production criterion was relaxed.
Both native and wrapper seals pass verification. The source audit checks all
192 copied native files and unchanged linked arithmetic objects. Parent
orchestration outputs and the mutable packet97 selection are not dependencies.

All five new files under `experiments/own-xpu-runtime/ops/lane-queue/` pass the
real planner using temporary queue copies:

- `proposed-p98c-smoke-B.txt`: route production / fast / production.
- `proposed-p98c-bracket-A.txt` and `proposed-p98c-bracket-B.txt`: route-fast
  plus rec-both-plus, experts fixed wide64. This is only decision f1e5's
  kernel-only part, not the half-cache composite.
- `proposed-p98c-attention-A.txt` and `proposed-p98c-attention-B.txt`: packet101's
  draft attention switch, alone.

Full jobs refuse until the same-seal lane-B smoke completes successfully.
Each device view requires incident64 and all twelve cold oracle prompts, 13/13
exact, zero cached tokens and identical per-prompt acceptance. Full brackets
report the slower candidate divided by the fastest of all three controls;
mean-control gains are explicitly diagnostic. Records remain on lane A and
still need the separate full-chain gates and fresh device repeat evidence.

Native builds and CPU milestones were committed and pushed immediately
(`6a07dd635`, `3445a0889`); the final seal/proposal commit follows this note.
The build remains about 73 MiB, with about 18 GiB free on root. Full-shape
archives preserve every original member after hash verification. Copied
historical patches/source retain their original whitespace; new edits pass
the whitespace check. No GPU, service, sudo, live queue or host setting ran or
changed. Device exactness, speed and wall-time savings remain unmeasured.

Primary evidence is in the packet's `evidence/{build,full-shape,reset-bytes,
protocol,native-source-audit,queue-plans}.json`, `lineage/screen-seal.json`,
and `placement-validation/wrapper-seal.json` plus its 130-test log.
