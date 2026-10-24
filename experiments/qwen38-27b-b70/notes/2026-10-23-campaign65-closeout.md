# Campaign 65 — correct audit proposal, incomplete original-receipt coverage

<!-- campaign-closeout -->

## Question and identity

Replay the actual campaign-64 audit request through the production keeper using its frozen earlier
archive and notes. Compare the original memory instruction with one generic suffix: notes are
selective, and exhaustive historical requests need original evidence and coverage checks.
[Registration and exact suffix](2026-10-23-campaign65-history-coverage.md). This is reconstructed
state, not a claim of historical wire-byte identity. One fresh c59-identity two-card Qwen3.8-27B FP8
server with full-precision KV; October 23, 22:42–22:46 EDT.

## Outcome

**Partial success; strict source-evidence gate fails.** Control reproduces the original three-line
proposal exactly, with no recall, 19 messages and 6,026 prompt tokens. The candidate proposes all
seven correct audit lines after one archive recall. However, it retrieves only the four missing
original receipts. Entries 6–8 still come from correct supplied notes, so the stricter recorded
requirement that retrieved original receipts cover all requested entries is not met.

No file is written and no external task tool executes. This is a proposed action, not a full-task
score. Neither production adoption nor a complete-evidence qualification follows.

## What worked

The first candidate request differs only by the registered system-memory suffix, adding 80 prompt
tokens (6,106 total). The candidate explicitly notices the missing ticket range and searches
`TICKET (1|2|4|5)/`. Original messages 5, 14, 25 and 32 supply split_at, sample, substrings_indexes
and ichunked. Those are exactly the four omissions in campaign 64's final audit.

Together with the three correct notes-derived identities, the proposed file is exactly 7/7 with
no extra entries. The change demonstrably repairs this gap in the proposed answer. It does not
demonstrate that the model verifies every surviving note against an original receipt.

All three calls finish with tool calls; no output cap is hit. Source/fixture hashes, cutoff,
suffix-only capture and control reproduction pass independent review. Shutdown is clean, no
restart, OOM or kernel fault; minimum host memory is 2.565 GiB.

## What failed or remains uncertain

The model interprets coverage as filling missing entries while trusting the entries already in
notes. The complete-evidence behavior specified by the strict source gate remains unproved and
fails this particular test. Do not retrospectively weaken that gate to call the experiment a pass.

Arm wall times are 12.504 s for control and 5.883 s for candidate; the candidate's second call reuses
5,824 cached prompt tokens. These are diagnostic costs, not a speed comparison. Individual call
latencies were not retained. Full-task execution, earlier trajectory effects and other histories
remain untested.

## Evidence and patches

- [Source audit](../data/2026-10-23-context-campaign65/source-audit.json),
  [provenance audit](../data/2026-10-23-context-campaign65/provenance-audit.json),
  [complete requests/responses](../data/2026-10-23-context-campaign65/results.json.gz),
  [retention receipt](../data/2026-10-23-context-campaign65/retention.json).
- [Independent preflight](../data/2026-10-23-campaign65-preflight/review.json),
  [frozen fixture](../data/2026-10-23-campaign65-fixture/retention.json),
  [probe](../scripts/context/main_history_contract_probe.py), [runner](../scripts/context/run_campaign65.py).
- [Server state](../data/2026-10-23-context-campaign65/server-health.json),
  [preceding exact-tree publication receipt](../data/2026-10-23-context-campaign65/preceding-publication.json).

Raw receipts remain under `context-longrun-20261016/campaign65-history-coverage/` and
`c65-K32V-check-s0.json`. The local GitHub CLI credential failed; the authenticated GitHub app
published the preceding reviewed file trees with a fast-forward lease and no force update.

## When to revisit

Close this decisive-turn diagnostic without another prompt, scope or cap sweep. The separately
registered [campaign 66](2026-10-23-campaign66-full-pi-contract.md) is an exploratory fresh full-task
trial motivated by correct gap repair. It is **not** confirmation of a passed complete-evidence gate.
It measures whether the same instruction improves the actual final artifact while preserving repairs
and standing rules. A passing practical score still cannot qualify universal historical coverage.
