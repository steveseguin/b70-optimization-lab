# Sparse-state replication and transfer result

The original generated task repeated its exact/cold elapsed signal on a fresh
server with reversed method order. The new seed-and-style case failed the fixed
checkpoint quality gate: archive invented a zero balance before that counter's
first posting. All four trials completed with 24/24 final answers. The new case
therefore supplies no qualified paired speed comparison.

The [prospective plan](2026-10-07-sparse-state-replication-plan.md) and all frozen
code/task bytes remained unchanged. No failed result was replaced, budget raised,
trial resumed or holdout opened.

| Fixed order | Task | Method | Final answers | Exact checkpoints | Total elapsed |
|---|---|---|---:|---:|---:|
| 1 | Original report, seed 83 | Archive | 24/24 | 24/24 | 506.6 s |
| 2 | Original report, seed 83 | Quoted events | 24/24 | 24/24 | 397.1 s |
| 3 | New dispatch, seed 97 | Quoted events | 24/24 | 24/24 | 362.6 s |
| 4 | New dispatch, seed 97 | Archive | 24/24 | 17/24 | 507.1 s |

All 155 calls report known zero cached tokens. Source delivery is exact for all
96 batches, and all 352 accepted quoted events match source and reference semantics
in order. There were no ingestion refusals, bounded failures or infrastructure
aborts. A completed trial can still fail quality; that distinction explains the
last row's completed status and false quality flag.

## What repeated and what failed

The original task's quoted elapsed reduction is 21.6%, following 21.7% in the
[initial screen](2026-10-07-sparse-state-result.md). Both original-task methods
produced the same full response messages and received the same inputs on all
40 corresponding calls across the two servers. The
[trace comparison](../data/2026-10-07-sparse-state-replication-result/original-trace-comparison.json)
binds the raw call files. This is observed repeatability for this generated task
and fixed protocol, not universal determinism or broad performance qualification.

The new dispatch archive returned `unitex10: 0` in batches 1–7. Batch 1 says
`ticket-n128-0 belongs to counter unitex10.`; its first balance posting occurs in
batch 8: `Dispatch recorded unitex10 at a balance of 110.` The model introduced
an unsupported balance from an ownership mention. Every actually initialized
balance was correct. The explicit batch-8 setting removed the error, and later
checkpoints and all final answers were exact. Historical questions in this task
start at batch 9, so they never directly ask about the earlier invented value.
The [raw-reply analysis](../data/2026-10-07-sparse-state-replication-result/checkpoint-failure-analysis.json)
records the precise scope and source evidence.

The prewritten gate requires every checkpoint exact, so later correction does
not qualify the pair. The new seed and wording changed together, preventing a
causal attribution to wording alone. Both sparse tasks also retain weak temporal
contrast: only 2/16 historical/ownership answers differ from final balances.
Do not turn this into a broad recall result or discard the checkpoint failure
because the questions happened to miss it.

## Cost location

Client-call seconds below exclude the small separately reported host overhead;
the main table uses complete trial wall time.

| Task/method | Initialization | Steady updates | Answering | Completion tokens |
|---|---:|---:|---:|---:|
| Report/archive | 53.6 s | 156.3 s | 295.9 s | 61,184 |
| Report/quoted | 54.7 s | 33.3 s | 308.1 s | 44,854 |
| Dispatch/quoted | 63.0 s | 33.8 s | 264.9 s | 40,881 |
| Dispatch/archive | 57.2 s | 170.3 s | 278.9 s | 62,302 |

On the exact original pair, the saving comes from steady updates to a wide table;
answering remains the largest phase. The dispatch costs are retained observations,
not an eligible paired speed percentage. These facts support testing historical
state access as a separate answer-stage change, without claiming it will repair
wrong ingestion.

## Preserved evidence and next action

The [independent audit](../data/2026-10-07-sparse-state-replication-result/audit.json)
was reproduced exactly from a restored evidence copy. The packet retains native
JSON/JSONL, hash-bound host and strict receipts, health command/log evidence,
trace/failure analyses and four byte-verified compressed SQLite stores. The
[inventory](../data/2026-10-07-sparse-state-replication-result/inventory.json) binds
60 preserved files; the inventory itself is additional. Raw output remains at
`/mnt/fast-ai/bench-results/context-sparse-replication-v1-20261007`.

Strict admission passed 12/12. The owner confirmed STOP at 06:44:03 UTC, card
release at 06:44:55, and healthy completion at 06:45:05 on 2026-10-07. No server
remains resident and no restart, reset or host-setting change occurred.

The previously committed [decision tree](2026-10-07-context-next-study-decision.md)
selects the valid-negative branch. The separate
[history study](2026-10-07-history-state-study-plan.md) prepares eight fresh trials
crossing bookkeeping and access to actual accepted history on two fixed temporal
documents. Both access modes persist the same states, including mistakes. Its
source/reference packet has been checked before model evaluation; its wrapper,
auditor and host still require CPU validation and independent review before launch.
