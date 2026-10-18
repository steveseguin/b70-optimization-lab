# Packet94 — HC norm fusion

CPU-only task on steve-b70s. Read packet84 lineage and the packet78/73/60/54/39
negative records before edits. `git pull --rebase` refused the shared dirty
worktree; fetch found no incoming main commits. No stash, branch or worktree.
Root started with about18 GB free. Frozen work remains untouched.

[Design and exact producer/consumer chain](../experiments/own-xpu-runtime/stage2/packet94-hc-norm-fusion/DESIGN.md).
The norm tensor must remain because mix reads it. The new dedicated consumer
recomputes the same trees and preserves every BF16 boundary. Compilation will
share packet93's existing lock. No GPU, services or host settings changed.

Milestone 1: source copies and design recorded; build and gates pending.

Milestone 2: both host/device builds pass. Every view passes96 complete HC
cases (12 scenarios, four consecutive tokens, both sides), twice per compiler.
Each execution also checks20,480 raw FP32 low/injection chains. All candidate
bytes equal actual compiled production, including nonfinite payloads. GNU and
Intel production differ only in NaN payloads in22 cases; these are recorded
separately, with no candidate tolerance. Initial cross-compiler assertion and
all raw bytes are retained. The downstream weight cache composes cleanly.

All six full-size startup tests and unchanged memory admissions pass. The
reader census proves each norm has exactly low, mix and injection readers and
low immediately follows norm. Fused views capture zero separate norm kernels
and retain low/gate counts on both ranks, including alternate-bank capture.
Twelve short/misaligned allocation tests, five malformed selections and14
unsupported-mode tests refuse correctly. The plain fused view adds no device
allocation; the cached combination adds442,368,000 bytes per rank and leaves
502,723,894 bytes below rank1's30 GiB arena cap. Build logical bytes112,150,547
before full-shape compilation; max compiler RSS recorded in build receipt.
[Byte evidence](../experiments/own-xpu-runtime/stage2/packet94-hc-norm-fusion/evidence/cpu-byte-identity.json),
[startup](../experiments/own-xpu-runtime/stage2/packet94-hc-norm-fusion/evidence/full-shape.json),
[allocation admission](../experiments/own-xpu-runtime/stage2/packet94-hc-norm-fusion/evidence/full-shape-admission.json).
Milestone 3: all three views are sealed and all four proposed queues passed
planning on a temporary copy. The 80 shared-wrapper tests and 10 packet tests
pass. Review found that the twelve compressed native-plan/census archives
needed explicit verification and seal binding; the pending seal.py change
does both. The coordinator's compile_turn.py whole-host hold guard is preserved
and bound into every seal. No GPU ran.

Resume after commit148210904: the full-shape runs, seals and temporary queue
plans had already completed, so no build or completed gate was repeated.
The existing seals and both direction/lane plans were checked against current
files. Pull with rebase refused the shared dirty tree; fetch confirmed main
had no incoming commits. Other jobs' staged and unstaged files were preserved.
Build disk usage is116 MiB (138,236,737 logical bytes including hard links),
and root has over17 GB free. Fixture scratch cleanup is recorded in
`evidence/scratch-cleanup.json`.

Exact proposed paths, with B first or A first respectively:

- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p94-B-grid.txt`
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p94-A-confirm.txt`
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p94-A-grid.txt`
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p94-B-confirm.txt`

[Screen handoff](../experiments/own-xpu-runtime/stage2/packet94-hc-norm-fusion/WINDOW.md)
and [CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet94-hc-norm-fusion/CPU-PREPARATION-CLOSEOUT.md).
Production remains selected; actual device output checks and speed are pending.
No service, live queue, host setting or frozen source was changed by this work.
