# Context research review — 2026-10-06

The quoted-events approach has a real successful 480K run, but several reported
question counts were wrong, one repeat was unsupported, and the checker does not
provide the claimed correctness guarantee. This review covers the recent quoted
checker commits through `2918a324d`, results through `5269846c1`, and the SkinDeep
snapshot through `8c37824`. It does not rerun model inference.

## Verified results

Scores come from each trial's `verifier/details.json`, not reward multiplied by
an assumed 24 questions. Timings below come from saved trial summaries and are
rounded. Preserve each trial's seed, task and checker version when comparing.

| Task and agent | Verified score | Time | Correction |
| --- | ---: | ---: | --- |
| 480K narrative, read mode, seed 0 | 10/10 | 25.7 min | Previously 24/24 |
| Same 480K narrative, quoted events, seed 0 | 10/10 | 19.6 min | Previously 24/24 |
| 480K narrative, read mode, seed 1 | Unverified | — | No completed artifact found; withdraw claimed 24/24 |
| 480K narrative, density 6, read mode | 13/13 | 28.5 min | Previously 24/24 |
| 119K narrative, density 6, read mode | 22/22 | 8.8 min | Previously 24/24 |
| 120K narrative, density 12, read mode | 14/16 | 13.4 min | Previously 21/24 |
| 120K narrative, density 12, quoted fix 2 | 16/16 | 7.4 min | Confirmed |
| Retention seed 0, quoted fix 2 | 35/36 | 5.7 min | Confirmed; 11,776 generated tokens |
| Retention seed 1, archive/read mode | 29/30 | 5.6 min | Completed, previously described as pending |
| Million-token narrative, read mode | 23/24 | 62.2 min | Confirmed; one stale final value |

The matched 480K times are 1,539 and 1,173 seconds: 23.8% less elapsed time for
quoted events in one comparison. Both tasks have 282 narrative batches plus a
final question batch, not 240 batches. Final-answer correctness does not prove
every intermediate state was correct. The million-token score does not estimate
a per-change reading-error rate.

[Evidence index](../data/2026-10-05-context/review-2026-10-06/evidence.json)
contains 28 selected completed attempts, including invalid attempts, original
paths and hashes, grader details and saved summary metrics. Supporting copies
and the export script are in the same directory. Raw source artifacts are
unchanged. This is an auditable result export, not a complete clean-host runtime
reproduction package.

## Checker findings

1. **High: edited notes can become supposedly verified evidence.** The fix-2
   fallback finds an `ITEM` header anywhere in the editable mirror and treats
   its following text as delivered input. A fabricated counter update therefore
   passes its quote check. It then writes an empty `.done` marker instead of
   preserving that text for recall. This contradicts both the provenance and
   archive claims.
2. **High: mixed merged and ordinary items can apply out of order.** The fallback
   only runs when no ordinary tool item was found. A newer ordinary item can be
   applied before an older merged item. In a CPU reproduction, set-to-10 followed
   by add-5 ends at 10 rather than 15.
3. **High: an unquoted event heredoc permits shell expansion.** The command
   recognizer accepts `<<EOF`, allowing `$(...)` to run before the checker reads
   state. Require a quoted delimiter; a standalone-looking command alone is not
   an adequate guard.
4. **Correctness limit:** checking that a quote and amount occur in text does
   not check whether the operation has the right meaning, whether an event was
   omitted or repeated, or whether a mentioned change was cancelled. Integer
   arithmetic is deterministic once events are accepted; overall bookkeeping
   is not guaranteed correct by construction.

The focused repair is preserved as
[an unapplied patch](../../../patches/context-quoted-delivery-validation-20261006.patch).
It rejects unprocessed items in edited turns before applying newer items, removes
the unauthenticated fallback, and requires quoted event heredocs. This intentionally
fails closed; safely recovering a merged batch needs an immutable delivery record.
It is not a general sandbox or a semantic verifier.

The existing plan-E experiment imports the live harness for queued trials. Its
files and server are left untouched so this review does not silently change the
experiment. Apply the patch after that campaign, under a new recorded identity,
then run the stub integration suite before further model trials. CPU regression
checks apply the patch to temporary copies, not the live harness:

```sh
python3 experiments/qwen38-27b-b70/scripts/context/test_quoted_delivery.py
```

## Reporting and organization

- SkinDeep's ledger renderer treated non-digit score strings as "No answer" and
  defaulted rows without input lengths to the 121K ledger. Reading and retention
  rows need explicit task families and numeric question counts, with their own
  tables. Combined seeds must not share one seed's token counts as if pooled.
- The site linked new claims to lab revision `18cd0508`, which predates them.
  Keep historical raw-data pins and cite the current corrected results and
  review evidence separately.
- Requesting a new seed in an existing task directory can fail planning because
  `second-comparison.sh` skips generation for that directory. The planner then
  cannot read the missing `task.toml`. A plan entry is not a completed trial.
- `CURRENT.md` now distinguishes completed reruns, unverified repeats and the
  protected active plan. Original failed runs remain in the evidence.

Website corrections are local until publication is requested. No model/GPU
inference, server restart or host-setting change is part of this review.
