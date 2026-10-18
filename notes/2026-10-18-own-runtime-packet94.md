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
Seals and temporary queue plans are next. No GPU ran.
