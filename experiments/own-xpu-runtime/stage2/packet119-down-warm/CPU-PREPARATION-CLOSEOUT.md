# Packet119 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can independent reads of the already-selected experts' tile16 DOWN weights
use gate/up's idle memory bandwidth and reduce the combined operator time?
Packet118 source copy, unchanged E1 gate/up arithmetic, `down_warm=p119`,
B70 target, packet100b's 384 fixed real route vectors, October 18.
The model-quality oracle remains `iq3-p49-split32-v1`.

## Outcome

CPU preparation passed. No device experiment ran in this work. GNU and Intel
each passed two fresh byte checks; the actual AOT micro retains the extra DOWN
read and has no spills. Both micro proposals pass temporary queue planning.
A separate conditional v5 bracket has compiled native binaries and passes its
selected startup, reset, protocol, inherited-limit and seal checks.
No speed gain, measured cache capacity, device equality or new model result
is claimed. The diagnostic weights and activations are synthetic; routes are
captured real model choices.

## What worked

The extra reads leave arithmetic unchanged and need no new model allocation.
Every selected DOWN byte belongs to the existing tile16 bank. Runtime warming
is bounded by the reported cache property. The exact binary's LLVM, vISA and
native instruction trace retain the intended load under the normal cache policy.
The full-shape capture tests distinguish production and candidate on both ranks
and reproduce capture identities after switches and fresh startup.

## What failed or remains uncertain

No B70 usable-cache-capacity measurement was available locally. The proposed
micro measures a cold/warm size curve before its operator pairs. Whether the
loads remain resident and save enough DOWN time is unknown. More gate/up reads
can also make the pair slower; both orders in both fresh processes must reach
at most 0.85× production pair time before v5 is admitted.
Review caught and fixed a missing qualification CLI, incomplete combined build
accounting, and missing v5 evidence/dependency seal checks. Startup compilation
caught and fixed an overly broad insertion of the new DOWN-binding code.
These were CPU preparation faults; none involved a device.

## Evidence and patches

- [Warming source](p119_warm.hpp) and [runtime binding](p49d_expert_submit.cpp).
- [CPU bytes](evidence/cpu-byte-identity.json), [ISA proof](evidence/warm-isa.json).
- [Micro preregistration](micro-preregistration.json) and [temporary plans](evidence/micro-queue-plan.json).
- [V5 instructions](v5/README.md), [startup](v5/evidence/full-shape.json),
  [reset](v5/evidence/reset-bytes.json), [protocol](v5/evidence/protocol.json).
- [Retention and rebuild](RETENTION.md), [task note](../../../../notes/2026-10-18-own-runtime-packet119.md).

## When to revisit

The coordinator executes the two proposed micros once each. If either fails
its exact-byte or 15% time gate, retain its results and close this warming arm.
Only a clean two-process pass admits the prepared v5 one-load bracket. Its
unchanged per-token model oracle still decides quality. The shared-expert and
small-GEMV variants have not been implemented or tested in this packet.
