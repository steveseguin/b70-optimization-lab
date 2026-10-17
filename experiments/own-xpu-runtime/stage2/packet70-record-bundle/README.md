# Packet 70: combined record chain

CPU preparation only; the coordinator owns device execution. Packet 65's
unchanged device binary is reused by path and SHA-256. Its C++/header sources
are copied byte for byte; no compile or CPU model run was performed.
[Binary and source identity](binary-reuse.json).

The fixed preset is packet 64's `1-draft-hc-batch`, placement 1: 24/24 target
layers, rank-1 draft, packet56 draft-head prefix, controller spin and pure-spin
waits, packet60 target HC fusion, packet59 draft-HC fusion via packet63, and
packet62 batched rollback copies. Packet65 adds the independent expert choice:
`production`, `wide64`, `wg64`, `wg128`, or `prefetch64`. Production is the
prepared default until both quick-screen lanes are complete. Each of the five
views has a separate seal; all share the same binary.

Every inter-window gap is now **90 seconds**, including after W windows and
at a resumed-chain boundary. Drains, teardown spacing, fault polling, STOP,
PID/start identity, lane admission and whole-host timing holds are inherited
unchanged from packet64. The full eleven-window chain has ten gaps: this
removes 1,075 seconds of scheduled waiting (five gaps shortened by 215 seconds),
not a measured device speed improvement. The owner's October 17 18:07 UTC
review reported more than 40 screens with 90-second gaps and an unchanged
fault count of two. This is the supplied evidence for the timing policy,
not a new soak or guarantee. No sibling packet or shared screen source changed.

The packet's [screen copy](screen/screen.py) stages exact request receipts before
drain. After worker exit, completed teardown, isolation and fresh postflight,
it releases both the cooperative lease and legacy lane lock. Only then does
the parent aggregate and write CPU reports. Report failures record
`report-failure.json`, leave `passed=false`, and cannot create a device-fault
latch. Failures before release still retain the lease marker and existing
fault behavior. [Six mock tests](evidence/lease-tests.log) include the full
incident64 + twelve-request flow, failure injection and admission of the next lease.

The packet49 oracle, target weights/arithmetic and full BF16 KV remain the
quality authority. Packet65's inherited expert fixtures and packet64's preset
fixtures are retained, with no new model execution. Their combination still
requires the full fresh device chain. Screens remain diagnostic. The inherited
owner-authorized 128-token submission scope is explicitly separate from the
strict 512-token final gate, which remains false.

[Commands](WINDOW.md), [orchestration](../../ops/packet70-orchestration/README.md),
[submission/resume](SUBMISSION.md), [retention](RETENTION.md),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md),
[task note](../../../../notes/2026-10-17-own-runtime-packet70.md).
