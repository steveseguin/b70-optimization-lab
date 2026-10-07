# Durable revision 2: protocol completes, answer quality still fails

The [repair plan](2026-10-07-durable-context-r2-plan.md) was implemented,
independently reviewed, frozen and run. All six development trials completed
with explicit submissions covering all 24 questions. The full quality gate failed,
so **none of the fresh held-out seeds was used and no speed result qualifies**.

| Method | Report style | Dispatch style | Total |
| --- | ---: | ---: | ---: |
| Summary | 19/24 | 17/24 | 36/48 |
| Model-maintained table with archive | 24/24 | 16/24 | 40/48 |
| Quoted events with code-maintained table | 24/24 | 17/24 | 41/48 |

These are seed-7 development results on two authored synthetic styles. They are
not independent held-out replications or directly comparable to the spent seeds
from the first pilot. The model/server profile, tasks, sources and budgets were
fixed before requests. This was one server and one clean campaign attempt.

## What was repaired and verified

The separate `durable_v2` harness preserves the first pilot unchanged. Partial
answers survive retrieval and restart; complete explicit submission replaces
implicit finalization. Exact batch fetch and digit-bounded search avoid the
batch-2/batch-20 collision. Cached repeats restore evidence; 32 reserved answer
calls and 24 distinct retrieval operations bound the loop. Saved answers and
questions remain visible. Review also fixed evidence eviction and missing-batch
budget accounting before the source freeze.

77 harness tests and 24 host-runner tests passed. The historical harness (58),
exporter (9) and old host runner (20) also passed. Both new frozen plans match
source/task bytes; documentation and manifest paths have no missing links.
The historical global pin baseline remains 87 matches, 231 drifted, zero absent.

The actual server passed 12/12 exact reference-output checks and full standing
qualification. Both fixed extraction diagnostics passed at 100% precision,
recall and event order. Development used the same server, thinking off and a
32,768-byte working prompt budget. The full matrix completed without resumption. An independent read-only database
check found all 288 source batches byte-exact; all 192 structured-table checkpoints
were exact. Saved sessions match submitted answers, and native answers were
regraded against the frozen tasks. Mixed answer/retrieval responses remained
intermediate steps, and no answer calls reported transport failures.

## What remains wrong

The dispatch archive trial kept the current counter table exact at every batch,
but substituted current balances into several end-of-batch-2 questions. It also
shifted retrieved seal values between question IDs. Its final answer included
every ID, so this is no longer the old premature-finalization defect. The quoted
method exhibits the same class of final-answer errors. Exact arithmetic and
source retention alone do not ensure the model associates evidence with the
right time and question.

The report summary trial submitted immediately without retrieval, getting two
current balances and three historical cross-references wrong. Durable access
cannot help when the model trusts an incorrect summary and does not consult it.

The next development lever should address final-answer reasoning: first compare
a bounded reasoning budget during the answering phase, keeping ingestion,
retrieval permissions and tasks fixed. Then consider explicit evidence attached
to each answer or historical table lookup if reasoning remains insufficient.
Any such work needs a separate revision and frozen plan; do not edit this run's
sources or relax its failed gate after seeing the outcome. Keep the new holdout
unused until the declared development condition is met. Larger streams and
speed tuning remain deferred.

## Evidence

Native results, answer-phase calls, saved sessions, strict/extraction receipts,
source-integrity checks and cleanup receipts are preserved in
[the revision 2 audit](../data/2026-10-07-durable-r2-result/audit.json).
Full local output: `/mnt/fast-ai/bench-results/context-durable-r2-20261007`.
The lifecycle reports a development-quality failure; that is the intended stop
condition, not a server crash. The server stopped at 03:51:33 UTC and GPU release was confirmed at
03:52:28 UTC. No server or new GPU run remains active or queued.
