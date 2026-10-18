# Packet80 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Question: can packet75's chain compose the host, route, norm, HC and draft
placement choices from packets76/78/79 while retaining packet49 arithmetic?
The October 17 CPU checks keep target identity iq3-p49-split32-v1, the packet49
oracle and full-precision KV. They prepare the two-B70 chain on steve-b70s.

## Outcome

The numerical, allocation and protocol checks pass. All 128 shared-wrapper
screen plans and 704 chain-window plans passed for the final source identity.
The final test run passed 200 chain tests, 24 subtests and 9 orchestration
tests. No device result is claimed.

The binary admits 16 host/route/norm/HC combinations across four placements.
Dense stays production and experts stay wide64. Other values, an unknown
placement or a changed sealed selection are refused. None of these 64
configurations needed exclusion after the CPU gates.

## What worked

Independent dispatch keys compose in one binary. Full post-load mocks exercise
the real allocation and capture path; the miniature native engine verifies
target and draft bytes for every placement. Separate native protocol tests
exercise rank-0 reverse handoff and rank-1 ordered retirement under both
compilers. Existing K2, merge and submission consumers accept the new keys.

## Evidence and patches

The [source manifest](parent-source-manifest.json) pins packet75 ancestry.
The selected seal binds local source changes and the binary. Retained gates:

- [Numerical bytes](evidence/cpu-byte-identity.json): 2,096 output and scratch
  cases per configuration, twice with GNU and twice with Intel.
- [Ordered retirement](evidence/retirement-byte-identity.json) and
  [native handoff](evidence/protocol.json): both compilers, repeated, including
  refusal paths and rank-0 reverse handoff.
- [Full-shape mocks](evidence/full-shape.json) and
  [memory admission](evidence/memory-admission.json): all 64 configurations on
  both ranks through the real post-load allocation and capture paths.
- [Native miniature engine](evidence/cpu-gates.json): all 64 configurations,
  twice, with exact target and draft identity against packet75.
- [Final rehearsal](evidence/dry-run.json) binds worker imports,
  lane admission, 128 screen plans, 704 chain plans and downstream tests.

## What failed or remains uncertain

The rank-1 draft at 23/25 has only 89,364,320 bytes left in its fixed arena.
It passes the existing admission rule, but the census does not measure actual
driver residency. The combined path still needs the fresh device chain's
packet49 exactness, repeat and performance checks. No CPU result substitutes
for them, and no combined speedup is inferred from separate screens.

The final review caught one inherited resume helper accepting packet70's schema
instead of packet80's. Direct entry tests now cover acceptance of packet80 and
refusal of packet70/75 before writes. Partial pre-fix plan logs and old seals
are retained; the final rehearsal passed after the fix. The first miniature
attempt refused before launch without OMP_NUM_THREADS=2; recorded runs use it.

All source changes remain in this packet and its new orchestration directory.
The [retention record](RETENTION.md) explains original-byte archives and local
build dependencies.

## When to revisit

Revisit CPU preparation after any binary, source, placement
or wrapper identity changes. The one-shot orchestration must be rerun when new
screen confirmations arrive; [ready.json](../../ops/packet80-orchestration/ready.json)
and its verifier determine whether the current command is ready. Nothing here
launches that command.
