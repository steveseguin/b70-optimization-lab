# Campaign 63 — retrieving an original receipt does not ensure faithful notes

<!-- campaign-closeout -->

## Question and identity

One bounded literal-query planner per frozen candidate, followed by the unchanged campaign-62
reviewer with only a retrieved-source field added. Six plans, twelve reviews, no retries or fallback.
Physical earlier-archive prefixes prevent future leakage; current observations remain available.
Same two-card Qwen3.8-27B FP8 server, full-precision KV, medium effort, 8,192 review output cap.
[Registration](2026-10-23-campaign63-source-retrieval.md). October 23, 21:29–21:41 EDT.

## Outcome

**No qualified mode: broad source gate 0/12.** Eight valid deltas; four capped replies remain
unapplied. Six valid query plans include two permitted empty plans. Twelve queries return seven
positive snippets and five correctly bounded misses. Only two distinct original receipts are
acquired: ticket 38 polynomial_eval and ticket 41 nth_or_last. No plan acquires ticket 39's receipt.

The six plans plus twelve reviews take 487.663 seconds of calls. This diagnostic neither measures
agent task completion nor establishes a speed result. No reviewer or source projection is adopted.

## What worked

One thinking-on review uses the original ticket-41 receipt to correct campaign 62's invented
identity. Earlier-source acquisition can resolve a particular uncertainty. The receipt boundaries,
literal search behavior and output clipping are independently checked, including control characters.
The two empty plans are valid: their relevant observations already occur in the current source cut.

Server shutdown is confirmed, minimum available RAM 2.71 GiB, no matching kernel faults.
Full requests, responses, acquisition results and source-grounded verdicts are retained.

## What failed or remains uncertain

One completed reviewer reads the retrieved ticket-38 receipt and writes **ticket 39 polynomial_eval**.
Another reasserts the inherited ticket-38/distribute claim despite the original receipt contradicting it.
These are failures to use acquired evidence, not merely missing retrieval. Completed responses still
omit observed defects or required-record problems; every completed condition fails the broader gate.

Searching an archive ending at message 478 for tickets 43/44 correctly returns nothing. Their actual
receipts at 484/488 are already in current source; a bounded search miss cannot refute those observations.
Unretrieved ticket-39 identity remains legitimately uncertain. The audit does not require the reviewer
to know evidence it never received. Four partial replies are not counted as successful corrections.

## Evidence and patches

- [Source audit](../data/2026-10-23-context-campaign63/source-audit.json),
  [complete results](../data/2026-10-23-context-campaign63/results.json.gz),
  [retention hashes and restore command](../data/2026-10-23-context-campaign63/retention.json).
- [Server state](../data/2026-10-23-context-campaign63/server-health.json),
  [independent preflight](../data/2026-10-23-campaign63-preflight/review.json).
- [Probe](../scripts/context/note_evidence_retrieval_probe.py),
  [runner](../scripts/context/run_campaign63.py),
  [frozen-prefix provenance](../data/2026-10-23-note-evidence-archive-prefixes/manifest.json).

Raw receipts remain under `context-longrun-20261016/campaign63-note-source-retrieval/` and
`c63-K32V-check-s0.json`; retained gzip restores the original result exactly.

## When to revisit

Close the campaigns 60–63 replay sequence. No larger prompt, cap sweep or automatic reviewer adoption.
Return to the [full pi task](2026-10-23-campaign64-current-pi.md) with current ctxkeeper and explicit
notes thinking on. Its actual new trajectory determines whether the historical failure still occurs
and which practical failure deserves the next intervention. This baseline does not promote the checker.
