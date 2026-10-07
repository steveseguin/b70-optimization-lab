# Historical accepted-state study: complete negative result

All eight fixed trials completed. Source-only answering was exact in every
condition. Adding historical balance access left all numeric states correct but
introduced wrong historical ownership joins. The prewritten continuation rule
fails; the unused t03/t04 development extension is not admitted.

## Complete results

A = archive bookkeeping, Q = quoted updates; S = source-only answering, H =
source plus historical balance access. Both modes saved the same actual-state
snapshots. Each row ingested anew; questions appeared only after ingestion.

| Document | Condition | Current | Earlier balance | Ownership join | Exact checkpoints | Total seconds | Calls |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| t01-clinic | AS | 8/8 | 8/8 | 8/8 | 12/12 | 225.5 | 24 |
| t01-clinic | QH | 8/8 | 8/8 | 3/8 | 12/12 | 263.8 | 24 |
| t01-clinic | QS | 8/8 | 8/8 | 8/8 | 12/12 | 198.7 | 22 |
| t01-clinic | AH | 8/8 | 8/8 | 3/8 | 12/12 | 194.0 | 23 |
| t02-theatre | AH | 8/8 | 8/8 | 3/8 | 12/12 | 179.7 | 23 |
| t02-theatre | QS | 8/8 | 8/8 | 8/8 | 12/12 | 199.8 | 22 |
| t02-theatre | QH | 8/8 | 8/8 | 7/8 | 12/12 | 298.6 | 28 |
| t02-theatre | AS | 8/8 | 8/8 | 8/8 | 12/12 | 205.9 | 22 |

All 188 calls report known zero cached tokens. All 96 original source batches
survived exactly, all 96 accepted checkpoints and immutable snapshots match their
references, and all 202 accepted quoted postings match operation, amount, counter,
source and order. There were no refusals, missing trials, cap failures or
infrastructure aborts. Completed execution does not mean correct final answers.

The [independent audit](../data/2026-10-07-history-study-result/audit.json)
reconstructs those counts and the failed continuation rule. No history/source
speed comparison is eligible because each history condition fails final quality.
The displayed elapsed times include initialization, ingestion, answering and
snapshot persistence. These are one-server development costs, not a general
speed qualification.

## Why the answers failed

Every error was an ownership join. All sixteen wrong answers equal the balance
of the ticket’s initial owner at the requested close, after the ticket had
transferred to another owner. The numeric balance histories themselves were
correct. The [source and answer error analysis](../data/2026-10-07-history-study-result/answer-error-analysis.json)
records each question, original transfer, expected owner and observed value.
Its `task_sha256` field hashes the complete task file; it is not the internal
semantic task fingerprint used by native results. The separately bound
[provenance clarification](../data/2026-10-07-history-analysis-provenance.json)
records both identities explicitly. Scores and preserved inputs are unchanged.

Both clinic history conditions used initial ownership for the same five joins.
The theatre archive/history condition also missed five joins. Theatre quoted/history
used additional source retrieval and got seven of eight joins right, but still
used the initial owner for join 2. Exact snapshots cannot answer ownership facts
that are outside the numeric table; the model must obtain and apply that source
evidence at the right time. This diagnoses selection/interpretation of ownership
evidence, not an arithmetic or snapshot-corruption failure.

Within each document/bookkeeping pair, all twelve ingestion prompts and response
texts were identical across answer-access modes; see the
[ingestion comparison](../data/2026-10-07-history-study-result/ingestion-comparison.json).
Thus the observed divergence occurs during answering. The treatment changes the
answer instruction and available tool together; it does not isolate one of those
two causes or establish a general causal law for other tasks.

## Frozen protocol, preservation and lifecycle

The [prospective plan](2026-10-07-history-state-study-plan.md) and
[prior decision](2026-10-07-context-next-study-decision.md) fixed all eight rows,
limits and the extension rule before temporal model outputs. Implementation was
frozen in commit `ea7047ed2`. Both access modes pay for snapshots of actual accepted
state, and neither receives a reference-corrected table. All 97 dependencies
remained unchanged through completion.

The owner passed all 12 strict reference prompts, started the fixed trials at
07:05:38 UTC, and completed them at 07:35:13. STOP was confirmed at 07:35:22,
both cards were released at 07:36:13, and healthy completion was recorded at
07:36:23 on 2026-10-07. `ctx-history-study-v1.service` is inactive with a successful
exit. No server restart, host setting change or device reset occurred.

The [preserved packet](../data/2026-10-07-history-study-result/inventory.json)
binds 194 files (about 4.1 MB including inventory/restore receipts), including all
native call evidence and 96 snapshot JSON files. All eight SQLite stores were
archived and byte-compared. A separate temporary restore reproduced the full
independent audit exactly after normalizing only output/directory root paths.
The [preservation receipt](../data/2026-10-07-history-study-result/preservation.json)
binds the archive, inventory and audit. The earlier four-row partial audit remains
a dated progress artifact; use this complete result for conclusions.

## Decision and limits

Do not extend or retune this matrix. Its history-quality, no-regression and
continuation conditions all fail. Keep t03/t04 unused. The separately frozen
[two-call full-source screen](2026-10-07-full-source-screen-plan.md) is the next
usefulness check, with its own server admission and final-answer-only contract.

These are two short assistant-authored, independently assistant-annotated
documents using a shared posting grammar. All requested earlier balances differ
from final values, but they contain only about 1,500 source tokens each and fit
together with their questions in one prompt. These results do not establish a
benefit beyond the model window, general factual memory or bounded total memory.
The failed ownership joins make that scope distinction concrete.
