# Sparse-state development screen, version 1

Prospective preparation, 2026-10-07. No model request is authorized by this file
alone: finish and audit the current semantic diagnostic, preserve its outcome,
verify card release, and freeze this separate implementation before execution.
The owner has asked work to continue. This screen investigates a materially
larger output-volume opportunity; it does not repair or complete r4.

## Question and four fixed trials

At eight counters, emitting quotations costs more output than rewriting a small
state table. At 128 counters with three changes per batch, sparse event output
could be much smaller. Both methods still receive their full current state, so
this is not a claim that durable storage removes input-context limits.

Use one new development seed, 83, and one explicit report-style generator.
Counter counts are fixed at 8 and 128. Every task begins with explicit source
postings initializing its counters in chunks of at most 16 counters per batch;
both methods see identical initialization batches for that task. Follow with
16 batches containing three actual set/add/sub updates and controlled filler.
Include all initialization calls and costs. Never preload a private oracle
state into the model. Names, event stream and text are deterministic and frozen.

Order: 8/archive, 8/quoted, 128/quoted, 128/archive. Within a size, both methods
see byte-identical documents and questions. The two sizes are different state
streams, not independent repetitions or a perfectly matched causal estimate of
state size. Do not choose a seed after model outputs arrive.

Fix 24 questions per task: eight current balances, eight integer historical
balances and eight historical ownership joins. Include updated and untouched
counters. Source ownership statements, historical times and joins must be
explicit. The programmatically generated reference is checked by separate
straight-line arithmetic replay and source/identity checks; it is not represented
as two independent human or assistant annotations.

## Interaction and quality

Reuse the frozen semantic trial engine as an explicitly identified implementation
dependency. A separate study manifest identifies these as generated sparse-state
tasks; the reused engine's native schema is compatibility metadata, not evidence
of human authorship or membership in the twelve-document semantic packet.
No frozen engine, task, plan or earlier result is edited to admit these tasks.

Keep the same working prompt limit of 32,768 UTF-8 bytes, 6,553-byte memory limit,
three ingestion attempts, 4,096-token thinking-disabled ingestion cap, and final
medium-thinking 8,192-token cap. Keep 24 retrievals and 32 answer calls. No
transport retry, output continuation, cap increase or resumed trial. Preserve
bounded model failures and continue other planned trials; infrastructure failures
abort the server. CPU checks must verify actual serialized prompt sizes and
local-tokenizer fit of reference responses before model execution. Such checks
are software/budget validation, never model accuracy or performance evidence.

A size passes the primary quality screen only if BOTH methods have all counters
exact at EVERY accepted batch checkpoint, exact final state, all 24 answers
correct, complete unresumed trials and no ignored refusal/failure. Accepted quoted event sequences must also match every reference counter,
operation and amount in order. Valid alternative quote spans remain acceptable.
Quote source acceptance alone is not semantic completeness. Record every attempted event
list and refusal; a later overwrite cannot hide an earlier wrong update.

Separate initialization, subsequent ingestion and answering for descriptive
wall time, calls and token costs. The total includes all three phases and every
retry. Check all raw request cache counts are known zero. Missing cache metadata
or hits prevent a cold-cost interpretation. Report every planned row regardless
of quality. No speed verdict, benchmark promotion or holdout admission follows
from one server or this synthetic development screen.

## Runtime and next decision

One fresh server uses the same cache-disabled, full-precision-KV profile and
standing twelve-case strict qualification as the semantic run. Bind source,
generator, manifest, runtime and prior STOP/card-release identities before
launch. Use the established one-owner locks, bounded health checks and graceful
owned shutdown. No resident service, automatic restart, reboot, driver reset,
power, swap or page-cache changes.

Planned output: `/mnt/fast-ai/bench-results/context-sparse-v1-20261007`.
Planned unit: `ctx-sparse-v1.service`. Do not start it while the semantic owner
is active. A live preparation receipt and CURRENT.md must identify the exact
frozen inputs and measured previous cleanup before this plan can run.

If the 128-counter screen is correct and shows at least a 10% reduction in total
elapsed time versus its paired archive trial, preregister fresh-server replication
and another writing style before a performance conclusion. Otherwise preserve
its failure or cost result and select the next substantial lever. A reduction
in output bytes alone is not a measured speed improvement. Any future broader
reliability claim requires separately authored confirmatory documents.
