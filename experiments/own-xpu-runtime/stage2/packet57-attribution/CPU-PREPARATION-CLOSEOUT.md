# Packet 57 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can we attribute packet 56's remaining draft and target work inside its actual
engine without changing numerical execution? October 17, 2026; the Unsloth
UD-IQ3_XXS quantized compressed model, 91,392-row draft prefix, unchanged
packet 49 target oracle, 23/25 split and rank-1 draft. Device work is prepared
for two B70 cards, 0+1, with BF16 KV and twelve cold 128-token requests per arm.
The implementation revision is `07ff6be275c356186de2f197bd4ec20ca88cc80b`.

## Outcome

CPU preparation is accepted. Both compilers finish; four fresh miniature
Engine runs preserve target tokens, proposals, hit/miss counts and layer
fixtures. Nineteen focused CPU checks pass. The final seal independently
verifies. No GPU executable ran, and no new quality or speed result is claimed.
The retained build is 336,332,092 bytes, below the 1 GB cap.

## What worked

Common-clock native receipts support an honest hit/miss reconstruction:
rank 0 finishes last in 93.32% of complete cycles. New selective event
recording retains site identities and uses existing drains without adding
kernel waits. The paired control and diagnostic summary preserve observed
cycle and draft-wall perturbation, distinguish partial cancelled target
layers, and refuse incomplete event coverage.

## What failed or remains uncertain

All 92 checked old site files are empty. Individual draft and boundary-layer
costs cannot be recovered from them; split changes remain conditional
average-half sensitivities. Sparse device sampling will not measure complete
GPU idle or every snapshot copy. Full-model equality on the new binary,
class costs, placement costs and profiling perturbation await the coordinator.

## Evidence and patches

- [Timeline, receipt identities and reproducer](TIMELINE.md).
- [CPU gate receipt](p57-cpu-gates.json), [host build](build-gnu-host-receipt.json),
  [device compilation](build-device-receipt.json), [final seal](build-receipt.json).
- [Independent review](REVIEW.md), [observation configuration](p57-preregistration.json),
  [next levers](LEVERS.md) and [task record](../../../../notes/2026-10-17-own-runtime-packet57.md).
- [Retention and restoration](ARTIFACT-RETENTION.md); raw old receipts and new
  build files remain under the registered external result directories.

## When to revisit

The coordinator runs [the sealed diagnostic command](WINDOW.md) after packet
55 releases host resources and fresh admission passes. Use its actual class
costs to rank the next meaningful lever. Keep packet 56's measured record
unchanged; the optimization lane remains open.
