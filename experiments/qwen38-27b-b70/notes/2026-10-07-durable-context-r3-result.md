# Durable revision 3: reasoning repairs historical answers; original gate fails

The owner asked to continue after revision 2. The separate
[r3 plan](2026-10-07-durable-context-r3-plan.md) enabled medium-effort reasoning
only during final answering, with an 8192-token combined reasoning/answer cap.
Ingestion, retrieval, source tasks and the original all-methods gate stayed fixed.

| Method | Report | Dispatch | Total |
| --- | ---: | ---: | ---: |
| Summary | 22/24 | 22/24 | 44/48 |
| Archive | 24/24 | 24/24 | 48/48 |
| Quoted events | 24/24 | 24/24 | 48/48 |

All six trials completed cleanly and explicitly submitted all questions. Both
structured methods answered every current, historical and cross-reference question
correctly on both styles. The summary method retained two wrong current totals
in each style. Those totals were already wrong in its notes, which it trusted
without retrieval. Both methods improved on the dispatch historical errors from
r2, but these are inspected seed-7 development results, not generalization proof.

**The registered r3 all-methods gate failed.** No held-out seed was used and no
speed result qualifies. The two styles share underlying per-seed events; do not
count them as independent natural-document samples.

The server passed 12/12 reference qualification and both extraction diagnostics.
All 288 original source batches were verified byte-exact; all 192 structured-table
checkpoints were exact. Actual reasoning fields, finish reasons and reported token
usage are preserved. There were no output-cap failures or resumed trials.
CPU validation passed 89 harness tests and 26 host-runner tests.

## Timing audit and next revision

A read-only audit found prefix-cache reuse in quoted-event answer calls. On the
report task, r2 had 12 such calls totaling 42,432 cached prompt tokens; r3 had nine
totaling 24,128. The corresponding archive calls had zero. The old campaign's
timing predicate did not inspect cache usage. Both campaigns had already failed
their quality gates, so no qualifying speed result needs withdrawal; their elapsed
comparisons additionally cannot support a cold-request speed claim. Native raw
measurements remain preserved without reinterpretation.

The next [r4 plan](2026-10-07-durable-context-r4-plan.md) uses a separately frozen
cache-disabled profile and fresh development seeds 17 and 29. It prospectively
makes archive-versus-quoted the primary pair, while retaining all summary trials
as a secondary diagnostic. This changes the scientific claim based on inspected
development findings; it does not turn r3 into a pass. Every primary answer must
still be correct and every planned trial must complete cleanly. Cache hits or
missing cache evidence block timing and fresh holdout admission. A single cold
server provides only a descriptive timing signal; independent fresh-server
replication is required before a speed verdict.

## Evidence and lifecycle

[Audited native results](../data/2026-10-07-durable-r3-result/audit.json) include
submitted answers, saved sessions, answer-call traces, reasoning/output counts,
source-integrity checks, cache totals and strict/extraction/cleanup receipts.
Full local output: `/mnt/fast-ai/bench-results/context-durable-r3-20261007`.
The owned server stopped and GPU release was verified at **04:22:53 UTC**.
The unit's failure status records its expected quality-gate stop, not a crash.
No r3 server remains running.
