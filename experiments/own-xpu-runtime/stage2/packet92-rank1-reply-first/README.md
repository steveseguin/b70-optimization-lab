# Packet92: rank1 reply before host reporting

Two sealed views share one binary copied from packet84: `production` and
`reply-first`. Production is hc-wide / wide64 / ordered / rec-parallel,
production route/norm/dense, draft-HC, batch rollback, rank1 draft, 24/24.
Only host report scheduling changes. Device kernels, operation order, arithmetic,
BF16 KV, target verification, waits, profiling guards, result copies and ordered
event retirement remain unchanged.

The next draft also waits for rank1 accept. The candidate therefore retains a
single report across the half reply and accept, submits the next asynchronous
draft, then completes reporting before the draft reply or any next half.
Without a draft it flushes before the next other command. Stop/reset/dump also
flush. Deferred errors poison the slot and abort the native mailbox; no next
half can execute after a failure. An already published result remains a verified
target result, but a later receipt error fails the run.

[Attribution](ATTRIBUTION.md) explains the dependency boundary. The movable
bucket is formatting/output, host load/affinity queries and a site summary.
Resource-counter snapshots remain at the original half boundary, and every
changing counter/array is frozen before deferral. Host load and affinity describe
report time. Existing receipt fields remain present; none is fabricated or
silently discarded. Failure to write either half or diagnostic receipt is fatal.

`rank1/p92-host.jsonl` has one row per half in both views. `result_ready_to_reply_ms`
measures from data/error proof to actual mailbox/socket publication;
`bookkeeping_ms` measures the deferred-capable report body. Each bucket uses two
steady-clock reads. The diagnostic row's own output is outside its bucket.
`busy_ms`/`rank_completed` continue to describe command execution: the candidate
half excludes deferred reporting, while the next draft command includes it.
These are host timings, not GPU timing or a speed claim. Existing p76 retirement
and profiling fields stay in `timings.jsonl`.

CPU gates pass: two GNU and two Intel mock state/mailbox runs (nine failure
cases each), two complete miniature runs per view against packet84, four
full-size real-startup mocks, unchanged memory admissions, and 87 Python checks.
The miniature gate compares 96 retained layer files, all 24 target tokens,
proposals and final draft state; it also checks the original half receipt fields
and every added timer row. GNU runs the complete miniature engine; GNU and Intel
independently compile/run the changed host state machine. The unchanged device
sources and reused object identities are separately hash-bound. No claim of
full-model or device correctness follows from these CPU tests.

[Coordinator handoff](WINDOW.md) · [CPU closeout](CPU-PREPARATION-CLOSEOUT.md) ·
[boundaries](DO-NOT-REPEAT.md) · [retention/rebuild](ARTIFACT-RETENTION.md).
