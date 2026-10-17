# Packet49b CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet49 add the production-screened expert kernels without changing its
split32 oracle identity, 4K SPEED6 topology or memory limits? Separate
packet49b, IQ3 compressed target, two B70 cards; CPU preparation only here.

## Outcome

Preparation remains in progress. No device result or speed claim is made.
Serial builds and fresh CPU/sanitizer gates must finish before sealing.

## What worked

The integration selects IQ2 gate/up and IQ4 down for each existing M=1/M=2
engine row. A compact4-byte final row pitch avoids increased weight-bank
storage while retaining every required load alignment and arithmetic order.
Shared oracle/queue/storage/metric admission checks pass33tests.

## What failed or remains uncertain

Production-matched dense M=2 evidence is absent, so QKV/Z stays out.
The inherited suite identity literal blocked the new oracle and was corrected
only in this packet. GPU byte parity, model exactness, fresh-device repeats
and WS128 speed remain pending coordinator windows. The compact pitch needs
new device qualification; no p48b gain transfers automatically.

## Evidence and patches

[Integration](INTEGRATION.md), [review](REVIEW-INDEPENDENT.md),
[shared oracle binding](oracle-binding.json), [build commands](CPU-BUILD.md),
[storage/restore policy](ARTIFACT-RETENTION.md),
[task note](../../../../notes/2026-10-17-own-runtime-packet49b.md).
Fresh receipts will be bound by the final `build-receipt.json`.

## When to revisit

After sealing, run the registered early windows on cards0+1, then the model
windows against the completed original packet49 oracle. Final speed is WS128
with its WS128x exactness companion. The lane remains open; this closeout
records only CPU preparation and its remaining device gates.
