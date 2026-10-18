# Packet121 decisions

Read [BUDGET.md](BUDGET.md) and its hash-bound inventory of every existing
DO-NOT-REPEAT ledger before opening another arm. These decisions do not change
the frozen ledgers or reopen their closed work.

| Idea | Decision and reason | Revisit condition |
| --- | --- | --- |
| Move draft to rank0 | Closed by packet79; misses gained work and overall speed lost. | A different dependency graph with matched evidence, not this table patch. |
| Depth-two speculation | Closed by packet66/71 lineage. | New preregistered mechanism, not more guessed-token reuse. |
| Use rank1's wait for the next exact draft | Inputs are not ready: the next token/final target state depend on its corrected half. | A proof of different available exact inputs. |
| Reuse wrong-token layer outputs | Embedding/PLE changes propagate through all target layers. | Prove a specific token-independent value, not a whole layer. |
| Omit more restore bytes or arbitrary double buffers | Canonical tails, terminal rollback and prepared pointers remain observable. | A complete ownership/terminal-state proof before implementation. |
| Reverse capture descriptor table | Implemented, CPU checks in progress; device effect unknown. | The sealed smoke, then the conditional bracket. No geometry sweep. |
| Treat miniature MTP as miss coverage | Its 64-token run has no misses. | Use explicit scripted misses in the real controller and verify counts. |
| Zero verification slot at fixture position0 | Cancels the fixture's speculation; production never speculates that position. | Retain the explicit absent-publication sentinel for this edge test. |

The long CPU byte gate uses one OpenMP thread and a 900-second per-process
bound after the default-thread run exceeded 300 seconds. Preserve its logs;
do not turn that harness timeout into a model or device failure claim.
