# Two-card exchange preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can our Stage 2 IQ3 engine use both B70s inside a layer while preserving its
single-card arithmetic? October 11 CPU-only design and compile preparation,
Unsloth revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`; future cards 2/3.

## Outcome

Preparation complete; native timing, peer capability and model parity unmeasured.
The compiled harness prepares peer-query/copy and pinned bounce controls plus
60 ordered FP32 reduction/broadcast rounds. No speed or quality promotion.

## What worked

The pinned Device/Arena/CopyEngine protocol supports a shared owner for both
queues without weakening allocation/event lifetimes. CPU mocks exercise all
case setup, transfer sequencing, exact comparisons and clean shutdown. The
SYCL target compiles and links. The design gives row/column and expert placement,
cost assumptions and a packet ladder with frozen-output gates.

## What failed or remains uncertain

One compiler API spelling was corrected (`exception_list.size()`). No native
failure or GPU work occurred. One exchange/layer, perfectly balanced top-10,
and arbitrary two-part summation are rejected assumptions. The counterexample
demonstrates reassociation can change bits. Packet4's real-model layer mismatch
is unresolved independently. Actual route, latency, shared-context event
visibility, two-card fit and full-model quality require their own device gates.

## Evidence and patches

[Design](../TWO-CARD-TP.md), [harness and commands](README.md),
[build/test receipt](build-receipt.json), [pinned owner](owner-source.json),
[projection inputs](projection.json), [negative index](DO-NOT-REPEAT.md).
Original code is packet-local; shared runtime trees and all sibling changes
were preserved. Scratch from this validation was removed; no raw device
measurements exist to archive.

## When to revisit

After coordinator admission for physical cards 2 and 3, run the documented
bounded transport packet. Feed measured wall distributions into the design,
then implement the tree/row and expert-slot exactness census. A passing
transport receipt alone never admits a model or changes its arithmetic.
