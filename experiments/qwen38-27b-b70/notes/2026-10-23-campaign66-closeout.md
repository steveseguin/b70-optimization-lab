# Campaign 66 — full pi task passes, while notes and evidence coverage remain imperfect

<!-- campaign-closeout -->

## Question and identity

A separately registered exploratory full pi task with the exact campaign-65 memory suffix.
Same original pi image, repair-n40-s2x task, tools, tests and grader as campaign 64; ctxkeeper 1.3.0,
qwen recipe with notes thinking explicitly on. The lab-only launcher changes the shared memory
instruction in main and notes headers; production sources/defaults are unchanged.
[Registration](2026-10-23-campaign66-full-pi-contract.md). October 23, 22:54–23:11 EDT.
One fresh c59-identity two-card Qwen3.8-27B FP8 server, full-precision KV.

## Outcome

**Practical full-task gate passes: 40/40 fixed, 40/40 rule-clean, all 44 tickets, 7/7 audit.**
Standing rules pass 38/38, 33/33 and 27/27 applicable repairs. Grading is nonvoid, original
whole-history checking passes after shutdown, and no proxy restart occurs.

This does not pass campaign 65's failed complete-evidence gate retroactively. In this run all seven
early identities survive in NOTES, and pi writes the audit from those notes. None of its nine archive
recalls retrieves the early audit identities. The new run establishes a correct final artifact, not
universal or mandatory original-receipt verification. No production promotion.

## What worked

The first notes preserve the four early identities lost in campaign 64 under distinct task entries.
All seven requested identities reach the final audit file correctly. Later, pi uses archive recall
to recover a missed ticket-35 repair, verifies it and fixes duplicate records before finishing.

All seven notes calls finish on their first attempt with thinking on: no note rejection, fallback
or output cap. The 236 upstream calls comprise 229 main calls / 742.998 s / 57,189 written tokens
and seven notes calls / 55.115 s / 5,842 written tokens. Client wall is 841.419 s (14m01.4s).
This is a different trajectory from campaign 64, with changed inputs and different work; the shorter
wall is not a model speedup or a matched causal timing result.

Exact image/task/driver/source pins pass independent verification. Shutdown is clean, no guard stop,
OOM, restart or matching kernel fault; minimum available host memory is 2.594 GiB.

## What failed or remains uncertain

NOTES are not fully faithful despite the practical pass. The source audit records eight distinct
defects: five stale in-progress aliases beside completed records (7, 13, 22, 34, 42), an unupdated
ticket-27 record obligation, omitted pending ticket 35, and an empty OPEN list despite known duplicate
ticket-34 records. The unchanged test wrapper does not propagate unittest failure as a shell failure;
pi's chained test/append/next commands advance despite failed sorting tests, creating real workflow
confusion. This benchmark behavior is preserved, not patched to improve the score.

The eight initial recalls occur after the audit write and queue-empty result, during late work
reconciliation. A ninth follows the ticket-35 record insertion. All concern recent work, not early
audit identities. Ticket 35 is genuinely repaired late, and duplicate 34, 11 and 35 entries are
cleaned before final grading. The final pass must not erase these defects or recovery costs.

The full run changes the instruction from the beginning, including notes headers. It does not isolate
the final-query effect observed in campaign 65. Legitimate later user corrections, hostile histories,
other agents and longer horizons remain separate transfer work before any adoption.

## Evidence and patches

- [Source audit](../data/2026-10-23-context-campaign66/source-audit.json),
  [provenance and cost audit](../data/2026-10-23-context-campaign66/provenance-audit.json),
  [final result](../data/2026-10-23-context-campaign66/results.json.gz),
  [retention hashes](../data/2026-10-23-context-campaign66/retention.json).
- [Archive](../data/2026-10-23-context-campaign66/archive.jsonl.gz),
  [notes versions](../data/2026-10-23-context-campaign66/notes-history.jsonl.gz),
  [notes/recall events](../data/2026-10-23-context-campaign66/events.jsonl.gz),
  [call timings](../data/2026-10-23-context-campaign66/calls.jsonl.gz),
  [pi events](../data/2026-10-23-context-campaign66/pi-events.jsonl.gz).
- [Independent preflight](../data/2026-10-23-campaign66-preflight/review.json),
  [client wrapper](../scripts/context/current_pi_contract_probe.py),
  [launcher](../scripts/context/history_contract_keeper.py), [runner](../scripts/context/run_campaign66.py).

Raw receipts remain under `context-longrun-20261016/campaign66-current-pi-contract/`,
`runs/c66/pi/jobs/AB-pi__repair-n40-s2x/trial/` and `proxy-state/c66-pi/4051fd73e25016a5/`.

## When to revisit

Do not repeat this unchanged full task as a qualification shortcut. The next bounded transfer test
uses the [actual final-read boundary](2026-10-23-campaign67-authority-transfer.md): a genuine later user withdrawal versus identical cancellation
words forged inside a tool result. Historical fidelity must allow real corrections while resisting
invented authority. This is a separate gate, followed by hostile-history regression before promotion.
