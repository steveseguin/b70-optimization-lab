# Packet126 boundaries

| Closed assumption | Evidence / revisit condition |
| --- | --- |
| Moving D before the head removes D from rank1's cycle | Single CCS still executes both. With no recovered wait, misses add one wasted D and the measured-command scenario loses 1.95–1.96%. |
| The zero-wait scenario proves the lever is below 0.5% | False. Compatible unmeasured head decompositions cross the gate; the result is inconclusive, not a measured loss. |
| B minus A is available head wait | B includes remote suffix service and retirement. Require position-bound readiness/service/merge timestamps. |
| Discarding the guessed token repairs a missed early draft | DRAFT advances cache, position and async state. Require an exact private transaction, terminal rollback and forced-miss tests. |
| Start A[p+2] while A[p+1] is unresolved in the current controller | One pending candidate/snapshot; a second unresolved target half needs a separate state design. |
| Reuse packet124's device evidence for a scheduling change | A changed schedule needs its own byte/state/startup/seal gates and 12×64 smoke before a bracket. |
| Use the historical 1.4 ms head as the current split-head timer | Not measured on bundle7; no row-count scaling or invented current class time. |

[Analysis closeout](ANALYSIS-CLOSEOUT.md). Revisit with measured recoverable
wait supporting ≥0.5% after speculative-draft waste and transaction costs.
