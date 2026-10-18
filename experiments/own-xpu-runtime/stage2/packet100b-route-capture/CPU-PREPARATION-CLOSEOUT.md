# Packet100b route capture: CPU preparation closeout

## Question and identity

Can a small diagnostic supply real target DOWN routes to packet100 without
changing target arithmetic or frozen parents? Packet97's record-line selection
with production head, two B70s on lane B, two standard prompts × 64 tokens.
The proposed micro retains packet100's compiled 2560 × 640 kernels and 15% gate.

## Outcome

Prepared and CPU-validated; no GPU ran. Both compiler builds and repeated copy
tests, both full-size startup/capture checks, 23 Python checks and six temporary
queue plans pass. The build is about 66 MB. Device output equality, actual routes,
micro timing and candidate qualification remain pending.

## What worked

Device-only per-layer copies into fixed token slots, accepted-step bookkeeping,
request-boundary readback, and a deterministic four-position micro sample.
The frozen packet100 driver accepts the new qualification provider through a
separate adapter; its quality and bracket rules remain unchanged.

## What failed or remains uncertain

The first full-shape fixture link retained the parent's executable entry object
and refused a duplicate main definition. The fixture link now removes that
object; both startup checks pass. No device fault occurred. CPU tests cannot
establish device output equality or a speed gain. The capture must pass both
64-token oracle comparisons before any route can qualify the micro.

## Evidence and patches

[Capture header](route_capture.hpp), [COW build](build_engine.py),
[CPU bytes](evidence/capture-cpu.json), [startup census](evidence/full-shape.json),
[Python checks](evidence/python-tests.log), [plans](evidence/queue-plans.json),
[final verification](evidence/final-verification.json), [retention](RETENTION.md).

## When to revisit

The lane coordinator runs the proposed capture and then the proposed micro when
lane B and the unchanged memory/fault/drain admission permit it. A candidate
advances only after the original per-route and both-order 15% gate. No live job
was queued and no existing packet was resealed.
