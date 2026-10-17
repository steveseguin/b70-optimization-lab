# Packet49b CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet49 add the production-screened expert kernels without changing its
split32 oracle identity, 4K SPEED6 topology or memory limits? Separate
packet49b, IQ3 compressed target, two B70 cards; CPU preparation only here.

## Outcome

CPU preparation passed and is sealed. All three builds, fresh CPU/sanitizer
gates and independent seal verification passed. No device result or speed
claim is made.

## What worked

The integration selects IQ2 gate/up and IQ4 down for each existing M=1/M=2
engine row. A compact4-byte final row pitch avoids increased weight-bank
storage while retaining every required load alignment and arithmetic order.
Shared oracle/queue/storage/metric admission checks pass 34 tests. The expert
gate passes 192 checks across fresh GNU and sanitizer processes; all 142
replacement banks retain their original byte sizes.

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
The [final seal](build-receipt.json) binds 35 artifacts and 437 sources, with
SHA256 `000960bb7690119fbb99723c00abc23961aab3efb6b94bfeb8734624e3e71221`.
The [fixture correction receipt](p49b-fixture-correction.json) preserves the
initial CPU geometry refusal and hashes; production guards stayed unchanged.

## When to revisit

Run the registered early windows on cards0+1, then the model
windows against the completed original packet49 oracle. Final speed is WS128
with its WS128x exactness companion. The lane remains open; this closeout
records only CPU preparation and its remaining device gates.
