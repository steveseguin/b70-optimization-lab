# Campaign 64 — all repairs pass, but selective notes become an incomplete audit

<!-- campaign-closeout -->

## Question and identity

The full original pi 1.2.0 repair-n40-s2x task on ctxkeeper 1.3.0, public qwen recipe with the
explicit `--notes-thinking on` override. Exact original image, task, tools, tests and grader;
no experimental reviewer or source projection. Fresh two-card Qwen3.8-27B FP8 server, full-precision KV,
MTP5, medium effort, two sequences. [Registration](2026-10-23-campaign64-current-pi.md).
October 23, 21:51–22:24 EDT. Historical campaign 20b differs in keeper and server settings and is
not a matched speed control.

## Outcome

**Practical gate fails: 40/40 fixed, 40/40 rule-clean, 3/7 audit.** All 44 tickets fetched; all three
standing rules pass (38/38, 33/33, 27/27 applicable repairs). Grading is nonvoid and the client sends
whole history. The grader's repair score of 1.0 does not include success on this separate audit gate.
The result explicitly records `complete: true` and `quality_pass: false`.

Pi writes and keeps the requested audit file, but lists only tickets 6, 7 and 8. This differs from
campaign 20b's deletion of a correct artifact: here the file is incomplete at creation.

## What worked

Every code repair and standing rule passes the unchanged grader. The late polynomial_eval,
unique_in_window and nth_or_last repairs all succeed. Apparent progress confusion observed live
around tickets 34–36 must not be called a skipped repair: final grading and source records establish
all repairs, including 35. The original image and four documented task-driver substitutions are
retained. Original whole-history checking runs only after confirmed GPU shutdown.

Agent time is 1,812 s; client wall is 1,817.522 s (30m17.5s). The 317 upstream calls comprise
294 main calls / 1,375.597 s and 23 notes calls / 393.181 s, total 1,768.778 s. These are actual call
totals, not the narrower status counters. Minimum host memory was 2.032 GiB; task peak was 331.4 MiB.
Server exit is clean with no guard stop or matching kernel faults. No model speed claim follows from this baseline.

## What failed or remains uncertain

The first persisted notes omit completed ticket 1 split_at, ticket 2 sample and ticket 4 substrings_indexes.
The raw reply mentions the first two under repeated `Ticket progress` keys; the intended one-slot-per-name
STATE merge retains only the last value. A CPU replay reproduces the saved notes exactly: representational
misuse, not a parser implementation bug. Ticket 4 is omitted from the reply itself. The notes also mislabel
active ticket 5 ichunked as ticket 4. Its later passing test does not upgrade the
stale unfinished summary; a subsequent rewrite drops it entirely. Late notes present completed work
starting at ticket 6. At the audit request, pi explicitly considers that there may have been other
early bugs, then treats the surviving list as exhaustive and writes only 6–8. It makes no audit-time
archive recall. Original evidence remains available; the agent does not consult it. The final notes also
retain stale ticket-38 pending work alongside its recorded completion; a passing repair score does not
establish internally consistent notes.

There are 19 reported cuts, 18 saved notes versions, two recalls and one reported notes failure.
Full event receipts reveal an internal thinking-off fallback despite the configured on setting:
11 in-place replies have thinking true and one has thinking false. A later full rewrite reaches its
8,192-token cap. These are unchanged keeper recovery behaviors, not a clean all-thinking-on result.
The failed ordinary rewrite still archives and advances the cut without new notes, leaving receipts
418–455 out of the live view and stale sieve work in STATE. Pi later recalls recent tickets and repairs
the bookkeeping. The successful final repair score does not make that loss harmless.

The status counters undercount total notes work: `notes_s` is 138.127 s and written tokens 14,698,
whereas the calls log records 393.181 s and 43,361 written tokens across all 23 notes calls.

## Evidence and patches

- [Source audit](../data/2026-10-23-context-campaign64/source-audit.json),
  [provenance and cost audit](../data/2026-10-23-context-campaign64/provenance-audit.json).
- [Final result](../data/2026-10-23-context-campaign64/results.json.gz),
  [retention hashes](../data/2026-10-23-context-campaign64/retention.json),
  [whole-history check](../data/2026-10-23-context-campaign64/history-check.json),
  [server state](../data/2026-10-23-context-campaign64/server-health.json).
- [Archive](../data/2026-10-23-context-campaign64/archive.jsonl.gz),
  [notes versions](../data/2026-10-23-context-campaign64/notes-history.jsonl.gz),
  [notes events](../data/2026-10-23-context-campaign64/events.jsonl.gz),
  [all call timings](../data/2026-10-23-context-campaign64/calls.jsonl.gz),
  [pi events](../data/2026-10-23-context-campaign64/pi-events.jsonl.gz).
- [Independent preflight](../data/2026-10-23-campaign64-preflight/review.json),
  [client](../scripts/context/current_pi_probe.py), [runner](../scripts/context/run_campaign64.py).

Raw receipts remain under `context-longrun-20261016/campaign64-current-pi/`,
`runs/c64/pi/jobs/AB-pi__repair-n40-s2x/trial/` and `proxy-state/c64-pi/4051fd73e25016a5/`.

## When to revisit

Do not repeat the unchanged full task or return to reviewer prompt/cap sweeps. The next specific
lever is the main agent's [history-use contract](2026-10-23-campaign65-history-coverage.md): selective notes are not an exhaustive event list;
exhaustive historical requests need original archive coverage. Test that behavior at this actual
failure with a matched reconstructed control before spending another full-task run. Any changed
prompt is a candidate quality intervention, not a lossless speed optimization or production default.
