# Packet 14 CPU implementation — closeout

<!-- campaign-closeout -->

## Question and identity

October 11, 2026: implement within-layer TP2 for the separate Unsloth
Flash-Next UD-IQ3_XXS quantized compressed version, retaining packet 13's
arithmetic, with packet 12's peer route on coordinator-owned cards 2+3.
Identity: `iq3-p14-full-row-p13-tree-slot-order-v1`.

## Outcome

CPU mini-model equality and compile-only SYCL gates pass. No device binary,
server, model payload read or external download was executed. Real-model
quality, native repeat, memory admission and speed remain unmeasured here.

## What worked

Whole-row dense shards retain the full-shape reduction. Expert-ID placement
retains original route-slot results and the original ordered sum. Two Arena
owners share a peer context, with bounded tracked copies and compact state.
Both projection shards are prepared/submitted before either wait. Independent
CPU reference and separately built packet-13 controls compare every buffer.

## What failed or remains uncertain

Two local expert sums are not the old arithmetic; that proposed shortcut is
rejected. Early CPU tests caught odd-head partition and metadata export errors;
both were repaired without oracle changes. Forty or more exact gathers per
layer exceed the old single-round-trip assumption. Streaming/scalar/verification
overhead remains; no 1.5× improvement is established. Native transcendental
parity and the real-model CPU oracle are still required.

## Evidence and patches

[CPU results](cpu-tests.json), [build/source hashes](build-receipt.json),
[full coverage and traffic](placement.json), [negative index](DO-NOT-REPEAT.md),
[implementation and arithmetic](README.md). Source is our own packet-13 CLI,
packet-12 transport, packet-9 experts, packet-10 expansion and packet-4 scalar
math adapted locally; Intel libraries are dependencies. Other packets and the
coordinator's running build were not edited. Scratch is deleted after validation;
`build.py --keep-build` reconstructs executables without opening a GPU.

## When to revisit

The coordinator's completed passing packet-13 one-card receipt unlocks the
separately admitted [layer-0 then first-token window](WINDOW.md). After exact
native equality and repeats, use measured exchange/scalar/streaming timings to
choose dependency-safe communication fusion and residency work. This closeout
ends CPU preparation, not the model optimization lane.
