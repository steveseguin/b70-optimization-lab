# Packet58k journal boundary repair — 2026-10-18

Question: why did the 07:24 UTC production-before arm refuse at K1a before
device execution? The retained `evidence/card0-screen-a/production-before/K1a/window.json`
reports `kernel journal boundary missing`. The queue passed the newest
reviewed kernel line's timestamp unchanged. The window queries strictly after
that timestamp, and an idle journal supplies neither a line nor a cursor.

The repair derives RT from the **validated saved capture**: its maximum
`__REALTIME_TIMESTAMP` minus 2,000,000 microseconds, using integer arithmetic.
`fault_review.validate()` still verifies the capture hash, exact known-fault
count and identity, boot, driver, current review and cursor tail. Only then
does each arm derive RT and pass it to K1a, K1b and WSCREEN. The arm receipt
records the original captured timestamp, derived RT and overlap duration.

For the refused capture, newest is `1792306806230449` microseconds
(`2026-10-18T07:00:06.230449Z`); RT is `1792306804230449`
(`2026-10-18T07:00:04.230449Z`). The review covers the journal through newest.
The unchanged window query starts at RT + 1 microsecond (journalctl's
inclusive `--since`). Therefore `(RT, newest]` is checked by both paths:
there is exactly a two-second overlap and no gap. A fault inside that overlap
still refuses; no known fault is silently filtered out of the window query.
Later lines remain subject to the existing full preflight, cursor and live
fault checks. Wall time is used only by the existing future-time rejection.

All 81 CPU tests pass, including the old exact-timestamp refusal, unchanged
journal behavior with the overlap, faults on both boundaries and just after
them, saved-capture tamper rejection, independence from later live captures,
and all three arms receiving the derived boundary. The native binaries are
unchanged; no build or device execution was needed. The seal verifies their
hashes and the updated Python sources. Three proposed queue jobs pass on a
temporary queue copy, targeting fresh `evidence/card0-screen-b` outputs.

Evidence: [regression tests](test_fault_boundary.py),
[CPU receipt](evidence/python-cpu-gates.json),
[queue plans](evidence/queue-plans.json), [seal](build-receipt.json).
The refused `card0-screen-a` output and original review capture remain in
place as history. The earlier CPU preparation closeout is unchanged.

No GPU job, service, live queue, settings or frozen packet was changed.
Device validation remains pending: the coordinator schedules the proposed
three-arm bracket in a whole-host gap. This repair makes no speed claim.
Revisit only if that fresh attempt produces new evidence of a boundary issue.
