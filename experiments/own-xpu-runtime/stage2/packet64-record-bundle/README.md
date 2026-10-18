# Packet 64: record bundle

CPU preparation is complete. One device binary supports eight sealed selections:

| Selection | Choices | Prepared default |
| --- | --- | --- |
| Target placement, draft on rank 1 | `1` = 24/24; `1-split23` = 23/25 | `1` |
| Draft kernels | `production`, `draft-hc` | `production` |
| Miss copies | `control`, `batch` | `control` |

The engine combines packet61x's draft-head prefix, controller spin, three
pure-spin waits and target HC fusion with packet63's selectable draft HC
kernels and packet62's selectable batched rollback copies. Third-bank and
overlap modes are unreachable through the sealed native selection parser.
The target weights, verifier arithmetic and full BF16 KV cache stay unchanged.

Every view in `selections/<placement>-<draft>-<miss>` has its own screen seal,
placement audit, target fixture and memory plan. Its executable is a hardlink
to the same binary. The coordinator chooses the final defaults after the
screens using [fast reseal](WINDOW.md); measured resealing took about 1.3 s.
No screen result is asserted for this combined binary yet.

The full chain reads the selected target boundary and draft rank. K2 keeps
operator-class dispatch independent of layer ownership, records the chosen
placement, and requires fresh operator exactness. Packet56's fixture binaries
remain unchanged; both full engines are packet64. KD writes its host scratch
inside the packet's external build tree. The extended checker includes
nested inputs, generated edges, admission sidecars and every registered
write/scratch location.

Lane-aware admission from commit `c495d1d6a` is adopted. Exactness/operator
windows reserve lane A; W2m, WSs and WS128 hold the whole host. A concurrent
lane-B screen must use the new `screen/v3-packet64-lanes` companion so it
honors the hold flag. Both sides retain private driver homes, fixed masks,
PID/start-time and fdinfo checks, READY checks and shared drain spacing.
This integration has CPU tests only; live overlap is still unmeasured.

CPU evidence: [validation manifest](cpu-validation.json),
[113 tests and seven subtests](evidence/final-tests.log),
[target and draft gates](evidence/cpu-gates.json),
[both memory placements](evidence/memory-admission.json),
[full path checks](evidence/input-checks.json).
Target fixtures match packet56, two fresh draft runs agree for every kernel
selection, and all 32 plans pass (eight selections × two lanes × two wrappers).
Owned build/selection files occupy about 352 MB, counting hardlinks once.

[Coordinator commands](WINDOW.md), [submission tools](SUBMISSION.md),
[retention and restoration](RETENTION.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md),
[do-not-repeat](DO-NOT-REPEAT.md), and
[task note](../../../../notes/2026-10-17-own-runtime-packet64.md).
