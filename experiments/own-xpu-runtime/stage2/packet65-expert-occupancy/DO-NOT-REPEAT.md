# Packet65 boundaries

| Date | Arm or method | Status / revisit condition |
| --- | --- | --- |
| 2026-10-17 | Batch all ten experts into one grid | Already production; not a new optimization |
| 2026-10-17 | WG64 / WG128 | CPU byte exact; coordinator in-engine comparison pending |
| 2026-10-17 | Wide raw operands, WG64 | CPU byte exact on GNU and Intel; fewer static loads with no spills; no device speed verdict |
| 2026-10-17 | Next-k-block raw lookahead, WG64 | CPU exact; earlier loads survive but compiler waits before current decode; larger code, device verdict pending |
| 2026-10-17 | Naïve gate/up/down fusion | Down needs all rounded activated rows across workgroups. No legal grid barrier supplied; not implemented |
| 2026-10-17 | Activation-only fusion campaign | About 4.7 µs opportunity cannot reach broad-class 30% bar; skipped |
| 2026-10-17 | Isolated timing or gate/down-only 30% | Cannot satisfy the approximately 0.192 ms full-class integration bar |

Packet52 free-order, packet53 persistent/SLM, and packet53b V16 gate/up arms
remain closed; see their retained DO-NOT-REPEAT files. Neither a passing CPU
fixture nor zero offline spills qualifies an engine speed improvement. Keep the
packet49 oracle, full BF16 cache, exact model weights and all arithmetic trees.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md). No performance arm is
closed here before the coordinator’s device evidence exists.
