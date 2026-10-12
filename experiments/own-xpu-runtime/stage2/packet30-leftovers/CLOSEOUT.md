# Packet30 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can exact specialised route, attention, small dense and combine/norm/mix kernels
reduce remaining decode costs without changing `iq3-p17-detmath-v2`? Source is
packet27 plus packet28 selected small GEMV incumbents; intended hardware is B70.
This closes CPU preparation only; no device result exists.

## Outcome

Kernels, runtime-baseline G3, two-owner wrapper and integration instructions are
prepared. No device ran, no timing winner was adopted, no speed was claimed.
Final compile/test/binary bindings are in [build receipt](build-receipt.json).

## What worked

CPU exactness fixtures and independent tree/race reviews preserve adjacent-pair
and odd-tail nodes, stable ranks, selected-order attention and BF16 boundaries.
The harness calls the actual runtime paths and uses eight full allocations for
large payloads. [CPU receipts](cpu-tests.json) distinguish all gate counts.

## What failed or remains uncertain

The four-launch route premise was corrected to five. Gate/low and norm/mix fusions
cross real dependencies and were excluded. Empty attention has a pre-existing
Core/incumbent disagreement and remains diagnostic. Some candidates trade
occupancy for launch reduction and can be slower. Gate/down lack a matched
post-packet28 in-model anchor. All device equality, timing, and model repeats
remain pending. [Negative index](DO-NOT-REPEAT.md) retains these boundaries.

## Evidence and patches

All new sources live here. Protected packets13..29, bounds, CURRENT and scoreboard
were read only. Designs and independent reviews are linked from [README](README.md).
Rebuild commands and source hashes are retained; build binaries are ignored.
No external patch or model weights were imported.

## When to revisit

Run [K0 then G3](WINDOW.md) on an admitted card. Integrate only qualified,
nonoverlapping dispatch proposals and then run the unchanged model quality and
fresh-owner gates in [INTEGRATE](INTEGRATE.md). This closeout does not end the lane.
