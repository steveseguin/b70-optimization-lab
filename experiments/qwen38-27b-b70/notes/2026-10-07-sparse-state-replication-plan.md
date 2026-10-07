# Sparse-state replication and transfer, version 1

Prospective plan, 2026-10-07, after the [initial screen](2026-10-07-sparse-state-result.md)
completed and independently passed its registered replication trigger. The owner
has asked work to continue. This is a new four-trial development campaign, with
no changes to the old screen, its engine, packet, score or gate.

## Fixed matrix and provenance

Use one fresh server and exactly this order:

1. Original 128-counter seed-83 report, archive.
2. Original 128-counter seed-83 report, quoted events.
3. New 128-counter seed-97 dispatch, quoted events.
4. New 128-counter seed-97 dispatch, archive.

The original document and compiled task are copied byte-for-byte from the frozen
sparse-state packet; do not regenerate them under changed metadata. Reversing
their original method order gives the original task a second-server observation.
The new case changes seed and writing style together: it tests transfer to one
new case, not an isolated causal effect of prose style or independent replication
of the original stream.

Keep 128 counters, eight initialization batches of sixteen explicit settings,
then sixteen batches with three postings each, 320 filler words per batch,
eight current questions, eight historical balance questions and eight ownership
joins. Preserve the untouched-counter control and the same prospective question
selection rule. Use explicit replacement balances, posted credits and posted
debits in dispatch wording; introduce no aliases, negations, draft corrections
or implicit operations. The fixed seed is 97; do not search seeds for quality or
cost after seeing model results.

Separate source parsing must reconstruct all 176 events, every full state,
ownership/review links and all answers from emitted text. Reject unrecognized
posting lines. This programmatic reference is not independent human annotation.
Report how many historical answers differ from final values in both cases. The
original task has only two such answers among sixteen historical/ownership
questions; this weakness remains visible and is not repaired retrospectively.

## Protocol and measurement

Reuse the exact frozen semantic trial engine through an isolated worker. The
new outer schema identifies replication/transfer provenance; its native semantic
schema is compatibility metadata. No historical-state lookup is available.

Keep the 32,768-byte serialized prompt limit, 6,553-byte memory limit, three
ingestion attempts, thinking-disabled 4,096-token ingestion and medium-thinking
8,192-token answering. Keep 24 successful distinct retrievals and 32 answer
calls. No continuation, cap increase, resumed trial or transport retry. Before
model execution, verify actual serialized prompt and reference-response token
fit with the local tokenizer, including initialization. Reference fit is CPU
validation, not a guarantee of model completion.

Quality requires every state checkpoint exact, final 24/24 answers, complete
unresumed trials and, for quoted events, every accepted event matching the
reference counter/operation/amount sequence. Preserve refused attempts and count
all their cost. Retain each bounded model failure and continue the other fixed
trials. Infrastructure failure aborts the campaign and retains unstarted rows.

Record total elapsed time, all calls, tokens and initialization/steady/answer
costs. Only fully exact paired outcomes with known zero cache tokens on every
call permit a descriptive elapsed comparison. The original-task repeat succeeds
as a replication signal only if it again has at least 10% less total elapsed
time for quoted events: `quoted <= 0.9 * archive`. Apply the same descriptive
criterion separately to the new case. Do not pool timings across tasks or
discard a slow/failed row. A repeated original-task signal remains scoped to
that generated task; the new style has only one server observation. Neither
opens a holdout or establishes a general performance claim.

## Lifecycle and next decision

Output: `/mnt/fast-ai/bench-results/context-sparse-replication-v1-20261007`.
Unit: `ctx-sparse-replication-v1.service`. Use the same unchanged target model,
full-precision KV and cache-disabled profile, with twelve-case strict admission.
Bind this plan, packet, wrapper, frozen dependencies and launch identity before
starting. Require the prior four-outcome audit, its true 128-counter replication
signal, confirmed STOP/card release on this boot, and an idle healthy host.

One supervised owner holds the established locks and owns every launch, client
and graceful cleanup. No resident service, restart loop, reboot, driver reset,
power, swap or page-cache change. Freeze implementation only after CPU tests and
independent review; a plan file alone is not launch admission.

If both cases are exact, cold and meet the elapsed criterion, prepare confirmation
of the new style on another fresh server plus separately authored development
documents before broader claims. If the repeat or transfer loses accuracy or the
material cost signal, preserve it and move to the already CPU-tested shared
historical-state lookup. That next study needs its own prospective comparison;
it must use each method's actual saved values, never grading answers.
