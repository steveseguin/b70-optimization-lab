# Packet30 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can exact specialised route, attention, small dense and combine/norm/mix kernels
reduce remaining decode costs without changing `iq3-p17-detmath-v2`? Source is
packet27 plus packet28 selected small GEMV incumbents; intended hardware is B70.
This closes CPU preparation only; device qualification remains pending.

## Outcome

Kernels, runtime-baseline G3, two-owner wrapper and integration instructions are
prepared. No device ran during CPU preparation or this repair; the coordinator's
first K0 failed before device contact. No timing winner was adopted or speed claimed.
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

## 2026-10-12 coordinator admission repair

The coordinator's 01:32:52 UTC K0 attempt failed with zero visible devices because
the wrapper omitted `LD_LIBRARY_PATH`; binary run paths covered linked libraries,
but not the runtime's lazy adapter/UMF loads. The coordinator retired the erroneous
latch as a preflight-class failure. The complete original K0 and latch bytes,
including empty-journal markers, are [archived](evidence/20261012-k0-no-devices-missing-library-path/README.md).
G3 refused before creating an output directory.

The wrapper now requires and forwards the coordinator's exact library path,
records its SHA256 and binds it from K0 to G3. It checks adapter, UMF and Level Zero
loader files on that path before launch, without loading them. Native K0 and G3
separate empty enumeration from invalid card indices and report device contact.
Only an exited failure with explicit no-contact evidence and a complete empty
kernel delta avoids the fault latch; uncertain/contacted failures retain it.

Rebuilt the changed harness for both CPU compilers and the device target (compile
and link only). CPU fixtures, hostile protocol tests and ELF checks are resealed
in the build/CPU receipts. Family kernel gates were rerun because their source seal includes the changed
harness. No device executable or discovery ran here. The next
coordinator windows use `k0-card2b` and `g3-card2b` in [WINDOW.md](WINDOW.md).
