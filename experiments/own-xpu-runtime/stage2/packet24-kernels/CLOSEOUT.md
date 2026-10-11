# Packet 24 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the slow non-GEMV work be distributed across independent work items while
preserving every v2 arithmetic node and rounding point? This packet starts from
the packet23-fast commit and per-file hashes in [source-proof.json](source-proof.json).
The model is the separate Unsloth Flash-Next UD-IQ3_XXS lane, with unchanged weights,
BF16 state, reference arithmetic and lossless oracle. Preparation on steve-b70s
was CPU-only on 2026-10-11, at low priority with two numerical threads.

## Outcome

CPU preparation passed; [build-receipt.json](build-receipt.json) seals the result.
Device correctness, fresh-owner determinism and performance are **pending**.
No device binary was run and no speed improvement is claimed. The unchanged v1
kernels and new v2 kernels coexist in one binary. The coordinator owns the eight
windows in [WINDOW.md](WINDOW.md); this closeout does not close the runtime lane.

## What worked

Independent complete subtrees preserve the ordered reduction nodes, including
odd tails. Private upper trees avoid cross-work-group barriers. Independent ranks
preserve route ties; disjoint GDN state rows preserve token order. The fused routed
consumers retain one input row instead of copying it per expert. Source arguments
and timing targets are in [README.md](README.md). CPU evidence is recorded in
[cpu-tests.json](cpu-tests.json), [fixture-gates.json](fixture-gates.json),
[real-eight.json](real-eight.json) and [sanitizer-mini.json](sanitizer-mini.json).

## What failed or remains uncertain

Review found diagnostic-output parity, incomplete binding validation, fixture
coverage gaps, and timing-fixture accounting defects. These were repaired before
sealing; [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) preserves the findings. Independent
[tree](tree-review.json), [race](race-review.json), and [K2](k2-review.json) reviews
record their final scope and source hashes. Mock execution cannot establish GPU
race freedom, compiler numerical behavior, register pressure or launch economics.
Extra stages can cost more than the barriers they replace: K2 must decide this.
Large GEMV kernels remain unchanged. [GEMV-NEXT.md](GEMV-NEXT.md) records their
weight traffic and exact next candidates, with gains labeled as hypotheses.

## Evidence and patches

The source, tests, guard checks, window runner and receipts are all in this packet.
[build-receipt.json](build-receipt.json) binds the binaries and source closure.
[carryover-proof.json](carryover-proof.json) scopes inherited long CPU results to
v1 only; v2 has its own eight-token, 384-layer streaming check. The compressed
[verbatim fixture receipt](fixture-gates-verbatim.json.gz) retains the original
fixture process evidence, with a verified byte hash in the compact receipt.
Ignored build binaries, prepared inputs and generated source mirrors are retained
for the coordinator. Ephemeral CPU scratch is removed after sealing; the cleanup
receipt lists those paths. `build.py` recreates CPU gates and native binaries
without executing any native device entry. Model files remain in the existing
external store and are not part of Git.

## When to revisit

Run K0, two fresh K1 owners, K2, the canary, and the three oracle-gated decode
windows in order. Advance v2 only after exact device outputs and real-model oracle
agreement. Use K2 event execution sums and sequence issue time to choose which
stages to retain. Investigate routed GEMV decode reuse next; do not infer an
improvement from the old unfused spans or from a roofline estimate.
