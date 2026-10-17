# Packet78 small kernels — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can fewer launches and cheaper small reductions improve the packet70 record
line? The October 17 CPU preparation copies frozen packet75 sources, retains
`iq3-p49-split32-v1`, wide64 experts, draft-HC, batch rollback, 24/24 layers,
full precision KV and packet49's oracle. Hardware target is two B70 cards.
No GPU or model computation was executed in this preparation.

## Outcome

Five candidates are sealed for diagnostic screens in one binary. Both GNU
and Intel pass two fresh CPU executions per view. Each execution checks
2,048 route cases and 40 full-size HC norm cases. The combined HC-wide view
also checks eight full-size gate/mix cases. Every compared byte agrees,
including routing indices, weights, gather descriptors and scratch values.

Ten full-shape startup runs pass: five views, both ranks. The actual engine
allocation, capture, speculative banks and draft initialization paths run
with payload-only mocks. Real expanded strides are checked. Captured operation
types confirm that all three selection keys reach their intended consumers.
One short allocation and five malformed selections are rejected. Eighty
shared-wrapper tests and five packet tests pass, including real lane admission
and worker imports in the closed environment.

The final verification records six lane-A plans and all twelve possible
lane-B plans. Both queue proposals are tested on a temporary copy. The shared
wrapper, live queue, latches and frozen packet trees are unchanged by this work.

## What worked

Existing raw events show approximately 3.2 / 3.2 / 10 / 3.3 microseconds for
route's maximum, exponential, ranking and renormalization stages. The new
route uses a single workgroup and a 45-round bitonic network over rounded
probability/index pairs. Thirty-five rounds stay inside subgroups; ten need
shared-memory exchange. The arithmetic and tie rule are unchanged.

The norm uses one subgroup per output tile, retaining all original 32-leaf
subtrees, upper-tree padding, scratch stores, gain and BF16 boundary. Packet60
low/injection/activation and packet73 HC gate/mix semantics remain intact.
The name `norm-fused` selects this single-subgroup alternative, not producer
or consumer fusion.

## What failed or remains uncertain

The first single-workgroup route retained all-pairs ranking. It passed CPU
checks, but source review identified unnecessary serial comparison work.
It was replaced before any device launch. Its source and first receipts are
retained under `evidence/pre-bitonic/`; this is a scheduling concern, not a
measured negative speed result. Those old seals are superseded and nonlaunchable.

No device parity, register/occupancy measurement or speed result exists for
either final candidate. Barrier cost and subgroup occupancy can still erase
the hoped-for benefit. The brief's approximately 4% is not a lab measurement.
CPU byte identity does not replace the device oracle or fresh-server gates.

## Evidence and patches

- [Existing route stage measurements](evidence/structure.json).
- [CPU byte checks](evidence/cpu-byte-identity.json).
- [Full startup and captured selection consumers](evidence/full-shape.json).
- [Python checks](evidence/python-tests.json).
- [Final seals and screen plans](evidence/final-check.json).
- [Temporary queue plans](evidence/queue-plans.json).
- [Route](p78_route.hpp), [norm](p78_norm.hpp), [source pins](parent-source-manifest.json).
- [Retention and rebuild boundaries](RETENTION.md).

## When to revisit

The coordinator can run the proposed lane-A grid. Lane B admits only its exact
best candidate if it beats both lane-A controls, then surrounds it with two
fresh controls. All thirteen packet49 checks remain mandatory. No live job
was queued here. An eventual winner still needs the appropriate full chain
before any speed promotion.
