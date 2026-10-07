# Sparse-state screen: wide-table signal requires replication

All four trials in the [frozen screen](2026-10-07-sparse-state-development-plan.md)
completed. The independent native audit finds:

| Counters | Method | Answers | Exact checkpoints | Total elapsed |
| ---: | --- | ---: | ---: | ---: |
| 8 | Archive | 23/24 | 17/17 | 316.8 s |
| 8 | Quoted events | 24/24 | 17/17 | 349.1 s |
| 128 | Quoted events | 24/24 | 24/24 | 397.3 s |
| 128 | Archive | 24/24 | 24/24 | 507.5 s |

All 155 calls report zero cached tokens. All 82 original deliveries and state
checkpoints are exact, and all 232 accepted quoted events match reference
counter, operation and amount in order. There were no checker refusals or
bounded trial failures.

The 128-counter pair meets its registered replication trigger: quoted events
used **21.7% less total elapsed time**, calculated as `1 - quoted/archive`.
This is one paired observation on one server and one generated task. No speed
gate or holdout admission follows from it. The eight-counter pair fails paired
quality and supplies no qualifying timing comparison.

## What accounts for the difference

At 128 counters, initialization cost was almost equal: 54.7 seconds quoted and
53.5 seconds archive. During the next sixteen batches, quoted events took 33.3
seconds and emitted 3,296 completion tokens; archive took 156.4 seconds and emitted
21,713 tokens rewriting its table. Answering still dominated: 308.4 seconds
quoted and 296.7 seconds archive, sixteen calls each. These are client-call phase
sums; the headline total above also includes non-call overhead.

At eight counters, archive returned 56 for `unitaf10` at the end of batch 12;
the correct value is 30. Its accepted table at that time was correct. The error
arose during final reconstruction from source text. Correct state retention is
therefore separate from correct final use of that state.

The question coverage is a material limitation. In the eight-counter task,
13 of 16 historical/ownership answers differ from the corresponding final
counter value. In the 128-counter task, only 2 of 16 differ. Copying current
values can therefore answer most of that task's historical questions. This is
a useful wide-table output-cost screen, but weak evidence for temporal reasoning.
The sizes use different streams and question difficulty; their contrast does
not isolate state size. This post-run [coverage analysis](../data/2026-10-07-sparse-state-result/question-coverage.json)
does not alter the frozen questions or their gate.

## Evidence and next action

[Independent audit](../data/2026-10-07-sparse-state-result/audit.json),
[host audit](../data/2026-10-07-sparse-state-result/diagnostic-host-audit.json)
and [inventory](../data/2026-10-07-sparse-state-result/inventory.json) bind all
native JSON call, trace and result evidence. `canonical-stores.tar.gz` preserves
the four SQLite stores; each archive member was byte-compared against its source.
Copy the result directory to a temporary location, extract that archive there,
then run `scripts/context/audit_sparse_v1.py --out <copy>` from this lane. This
restored-copy audit was rerun and matched the original findings exactly.
Full host output remains `/mnt/fast-ai/bench-results/context-sparse-v1-20261007`.

Standing strict qualification passed 12/12. The owned server stopped cleanly at
05:57:49 UTC; card release was verified at **05:58:40 UTC**, and postflight health
passed. No resident server remains. No reboot, reset or host-setting change occurred.

The registered next action is the separate [replication plan](2026-10-07-sparse-state-replication-plan.md):
repeat the original 128-counter task on a fresh server with reversed method
order, then test a prospectively fixed new seed and dispatch style. The prepared
historical-state lookup remains CPU-only until that decision path is resolved.

