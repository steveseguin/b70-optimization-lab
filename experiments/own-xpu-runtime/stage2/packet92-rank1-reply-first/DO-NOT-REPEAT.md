# Packet92 boundaries

| Method | Outcome / next condition |
| --- | --- |
| Move bookkeeping just after half reply, before accept | Still serial: controller immediately waits for accept. Overlap requires carrying the report past accept and next-draft submission. |
| Count packet76's 666 us as current savings | Invalid: predates ordered retirement and contains work this candidate retains. New timer buckets and matched screens required. |
| Defer raw Engine/Candidate references | Unsafe: accept clears Candidate and draft changes counters. Freeze every mutable report value at the half boundary. |
| Suppress deferred I/O/affinity failure | Refused: poison, abort mailbox, no next half. Nine mock failure cases cover queued half, command boundaries and published-reply abort. |
| Move profiling, result readback or retirement in this candidate | Outside this mechanism. Keep synchronization, sticky errors and profiling safety checks before reply. |
| Call CPU timing a speed result | Invalid. Shared matched device screens and unchanged acceptance are pending. |
| Graph replay | Still deferred under packet76; this change supplies no new evidence for it. |

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
