# Packet49b decisions and negative-result index

| Finding | Evidence | Revisit condition |
| --- | --- | --- |
| Packet45's current tree is later than the SPEED6 record | SPEED7 and K2 probe closeouts in packet45 | Derive the selected historical snapshot explicitly; do not inherit unqualified later changes silently |
| Packet48's isolated controls do not establish production gain | [Packet48 device result](../../../../notes/2026-10-17-own-runtime-packet48-device-result.md), packet48b reconciliation | Fresh production-matched control/candidate windows, exact bytes and per-class decision |
| Packet47 ordered attention is slower | [Packet47 device result](../../../../notes/2026-10-17-own-runtime-packet47-device-result.md) | New mechanism with an independent worthwhile gain estimate |
| Packet46 layer launch fusion is neutral | [Packet46 device result](../../../../notes/2026-10-17-own-runtime-packet46-device-result.md) | New evidence that launches dominate a relevant workload |
| The split32 reduction cannot use the old full-model oracle | New arithmetic identity, independent scalar reference | Regenerate the full suite and captures, keep old differences informational |
| M=2 bridge support is not full-engine batching | [README](README.md) and independent attention review | A separate scheduling change with complete rollback and quality gates |

These close individual choices. Device qualification, production GEMV choices,
one-card work and further speed improvements remain open.

| Packet48b dense M=2 is unqualified | Packet48b preregistration covers M=1 only | Fresh production-matched M=2 gate before GDN QKV/Z adoption |
| 16-byte final expert row padding exceeds existing arena headroom | [Integration memory proof](INTEGRATION.md) | A separately justified memory mechanism; never silently raise the cap |
