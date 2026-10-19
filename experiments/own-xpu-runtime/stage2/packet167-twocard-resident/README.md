# Packet167: two-card resident lookup audit

Closed at applicability: the tables are file-mapped, but the packet136 record
suite has zero recorded major faults. No runtime copy, candidate, queue row or
READY was created. Newer cold-run exceptions remain in the evidence.

[Source trace, full window table and closeout](../../../../notes/2026-10-19-own-runtime-packet167.md),
[negative-result index](DO-NOT-REPEAT.md), [replay](audit.py),
[saved audit](evidence/fault-audit.json).
