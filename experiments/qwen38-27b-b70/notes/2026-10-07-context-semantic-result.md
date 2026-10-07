# Semantic diagnostic: quoted events exact; archive misreads a reset and a credit

All 36 trials in the [fixed live plan](2026-10-07-context-semantic-live-plan.md)
completed under the unchanged budgets. The independent native audit verifies:

| Method | Final answers | Exact observable balance checkpoints | Calls |
| --- | ---: | ---: | ---: |
| Summary after every batch | 84/84 | Internal state not observable | 60 |
| Model-maintained archive table | 82/84 | 44/48 | 103 |
| Quoted events, code-maintained table | 84/84 | 48/48 | 102 |

All 84 accepted quoted events match the reference counter, operation and amount
in order. There were no omissions, extra events or checker refusals. Valid quote
span differences are separate from semantic matching. All 144 original deliveries
across the 36 trials remain byte-exact. All 265 calls report zero cached tokens.

## What failed and what final answers would hide

In both s06 variants, the archive treated `amber10 was set to 7` as addition:
18 became 25, then the next batch's credit of 2 produced 27. The correct final
balance is 9. During final retrieval it correctly reconstructed the historical
reset, yet retained the wrong current answer from its own table.

In the stress variant it also treated `birch11 was credited 9` as subtraction:
15 became 6 instead of 24. A later explicit reset to 13 hid that error in the
final balance. Intermediate checkpoint grading exposed it. The two variants
share their underlying postings, so their repeated reset failure is not two
independent examples of the same defect.

The quoted method emitted the correct operations in these cases and code applied
them exactly. This supports the narrow design benefit: verified source storage
and deterministic arithmetic reduce bookkeeping errors when extraction is right.
It does not make quote validation a proof of correct interpretation or complete
extraction. These twelve documents passed the separate semantic comparison;
other documents can still contain unsupported or misunderstood instructions.

Summary kept enough information to answer these very short documents with one
answer call each; the structured methods usually retrieved original batches.
This is a four-batch authored diagnostic with forced summarization after every
batch, not the earlier long-stream workload. Its costs establish no general
speed ranking. Summary's unobserved internal balances are not graded as exact.

## Scope and preservation

The six stress/control pairs cover cancellations, drafts, posted reversals,
aliases, nearby numbers and historical ownership joins. Paired variants share
answers; these are not 84 independent questions. Two separate assistant
annotations were reconciled before model execution. This is neither independent
human validation nor an external or held-out benchmark. The frozen durable
holdouts remain unused. No earlier failure or gate was reclassified.

Before launch, 31 adapter/client and 38 lifecycle CPU tests passed; the separate
native auditor has 12 tests, including a net-zero extra-transaction case whose
balances remain correct. Audit reconstructs saved answers and every observable
checkpoint from raw replies and SQLite events, compares semantic event tuples,
checks receipts and artifact hashes, and leaves unreported usage unknown.

[Native audit](../data/2026-10-07-context-semantic-result/audit.json),
[complete inventory](../data/2026-10-07-context-semantic-result/inventory.json),
[host audit](../data/2026-10-07-context-semantic-result/diagnostic-host-audit.json)
and all native JSON call/trace/result evidence are preserved in the result folder.
The 36 canonical SQLite stores are preserved in `canonical-stores.tar.gz`, with
all archive members byte-compared against the originals. To rerun the read-only
audit, copy that result folder into a temporary directory, extract the archive
there, then run `scripts/context/audit_semantic_v1.py --out <copy>` from this lane.
Full original output remains `/mnt/fast-ai/bench-results/context-semantic-v1-20261007`.

Standing strict qualification passed 12/12. The server stopped cleanly;
card release was verified at **05:19:26 UTC**, followed by a successful health
check. No model server remains running. No reboot, reset, power, swap or page-cache
setting was changed.

Next is the separately preregistered [sparse-state screen](2026-10-07-sparse-state-development-plan.md):
eight versus 128 counters, unchanged budgets, initialization included, and every
state checkpoint plus every accepted quoted event checked. A single synthetic
screen cannot establish a general speed advantage.
