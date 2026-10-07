# Full-source screen: use the simple baseline for these short documents

Both fixed requests answered all 24 questions correctly, including all ownership
joins. Supplying the entire short source used much less observed task time than
the earlier exact streaming conditions. For this static final-answer use case,
start with the complete source and stop adding retrieval-interface variants.

## Complete observations

| Document | Current | Earlier balance | Ownership join | Task seconds | Prompt tokens | Completion tokens | Reasoning tokens | Cached tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| t01-clinic | 8/8 | 8/8 | 8/8 | 27.75 | 3,300 | 3,762 | 3,438 | 0 |
| t02-theatre | 8/8 | 8/8 | 8/8 | 34.86 | 3,281 | 4,539 | 4,215 | 0 |

Exactly one request ran per document, in the fixed clinic/theatre order. Both
returned valid, complete, correctly typed submit JSON with `finish_reason=stop`.
There was no retry, continuation, truncation, budget increase or infrastructure
failure. Reported prompt counts exactly match the prospective local tokenizer
calculation. All token accounting is known and internally consistent.

The [independent audit](../data/2026-10-07-full-source-result/audit.json)
reconstructs requests and grades from the original source and references, then
checks raw response, usage, finish, timing and artifact bindings. Intermediate
checkpoint and event quality are **not measured**, represented as null. A correct
final answer is not a streaming-state guarantee.

## Descriptive cost comparison and its limits

| Document | Direct full source | Quoted, source-only | Archive, source-only |
| --- | ---: | ---: | ---: |
| Clinic | 27.75 s, 1 call | 198.67 s, 22 calls | 225.46 s, 24 calls |
| Theatre | 34.86 s, 1 call | 199.75 s, 22 calls | 205.93 s, 22 calls |

Every displayed condition answered 24/24 and every relevant call reported zero
cache reuse. The streaming columns come from the separately preserved
[history study](2026-10-07-history-state-study-result.md). Their totals include
initialization, ingestion, answering and snapshot persistence. Direct task time
starts before request persistence and ends after the raw response and result are
flushed/fsynced; endpoint exchange alone took 27.7277 and 34.8368 seconds. Its final
timing-receipt write and offline audits are outside that boundary. Packet creation
and shared server lifecycle are separate for both methods.

This is a standalone screen against earlier runs, not a matched-server speed
qualification. The direct method sees the questions with all the source. Streaming
sees questions after ingestion, has a larger total possible reasoning budget and
produces auditable intermediate state. The comparison answers a practical static
final-answer question; it does not isolate bookkeeping, match every output
obligation or justify a general speed multiplier.

The historical-access conditions are excluded from exact-quality cost comparisons:
they scored 19/24, 19/24, 19/24 and 23/24. Their correct numeric snapshots did not
prevent stale ownership joins. The simple full-source results reinforce that
retrieval machinery was unnecessary for these particular short final questions.

## Admission, preservation and lifecycle

The [separate prospective plan](2026-10-07-full-source-screen-plan.md) was written
after the first observed history failure, with the same two development documents
fixed in advance of direct-source results. This is not a holdout or a result-blind
choice of task. The sources, questions, conventions and generation policy were
unchanged. Each document contains about 1,500 source tokens; the complete requests
fit the 32,768-byte prompt cap without selection or summarization.

The implementation was frozen in `18ebff28e`. Its 12 client, 18 independent-audit
and 28 host tests passed. A complete two-stub run and relocated replay passed
without claiming model quality. All 35 guide checks passed. The supervisor binds
120 dependencies and 410 prior artifacts; these remained unchanged.

Passive admission passed at 07:38:53 UTC on 2026-10-07, after the entire negative
history study had stopped, passed health and been preserved/restored. The new
server started at 07:39:28 and was ready at 07:41:57. All 12 strict reference checks
passed; the screen began at 07:43:25 and both trials were audited by 07:44:30.
STOP was confirmed at 07:44:39, both cards were released at 07:45:31, and
healthy completion was recorded at 07:45:39. `ctx-full-source-v1.service` is now
inactive with a successful exit. No resident model service, restart or host/device
setting change remains.

The [33-file evidence inventory](../data/2026-10-07-full-source-result/inventory.json)
preserves both exact requests, raw responses, usage, timings, launch/strict and
STOP/card/health records. A separate restored copy reproduced the independent
audit exactly except its output-root path; the
[preservation receipt](../data/2026-10-07-full-source-result/preservation.json)
binds that check. The serialization conventions and exact candidate
requests remain in the [CPU feasibility packet](../data/2026-10-07-full-source-feasibility/README.md).

## Decision

The planned stopping criterion is met: both direct answers are exact and materially
cheaper in observed task cost. Close short static retrieval-interface tuning.
Keep the numeric bookkeeping engine for a separately justified streaming or
intermediate-audit requirement, rather than making it the default for small
documents. The history extension stays closed and t03/t04 remain unused.

These assistant-authored and assistant-annotated numeric documents do not establish
general factual-memory accuracy or performance beyond the actual model window.
Further work should begin with a concrete application and independently sourced
facts, or a relevant-history capacity measurement—not another seed/size matrix
of the same short controlled task. The
[research priorities and CPU reviews](2026-10-07-context-research-priorities.md)
record the representation, provenance and total-resource gaps that remain.
