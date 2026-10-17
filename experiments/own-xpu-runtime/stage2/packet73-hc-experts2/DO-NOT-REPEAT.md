# Packet73 negative and bounded choices

| Arm | Outcome and evidence | Revisit condition |
| --- | --- | --- |
| HC virtual-four logical chains, separate stream subgroups | Rejected: 51 flag stores / 60 flag loads after linking device libraries. [Source](evidence/rejected-hc-virtual4.hpp), [report](evidence/rejected-hc-virtual4-linked.json). | A new spill-free mechanism with in-engine justification. Do not use packet67's four-stream geometry. |
| IQ4 all sixteen chains' raw span resident | Rejected: 256-byte GRF spill in the unlinked TU; final smaller eight-chain span is spill-free under linked compilation. [Source](evidence/rejected-iq4-span128.hpp), [report](evidence/rejected-iq4-span128.json). | Lower liveness without losing raw-load sharing. |
| Unlinked HC offline SPIR-V | Invalid occupancy evidence: unresolved fmaf calls added stack spills. Final inspection links exactly the required SYCL device libraries. | Never use unlinked math calls to rank candidates. |
| First HC output-pair implementation | Rejected by GNU fixture on scenario 0, byte 2: assumed row pitch 360 instead of expanded 380 including metadata. [Source](evidence/rejected-hc-pair-first.hpp). | Corrected in accepted implementation; keep metadata and assert fixture geometry. |
| Route epilogue fusion | Deferred within this packet: globally normalized top-k and tie rules need a separate synchronization design. | A bounded independently exact design with enough expected value. |
| CPU/offline success as speed or full-model quality | Not permitted. | Fresh in-engine screens, all 13 exact checks, before any record qualification. |

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) records the handoff.
