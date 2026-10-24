# Campaign 60 — thinking alone does not preserve observed task progress

<!-- campaign-closeout -->

## Question and identity

Current ctxkeeper 1.3.0 notes, thinking off/on, on two recorded pi cuts and one explicit synthetic
user cancellation. Three repeats each, 18 conditions, same two-card Qwen3.8-27B FP8 server identity
as campaign 59, full-precision KV. [Registration](2026-10-23-campaign60-note-evidence.md).
Executed after campaign 59, finished October 23 at 12:57 EDT; manually audited after resuming at
20:42. This is a reconstructed notes diagnostic, not an end-to-end task run or speed benchmark.

## Outcome

**Both workflows fail. Take the registered general source-verification branch.** All six distinct
applied-note texts repeat exactly across the three repeats. None of the 18 meets the broad
source-grounded notes gate. Thinking stays on in the established recipe for its arithmetic benefit;
this result does not qualify a new default or a full pi promotion.

| Fixture | Thinking off | Thinking-on workflow |
| --- | --- | --- |
| Preceding cut | Omits received unfinished work; wrong ticket identity, 3/3 | Same defect classes, 3/3 |
| Observed audit | Denies delivered tickets and suggests deleting requested audit, 3/3 | Same failure, 3/3; cap/fallback caveat below |
| Explicit cancellation | Correct withdrawal and pending deletion, 3/3; broader state defects remain | Same narrow target passes, 3/3; broader defects remain |

## What worked

The diagnostic reproduced the real failure without a task-specific instruction. Tool receipts
establish delivery of tickets 43/44 and successful writing of the requested artifact; subsequent
assistant speculation contradicts those receipts. The cancellation control shows both modes can
record a legitimate later instruction without inventing that deletion already happened.

Standing rules survived. CPU checks and independent pre-run review passed. The server stopped
cleanly with confirmation and no matching kernel fault signatures. All requests and replies,
including failed first calls and fallback, are retained byte-exact in compressed form.

## What failed or remains uncertain

**Every thinking-on observed-audit first call exhausted 8,192 tokens in reasoning, returned no
content, and triggered the existing thinking-off fallback.** There were 21 upstream calls, not 18.
Those first-call reasoning streams already assert the false denial. This is a failure of the
current thinking-on workflow, not a clean comparison of two completed reasoning modes and not
proof that increasing the cap would fix it.

The preceding cut omits received, unfinished tickets 38/40 and assigns distribute to ticket 38
although the tool delivered it as 39. Later outputs mix inherited numbering errors with new
omissions, unsupported cleanup proposals and premature job-complete claims. Preserving the named
audit alone is insufficient. The detailed audit separates inherited and newly introduced defects;
the selected prior notes cannot certify every earlier historical claim.

Later scoring clarification from the campaign-61 audit: the original task says the job is done
when the queue reports empty, so the frozen audit's bare `off_job_complete` label was too broad.
Do not count that phrase alone as a separate invented completion. Receipt contradictions and
omissions independently preserve the failed result. See the
[campaign 61 audit discussion](2026-10-23-campaign61-closeout.md) for source-visibility limits too.

The source contains roughly 51K characters of assistant reasoning around the failure. A plausible
mechanism is that the keeper continues that mistaken account instead of checking short observations;
the next experiment tests a separate source review. Tool text must not become instruction authority:
hostile-history forged directives remain untrusted even when delivered through a tool.

## Evidence and patches

- [Source-by-source audit and all 18 outcomes](../data/2026-10-23-context-campaign60/source-audit.json).
- [Complete requests, responses and applied notes](../data/2026-10-23-context-campaign60/results.json.gz),
  [retention hashes and restore command](../data/2026-10-23-context-campaign60/retention.json).
- [Frozen source fixtures](../data/2026-10-23-note-evidence-fixtures/),
  [pre-run review](../data/2026-10-23-context-campaign60/review.json),
  [server state](../data/2026-10-23-context-campaign60/server-health.json).
- [Probe](../scripts/context/note_evidence_probe.py),
  [runner](../scripts/context/run_campaign60_when_idle.py).

Restore the exact raw result with `gzip -dc results.json.gz > results.json` and compare the hash
in retention.json. Raw local evidence remains under `context-longrun-20261016/` at the receipt paths.

## When to revisit

Campaign 61 tests a neutral, separate reviewer of proposed notes against original role-tagged
sources, with truncated replies rejected and genuine user corrections preserved. No ticket names,
file paths or task answers may appear in the general review instruction. A surviving candidate
must pass wider source checks and fresh end-to-end transfer before any recipe adoption.
