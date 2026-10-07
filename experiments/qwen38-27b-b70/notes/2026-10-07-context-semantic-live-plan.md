# Semantic development live diagnostic, version 1

Prospective plan, 2026-10-07. Freeze this document and the implementation before
any model request. This is a meaning/interpretation diagnostic, not a speed
benchmark, long-context comparison, or admission to the frozen r4 holdout.

## Question and scope

Does quoting preserve the intended meaning of actual postings when nearby text
contains cancellations, drafts, reversals, aliases or distracting numbers? A
verbatim quote and correct arithmetic establish provenance and bookkeeping;
they do not establish correct attribution, interpretation or complete extraction.
Compare the same documents with model-maintained archive tables and summaries.

Use all twelve documents in the [authored packet](../data/2026-10-07-context-semantic-development/documents.json),
SHA-256 `8fe86d7dc3ebd7d16ee06672ab0f7b8dc950a2ecc6b92c88f8019849dfcdb579`.
The [adjudicated reference](../data/2026-10-07-context-semantic-development/adjudicated.json)
binds two separate assistant annotations. They agree on all 84 answers, 48 batch
states and 84 events; six alias quote-span differences are retained separately.
This is not independent human validation. Do not change documents, annotations,
prompts, caps or scoring after model results arrive; improvements require a new
version and preserve this outcome.

## Fixed matrix and interaction

Run 36 trials: all twelve document IDs in sorted order, each with summary,
archive and quoted methods. Rotate that three-method order by document index
modulo three. Stress/control variants share underlying events and answers;
report their dependence and retain every planned row.

Every method receives the same four original batches in order, one at a time,
and the public reading conventions on every request. Questions appear only
in the answer phase. Private reference events, states and answers never enter
model prompts. Archive maintains its complete table; quoted emits ordered
literal set/add/sub events and the existing ledger performs arithmetic. Summary
compresses after **every** batch. This forced four-step summarization is a short
semantic diagnostic; it is different from r4's budget-triggered summarization
and cannot be presented as a direct continuation of that workload.

Each working prompt is limited to 32,768 UTF-8 bytes, memory to 6,553 bytes.
Ingestion uses thinking disabled and a 4,096-token output cap. Final answering
uses thinking enabled, medium effort and an 8,192-token combined reasoning/output
cap. Preserve the raw reasoning, content, stop reason, request and usage.
Typed answers use explicit per-question int/str declarations, including integer
historical answers. All methods may retrieve original delivered batches through
the same bounded protocol: at most 24 retrievals and 32 answer calls. Accepted
partial answers persist; missing answers are wrong in final scoring.

Allow at most three JSON/protocol attempts per ingestion batch. There is no
continuation after output truncation, no cap increase and no transport retry.
Fresh output only; no resumed or repeated model trials. A valid model response
that reaches its output cap, an unsupported terminal model response, exhaustion
of protocol attempts or exhaustion of the answer budget is a terminal failed
trial. Preserve its partial traces, count its missing answers wrong, and continue
the planned matrix. Invalid HTTP envelopes, transport failures and internal
storage/runtime failures abort the campaign and trigger owned cleanup. They are
not silently converted into model-quality failures.

## Evidence and interpretation

Record every attempted event list, every checker refusal and every accepted
checkpoint. Score event semantic tuples separately from quote acceptance:
omissions, spurious events and identifiable wrong counter/operation/amount;
report ambiguous unmatched events without inventing a correspondence. A valid
alternative quote span is not a semantic error. Score every checkpoint so a
later overwrite cannot hide an earlier wrong update. Grade final answers by
category and declared type. Separate ingestion completion, final-answer
completion, semantic accuracy and provenance acceptance.

Summary has no observable internal counter table; its intermediate correctness
is unknown. Failed traces retain only observed batches, never synthetic replies.
Report planned/completed/failed/unstarted counts and stress/control pairs,
including failures. CPU gold-response replay is explicitly a wiring test and
cannot count as model evidence. Audit native call logs and source storage after
execution. Report token/call counts descriptively; this packet establishes no
performance verdict regardless of its results.

## One owned fresh server

Use the r4 cache-disabled profile with unchanged model, full-precision KV and
pinned target-verified MTP configuration. Verify actual emitted arguments before
requests. Freeze all model-client, annotation, plan, lifecycle and runtime
helper dependencies in the preparation receipt. Require prior r4 STOP and
card-release evidence on the same boot, idle ownership, resource/fault checks
and the bounded two-device health check. The same standing strict reference
qualification must pass all twelve cases before any semantic request.

Output: `/mnt/fast-ai/bench-results/context-semantic-v1-20261007`.
User unit: `ctx-semantic-v1.service`, Restart=no, KillMode=process,
SendSIGKILL=no. One start only; no automatic retry or server restart. No reboot,
driver reset, power, swap or page-cache changes. Stop only the owned server
gracefully and verify empty cards on completion or failure. No resident service
remains. The prior r2/r3/r4 implementations and held-out seeds stay frozen.

## Follow-up decision

Use errors to identify interpretation or interface defects, preserving this
packet as development evidence. Before broad reliability claims, require a
separately authored confirmatory corpus. For performance work, investigate
larger sparse state tables with a prospectively fixed quality gate, all-request
zero-cache evidence and fresh-server replication; quoting adds text and is not
assumed faster.
