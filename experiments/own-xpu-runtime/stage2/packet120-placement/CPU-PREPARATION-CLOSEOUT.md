# Packet120 placement preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Move target layer24 from rank1 to rank0 in a frozen copy of packet118 bundle7,
without changing any layer operation. Unsloth quantized compressed Flash-Next,
`iq3-p49-split32-v1`, wide64+halfcache, tile16 down, head split, 80,128 draft
prefix and fusion. Placement1 is 24/24; placement25-23 is 25/23. Four-card
host, October 18, CPU preparation only; each proposed device stage uses two cards.

## Outcome

CPU preparation passes. The candidate leaves 2,935,448,568 / 1,915,340,336 bytes
inside the unchanged 30 GiB rank arenas. No offload or head adjustment is needed.
GNU and Intel each pass two fresh exact-byte runs; both views pass all eleven
real-shape startup/host-reference windows. All thirteen protocol/policy tests,
four actual rank-exec limit interceptions and the forbidden-cap negative control
pass. Both three-stage v4 proposals pass temporary queue planning. Device
output equality, residency and speed remain unmeasured.

## What worked

The real allocation/capture census includes KV, scratch, recurrent banks,
speculative images, staging, E1 half-cache and the rank0 head suffix. The source
and captured-plan audit finds identical operations/storage for the moved layer
and identical ownership and operations for all other layers. Only two native
files change, to admit split25 and the existing pre-engine canary.

Both actual rank exec sites preserve all inherited resource limits and require
unlimited address space. Failure hooks and receipt-writing failures cannot
suppress the inherited drain stop. The report independently recomputes memory
admission and binds allocator and DRM client observations to both rank PIDs.

## What failed or remains uncertain

An initial fixture link retained an ancestor entry object; it was excluded as
in the parent harness. The first startup attempt correctly refused split25 on
the mini canary until that pre-engine path was admitted. A later complete
startup pass refused its final seal because Python sources changed during the
run; the final clean run passes after all edits. Refusals are retained.

The original +3% hypothesis is uncertain: packet108's draft wait is not spare
target-race time. Moving a whole layer may exhaust the roughly 0.52 ms race
slack and lengthen misses. No speed is inferred. Driver/library pools outside
the allocation arena and actual device residency still require the screen.

## Evidence and patches

[Census](evidence/census-first.json), [native delta](placement.patch),
[source/plan audit](evidence/source-audit.json),
[byte checks](evidence/cpu-byte-identity.json),
[full shapes](evidence/full-shape.json), [startup windows](startup103.json),
[protocol tests](evidence/protocol-tests.json),
[launch limits](evidence/launch-limits.json),
[temporary plans](evidence/queue-plans.json),
[timing hypothesis](TIMING-HYPOTHESIS.md), and [retention](RETENTION.md).
No existing packet, shared screen, live queue, GPU job or host setting changed.

## When to revisit

The waiter can run the proposed lane-B production / 25-23 / production bracket.
All twelve prompts × 128 tokens must match the unchanged oracle, with identical
acceptance across stages. A candidate beating both controls by at least 0.5%
admits the lane-A confirmation proposal, which enforces the same threshold.
The report includes hit/miss means and each rank's command times. This remains
a diagnostic screen; full strict512 quality/performance promotion is pending.
