# Campaign 62 — removing recorded reasoning repairs some cuts but loses others

<!-- campaign-closeout -->

## Question and identity

Campaign 61's twelve reviewer requests with only source-assistant `reasoning_content`/`reasoning`
fields removed. Every visible message, role, tool call/result, prior note and candidate stayed exact;
independent review restored the removed fields and matched all twelve actual campaign-61 requests.
Same two-card Qwen3.8-27B FP8 server identity, full-precision KV, medium effort, 8,192 output cap.
[Registration](2026-10-23-campaign62-observable-evidence.md). October 23, 21:06–21:18 EDT.

## Outcome

**Partial benefit, no qualified mode. Broad source gate: 0/12.** Ten valid deltas, two cap failures
rejected without fallback. Both thinking-on preceding cuts now finish and retain the two skipped
tickets and correct repair identity. Both thinking-on observed cases retain the actual audit request
and completed write. Both thinking-on cancellation cases exhaust the cap, so the gains do not extend
across the fixed diagnostic. Thinking off still fails both observed-audit targets.

Calls take 478.567 s in total, versus 451.075 s in campaign 61. These are different diagnostic
inputs on different servers; no speed verdict or adoption follows from them.

## What worked

The narrower review view resolves the preceding-cut cap problem and the main omissions/identity
error there. This is meaningful evidence about the effect of recorded reasoning. The ablation is
exactly scoped: 20 reasoning fields / 10,394 characters removed in the preceding cut; 12 fields /
54,457 characters in the observed/cancellation cut. No source observations or candidate text removed.

Full requests/responses and field-removal receipts survive. CPU tests and independent review prove
the inverse transformation. Server stopped cleanly and confirmed, minimum available RAM 2.80 GiB,
no matching kernel fault signatures.

## What failed or remains uncertain

The improved preceding outputs still omit required-record defects: the bogus distribute/window-size
record and, in one condition, duplicate convolve entries in RECIPES.txt. The audit distinguishes these
remaining omissions from the substantial core improvement rather than calling the whole cut correct.

One thinking-on observed review invents **ticket 41 = unique_in_window**, using processing order to
override prior notes that identify 41 as nth_or_last. The original unique_in_window delivery (message
472) is outside this cut but legitimately retrievable from earlier history. Both observed reviews
omit the visible polynomial_eval bug. Both cancellation reviews with thinking truncate; the last
contains only a partial new rule and is correctly left unapplied. No cap increase is justified here.

Removing recorded reasoning from the review view is lossy and does not make the remaining facts
self-verifying. The agent's live history and production notes recipe were never changed.

## Evidence and patches

- [Full source audit](../data/2026-10-23-context-campaign62/source-audit.json).
- [Complete results and removal receipts](../data/2026-10-23-context-campaign62/results.json.gz),
  [retention hashes/restore command](../data/2026-10-23-context-campaign62/retention.json),
  [server state](../data/2026-10-23-context-campaign62/server-health.json).
- [Independent preflight](../data/2026-10-23-campaign62-preflight/review.json),
  [probe](../scripts/context/note_evidence_observable_probe.py), [runner](../scripts/context/run_campaign62.py).

Raw local receipts remain under `context-longrun-20261016/campaign62-note-observable-review/` and
`c62-K32V-check-s0.json`; gzip restoration is byte-exact against the retention receipt.

## When to revisit

No more unchanged thinking on/off or cap sweeps. The next specific question is whether bounded
retrieval of earlier original observations prevents unsupported identity reconstruction. Retrieve
only history available before the cut, preserve genuine user corrections, and score acquisition
coverage separately from whether the reviewer actually uses the evidence correctly.
