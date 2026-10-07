# Historical accepted-state study, version 1

Prospective implementation plan for Branch B of the previously committed
[next-study decision](2026-10-07-context-next-study-decision.md). The running sparse
replication's dispatch archive has already returned an unsupported zero balance
for `unitex10` in batches 1–7, before its first balance posting in batch 8.
Both independent raw reviews confirm the extra entry. Its remaining trial still
finishes unchanged; this study cannot launch until that full campaign is audited,
stopped and released. No temporal model result has been observed.

## Fixed comparison

Use the frozen `history_v1` engine for every condition. Cross bookkeeping
(`archive` or `quoted`) with answer access (`source-only` or `history`). Both access
modes save, verify and pay for the same immutable snapshots of the method's actual
accepted state. History adds access to `state_at`; it never supplies reference
answers or repairs values. Source retrieval remains necessary for ownership.
The change being measured is the combined answer instruction/tool-access policy.

Run these eight fresh trials, exactly in order, on one newly qualified server:

| Position | Document | Bookkeeping | Answer access |
|---|---|---|---|
| 1 | t01-clinic | archive | source-only |
| 2 | t01-clinic | quoted | history |
| 3 | t01-clinic | quoted | source-only |
| 4 | t01-clinic | archive | history |
| 5 | t02-theatre | archive | history |
| 6 | t02-theatre | quoted | source-only |
| 7 | t02-theatre | quoted | history |
| 8 | t02-theatre | archive | source-only |

Every row ingests the source anew, with separate files and transcript. No shared
ingestion, resumed answers or reconstruction from an earlier trial. Each factor
has balanced positions across the two documents. Finish all eight rows after any
bounded model/protocol failure; infrastructure failure stops and preserves every
remaining planned row as unstarted. No summary arm, budget increase or retry.

The source and adjudication are the fixed
[temporal packet](../data/2026-10-07-temporal-development/review-note.md).
Bind source SHA `45ae96b4c80dca9a14defddf1bf33ae895e47fed9848101dbdc9ae2cb2be666f`
and adjudication SHA `e8bee704ebcdf69635205eefe949884bbb096d724fbb01646e046c836b461b1f`,
both independent annotation files, exact compiled tasks and all public conventions.
The first two document IDs were selected in the decision note before any temporal
model output. The other two documents remain unused development cases, not holdouts.

## Fixed limits and evidence

Keep 32,768 serialized prompt bytes, 6,553 memory bytes, three ingestion attempts,
thinking-off 4,096-token ingestion, and medium-thinking 8,192-token answers.
Keep 24 successful distinct retrievals and 32 answer calls. Searches, source
fetches and historical state fetches share the retrieval cap. Repeated cached
retrievals still consume an answer call. No cap compensates for a failed lookup.
Preserve question visibility only after ingestion ends.

The CPU fixture demonstrates that twelve source fetches plus nine earlier-state
fetches fit: 21 retrievals and 22 calls including submission. It does not guarantee
that the model chooses this schedule, reasons correctly or fits its output cap.
Preparation must independently recompute exact serialized prompt/reference-response
fit with the actual local tokenizer and freeze those receipts.

Grade each row's current, historical-balance and historical-ownership answers
separately, eight per category. Missing/null answers are wrong. Strict quality
requires complete unresumed execution, 24/24 answers and every one of the twelve
accepted state checkpoints exact. Quoted events additionally require exact
counter/operation/amount sequence and source quotes. A correct final table cannot
erase an earlier bad checkpoint. Report source delivery, refusals, all spent
calls/tokens/time, retrieval action counts, cached repetitions and cap exhaustion.

The independent audit must reconstruct actual state from raw accepted replies,
check the canonical ledger, every snapshot and returned `state_at` value, and bind
all raw response/artifact hashes. Snapshot integrity alone does not prove quality.
Snapshots must preserve wrong, missing or extra archive entries; they cannot read
the private reference to correct the model. Record whether an answer error arose
in ingestion or in choosing/interpreting source or history evidence.

Only exact cold pairs permit descriptive cost comparisons. Every relevant model
call must have known zero cached tokens. Report total elapsed time including
persistence, answer-phase costs and ingestion separately, per document. Compare
history versus source-only within each arm and bookkeeping within each access
mode. Do not pool different documents or compare this engine's timings directly
to older engines without snapshot persistence. No general speed claim or holdout
admission follows from this experiment.

## Lifecycle and continuation

Prepared packet: `data/2026-10-07-history-study/`. Output:
`/mnt/fast-ai/bench-results/context-history-study-v1-20261007`.
Owner unit: `ctx-history-study-v1.service`. Require the completed independent
four-row sparse-replication audit to confirm a valid negative quality/cost outcome
under the prior decision; unknown/nonzero cache or infrastructure is not a valid
negative timing result. Bind native results and raw costs, not just gate booleans.

Require same-boot confirmed STOP/card release, idle health, unchanged qualified
image/model/full-precision KV and cache-disabled/no-warmup profile, and strict
12/12 admission. One supervised owner holds the established locks and owns launch,
client, raw evidence and graceful shutdown. No resident service, automatic restart,
reboot, reset, power, memory, swap or page-cache change. Freeze the new wrapper,
host, auditor, engine, source/reference packet and lifecycle dependencies only
after CPU checks and independent review. A plan file is not launch admission.

After all eight rows, use the previously frozen continuation rule: complete
auditable evidence, every history row fully exact, no category accuracy loss
against its same-arm source-only counterpart, plus either a temporal-answer
improvement or one arm with exact results and at least 10% lower total elapsed
under history on both documents (all relevant calls cold). This only admits
preparation of the fixed t03/t04 development extension described in the decision
note. The runner does not launch it automatically. If the signal is absent,
preserve all results and classify the limiting error before choosing a separate
extraction, ownership or cost experiment. Do not retune this matrix.

These are short assistant-authored, assistant-annotated documents with a shared
controlled posting grammar. All historical balances differ from final values,
but only five of 32 ownership joins across the full four-document packet require
a different historical owner, and one historical target is duplicated. This is
not human validation, a representative external corpus or a long-context test.
