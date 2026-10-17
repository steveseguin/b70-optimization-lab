# Packet49d: packet49c engine plus banked exact kernels

Separate source copy of packet49c, retaining arithmetic `iq3-p49-split32-v1`
and the same hash-bound [packet49 oracle](oracle-binding.json). Preparation
never changes a protected packet, live chain, service or GPU.

The three banked packet53b winners are fixed: expert gate/up virtual8 split
stream, expert down virtual16, and small FFN Q6 virtual4. All five eligible
packet54 route, recurrence and HC mix candidates compile into one device build.
`selection.json` chooses production or one candidate per class. The engine
resolves submit functions at initialization; token replay does not parse or
branch on candidate names. M=1 and each serial M=2 row use these same sites.

CPU gates cover every selectable choice against production, independent of the
eventual selection. `cpu-preparation-seal.json` does not admit a GPU window.
The coordinator writes the selection after packet54's device decision, then
runs the fast reseal in [WINDOW.md](WINDOW.md). It revalidates both timing owners
and requires banked plus selected savings of at least 40 microseconds per ordinary
M=1 layer in each owner. It hashes existing CPU evidence and binaries without
rebuilding or rerunning numerical gates. `build-receipt.json` binds the final
selection and submission lineage.

- [Coordinator commands and selection](WINDOW.md)
- [CPU build and verification](CPU-BUILD.md)
- [Integration boundaries](INTEGRATION.md)
- [Storage envelope](ARTIFACT-RETENTION.md)
- [Task record](../../../../notes/2026-10-17-own-runtime-packet49d.md)

Keep target split 23/25, draft rank 1, capacity 4096, BF16 KV, model weights and
transaction/rollback unchanged. Operator savings are not model gains.
The coordinator must complete all early and model windows. WS128 remains the
authorized 128-token record scope; the strict 512-token gate stays false.
Preparation performs no external submission. Copied historical helpers are
implementation history, not approved entry points. Use this runbook only.
Never edit or reseal after a 49d device chain starts.
