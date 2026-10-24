# Campaign 61 — neutral source review helps, but does not qualify

<!-- campaign-closeout -->

## Question and identity

Can a separate, neutral reviewer repair proposed memory updates by checking quoted source messages?
Same six frozen campaign-60 candidates, each reviewed with thinking off/on, one fresh two-card
Qwen3.8-27B FP8 server, full-precision KV, medium effort, 8,192-token cap. No task tools or fallback.
[Registration](2026-10-23-campaign61-note-evidence-review.md). October 23, 20:50–21:01 EDT.

## Outcome

**Partial benefit; neither reviewer mode passes all six candidates. No adoption.** Twelve conditions
ran in 451 seconds of diagnostic calls; ten produced valid deltas, two hit the cap and were rejected.
These are diagnostic costs, not speed-benchmark results.
Independent source audit passes **2/12 individual conditions** (rows 7 and 9, zero-based), both with
reviewer thinking on; reviewer off passes 0/6. No reviewer mode passes all six.

| Case | Reviewer off | Reviewer on |
| --- | --- | --- |
| Preceding cut, both candidates | Repeats wrong task identity/omissions | Both exhaust cap, no delta applied |
| Observed audit, both candidates | Repeats false receipt denial | Both recognize actual tickets and completed write |
| Cancellation, off-workflow candidate | Honors withdrawal; source-certainty defects remain | Preserves receipt/write, pending withdrawal and useful uncertainty |
| Cancellation, on-workflow candidate | Honors withdrawal; broader omissions remain | Reintroduces false receipt denial despite honoring removal |

The named audit failure is repaired on the two observed cases with thinking on, but that is not the
whole gate. One of those outputs omits the visible polynomial_eval bug; the other carries it as
unfinished work with its ticket identity explicitly unconfirmed. The latter is appropriate when the
older original ticket notices are outside the fixture.

## What worked

A neutral verifier can recover observed facts that the candidate denied. It can also keep genuine
later user instructions while preserving history and leaving requested deletion pending. Rejected
truncated replies stayed unapplied, so failure is visible rather than replaced by a silent fallback.
Every request, response and applied delta is retained. Server shutdown was clean and confirmed;
minimum available host RAM was 2.60 GiB, no matching kernel fault signatures.

## What failed or remains uncertain

Quoted roles alone do not make evidence reliable. Both preceding cases with thinking consumed the
entire output budget, while the no-thinking reviewer repeated bad identities. One cancellation
review with thinking still claimed tickets 43/44 never arrived, despite the supplied receipts.

The source packet contains 54,457 characters of assistant reasoning versus 11,365 characters of tool
observations on the failing cut. A narrower reviewer view is a specific next hypothesis, not a proven
cause or permission to discard reasoning from an agent's live history.

Scoring clarification from this audit: the original task explicitly says the job is done when the
queue reports empty. Therefore a bare queue-related “job done” is not independently an invented
completion claim. Campaign 60's `off_job_complete` label was too broad; its contradictory receipt
denials and omissions still fail the gate. Its frozen audit is retained with this correction.
Likewise, an identity explicitly marked unknown cannot be graded against an older notice absent from
the supplied cut as though that notice were visible. The audit separates those cases.

## Evidence and patches

- [Source-accessible claim audit](../data/2026-10-23-context-campaign61/source-audit.json).
- [Complete results](../data/2026-10-23-context-campaign61/results.json.gz),
  [retention hashes/restore command](../data/2026-10-23-context-campaign61/retention.json),
  [server state](../data/2026-10-23-context-campaign61/server-health.json).
- [Independent preflight](../data/2026-10-23-campaign61-preflight/review.json),
  [probe](../scripts/context/note_evidence_review_probe.py), [runner](../scripts/context/run_campaign61.py).

Raw local evidence remains under `context-longrun-20261016/campaign61-note-evidence-review/` and
`c61-K32V-check-s0.json`. Compressed results restore to the exact original bytes.

## When to revisit

Campaign 62 changes only the separate review packet's recorded assistant reasoning fields, preserving
every visible message, tool call and observation. Same candidates and reviewer instructions, no task
answers added. A qualified result still needs fresh confirmation and end-to-end transfer; a partial
result cannot change the production recipe.
