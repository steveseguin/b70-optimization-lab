# Packet122 draft HC CPU preparation — closeout
<!-- campaign-closeout -->

## Question and identity

Can distributing independent sigmoid products and keeping one column's four
streams in a subgroup reduce the current draft HC gate cost without changing
a byte? Packet118 bundle7, fixed 80,128 prefix, original target oracle,
full 16-bit KV. Prepared on steve-b70s on 2026-10-18, CPU only.

## Outcome

CPU preparation passes. GNU/Intel each pass 16 byte cases twice; the four
runs share the same full output digest. Both views/ranks pass startup and
five-view switch/reset checks. Two fresh miniature IPC brackets match the
unchanged parent's tokens and draft/target state. Device speed and bytes
are unmeasured; no optimization is adopted or promoted.

## What worked

The new subgroup mapping keeps p59's original chain and reduction while
removing local-memory exchange and distributing independent epilogues.
[CPU bytes](evidence/cpu-byte-identity.json),
[full shape](v5/evidence/full-shape.json), [reset](v5/evidence/reset-bytes.json),
[protocol](v5/evidence/protocol.json), [exec limits](v5/evidence/exec-limits.json).

## What failed or remains uncertain

No device run occurred here. The candidate may lose from cache access or
shuffle/branch costs; the preregistered micro decides. Context4096 uses cyclic
real-capture fill, not a natural prompt. A copied budget-only wrapper callback
was caught during source review and removed before any device run; its native
binary did not change. The v5 proposal remains blocked until both micros pass.

## Evidence and patches

[Runtime delta](runtime-delta.patch), [candidate](p122_hc.hpp),
[micro gate](micro_gate.py), [provenance](source-copy-provenance.json),
[budget and byte table](../packet122-draft-budget/ROOFLINE.md),
[retention](RETENTION.md), [owner note](../../../../notes/2026-10-18-own-runtime-packet122.md).

## When to revisit

The coordinator runs the two proposed micros. Close this arm if any changed
class fails<=0.8 or any byte differs; do not geometry-sweep this same mechanism.
Only a passing exact micro authorizes the proposed v5 bracket. Its result
decides whole-model transfer. This closes CPU preparation, not the model lane.
