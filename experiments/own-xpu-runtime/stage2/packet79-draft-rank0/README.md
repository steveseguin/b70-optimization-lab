# Packet79: rank0 draft on the record lineage

CPU preparation is complete. Six sealed views share one binary: placements
`1`, `0-split23`, and `0`, each with production HC or `hc-wide`. Target
arithmetic `iq3-p49-split32-v1`, packet49 verification, BF16 KV, draft-HC,
wide64 experts and batch rollback are unchanged. Sources are copied from
packet75; all kernel objects are identical to packet75. Only the host draft
loader changes. The rank0 private head has exactly 91,392 expanded Q6 rows
(308,904,960 bytes), never the full head.

The roughly 5% gain at 23/25 is a projection from packet77, not a measurement.
Real-model outputs, acceptance, memory residency and speed await the coordinator.

| Placement | Target layers | Draft rank | Rank0 allocation / arena headroom, GB | Rank1 allocation / arena headroom, GB |
| --- | --- | --- | --- | --- |
| `1` | 24/24 | 1 | 27.685 / 4.527 | 31.267 / 0.945 |
| `0-split23` | 23/25 | 0 | 30.223 / 1.989 | 29.029 / 3.184 |
| `0` | 24/24 | 0 | 31.349 / 0.864 | 27.913 / 4.299 |

Decimal GB. These are the real allocation calls in the full-shape mock, under
the unchanged 30 GiB arena. The separate physical-capacity plan retains the
existing reserves and 1.5 GB minimum free; rank0 margins after reserves are
3.973 GB at 23/25 and 2.847 GB at 24/24. Driver overhead remains unmeasured.
The name `0` explicitly passes `--target-split 24`; it does not use the historical
22/26 default. [Census and admission](evidence/memory-admission.json).

All 12 full-size post-load setup runs pass. Twelve fresh miniature runs match
packet75 target tokens, 96 target-state fixtures per run, draft proposals and
draft state. GNU and Intel each pass two fresh selected-operator and native
protocol runs. All 75 Python tests, 12 real wrapper plans and both temporary
queue plans pass. [Final verification](evidence/final-check.json).

Only the new entry points below are supported. Other copied packet75 helpers
are retained source history, not a prepared full-chain entry point.

- [Screen commands and proposed jobs](WINDOW.md)
- [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md)
- [Rebuild and retention](RETENTION.md)
- [Task note](../../../../notes/2026-10-17-own-runtime-packet79.md)
