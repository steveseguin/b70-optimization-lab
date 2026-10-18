# Packet118 bundle7 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Prepare bundle6 plus the independently preregistered 80,128-row draft prefix
for the Unsloth quantized compressed Flash-Next IQ3 lane. Source is the frozen
packet111 bundle after packet111r; target arithmetic is `iq3-p49-split32-v1`.
Exactly two selections: 91,392 and 80,128 draft rows, both with fusion and the
repaired target-head split. Four-card host, October 18, CPU preparation only.

## Outcome

CPU preparation passes. GNU and Intel each pass two fresh head/fusion/reset
checks and two runs for each prefix. Both selections pass real-shape VRAM
admission and all 22 chain startup/host-reference windows. The smoke proposal
shipped in `27494913b` before the remaining orchestration tests. Both composite
proposals pass temporary queue planning. All 31 policy/submission tests pass.
No model speed or device quality is claimed; smoke and composites are pending.

## What worked

Only two C++ headers differ from packet111's runtime: they admit the fixed
packet114 prefix label. The exact packet114 selection changes are checked by
the [source audit](../../ops/packet118-orchestration/source-audit.json).
Both prefixes share the existing target head allocation. KD retains target
captures and recomputes only its prefix-specific draft reference.

The existing native launch guard observes all inherited getrlimit values.
The [CPU interception proof](../../ops/packet118-orchestration/evidence/launch-limits.json)
passes six actual rank boundaries (smoke, composite and chain); the old 8 GiB
address-space cap is rejected by an isolated negative child. Device imports
change no resource limits.

## What failed or remains uncertain

A new CPU shape assertion initially called a private C++ accessor. The test
now reads the runtime's prefix receipt; the [compile refusal](evidence/initial-full-shape-compile-refusal.log)
is retained. No runtime fault or changed arithmetic resulted.

Device smoke, exact target output and performance remain unmeasured by this
task. The candidate must beat both packet103 controls by at least 1.0% on
**each** lane, with exact prompts and deterministic acceptance within the same
selection. Different prefix selections may have different acceptance. The
full record chain and submission remain blocked until those gates pass.

## Evidence and patches

[Byte gates](evidence/cpu-byte-identity.json), [prefix gates](evidence/prefix-byte-identity.json),
[allocation census](evidence/full-shape.json), [22-window startup](startup103.json),
[smoke plan](evidence/smoke-queue-plan.json),
[composite plans](../../ops/packet118-orchestration/p118-composite-plans.json),
[CPU tests](../../ops/packet118-orchestration/tests.log),
[final audit](../../ops/packet118-orchestration/cpu-final.json),
[readiness](../../ops/packet118-orchestration/ready.json), and
[retention/restoration](RETENTION.md). All source changes are in this packet;
older stage and ops trees remain frozen. Live queues were not edited.

## When to revisit

The coordinator can execute the shipped smoke and then the two composites.
After their receipts exist, run the orchestration's `--evidence-only` reader;
CPU preparation is already complete. Readiness then enforces the fresh chain
folder, exact selection, threshold, smoke, CPU-test and launch-limit proofs.
Never retune N from those results. No job was launched or submitted here.
