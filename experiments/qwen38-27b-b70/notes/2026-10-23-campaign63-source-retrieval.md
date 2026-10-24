# Campaign 63: acquire earlier source evidence before reviewing notes

Registered after campaign 62's completed audit, before any campaign-63 model call. The reviewer
sometimes invents identity from processing order when the original delivery lies outside its cut.
Test a bounded acquisition step instead of another instruction rewrite or larger reasoning cap.

## Inputs and controlled change

Use the same six frozen campaign-60 candidates and campaign-62 current evidence projection. Final
reviewer instructions, sampling, 8,192-token cap, off/on modes and ordering remain unchanged. Add only
one `retrieved_source` field to the final evidence packet, identical across the two reviewer modes.

For each candidate, one neutral thinking-off planner sees the existing packet plus the availability
of earlier history. Output strict JSON with zero to three literal queries, each nonempty and at most
96 characters; 512-token cap, no retry or adaptive follow-up. No task-specific names or expected answers
are embedded in the planner instruction. Empty queries are a valid no-acquisition outcome, not an
oracle fallback. Invalid or truncated plans fail the dependent pair and remain in the result matrix.
Transport failure aborts the diagnostic.

Search physically frozen archive prefixes ending at the fixture's `prior_upto`: 438 for the preceding
cut, 478 for observed/cancellation. Source hashes bind the original archive and prefix projections.
Preserve all roles/messages/IDs/content/calls/results; remove only the same two assistant reasoning
fields as campaign 62 and regenerate search text. No future messages, later NOTES, grader, historical
reference answer or synthetic future action enter the archive.

Use existing `Archive.recall` with escaped literal patterns, absolute message numbers, six hits/query,
and a separately enforced 2,400-character response limit per query, 7,200 combined. No `message=` or
`notes_at`: the former does not enforce `before` or `max_chars`. Disclose omitted hits, host clipping,
and the searcher's 300-character matching-sentence crop. These are excerpts, not complete-source claims.
The planner chooses all queries before seeing any result. No task tools execute.

One fresh c59-identity two-card Qwen3.8-27B FP8 server, full-precision KV. At most six short planning
calls plus twelve reviews; final reviews retain medium effort/temperature zero, no fallback or retry.
Expected diagnostic 13–16 minutes including startup (prediction, not measurement); 30-minute client cap.

## Predictions and decisions

Hypothesis: the planner retrieves the original delivery evidence for disputed identities in both
observed cases, and thinking-on reviews stop asserting the wrong identity without losing the real
audit receipt or pending work. This tests acquisition and use separately:

1. Record exact queries, source cutoff, returned message references, omissions, bytes and hashes.
2. Audit whether relevant original evidence was actually acquired; do not score retrieval only by
   the final answer or silently inject a missing query.
3. Apply the unchanged broad source-quality gate to every final condition: identities, omitted work,
   required-record defects, authorized instructions, genuine cancellation, and explicit uncertainty
   when available evidence is insufficient. Cap or plan failure counts as failure.

One mode passes all six: register fresh confirmation, then transfer if confirmed; no adoption from
this replay. Sources not acquired: diagnose query selection. Sources acquired but contradictions
persist: diagnose evidence use; do not add retrieval breadth or more context reflexively. Partial
benefit remains partial, and all misses stay recorded. No unconditional production checker or speed
claim; retrieval and review overhead must later earn their place in an end-to-end task.

## Operation

[Probe](../scripts/context/note_evidence_retrieval_probe.py),
[runner](../scripts/context/run_campaign63.py),
[prefix fixtures](../data/2026-10-23-note-evidence-archive-prefixes/).
CPU checks must prove physical future exclusion (including a future-only sentinel), literal regex
handling, exact projection, attributed snippets, hard reply bounds, equal retrieval across modes,
and that the final request changes only by the extra evidence field. A hash-bound independent review
is required before launch. Prior servers must be stopped; existing memory/fault guards and graceful
shutdown stay. No extra agents/tests/builds while the model runs and no resident server at the end.

Unit `ctx-campaign63`; raw result `context-longrun-20261016/c63-K32V-check-s0.json`; receipts under
`context-longrun-20261016/campaign63-note-source-retrieval/`. Parent remains active for completion audit.
