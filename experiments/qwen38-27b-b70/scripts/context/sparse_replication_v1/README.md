# Sparse-state replication and transfer

This new wrapper follows the prospective sparse replication plan. It reuses the
same pinned semantic engine in isolated workers; all earlier engines and packets
remain unchanged. It does not expose historical-state retrieval.

The four trials are fixed: report seed83 archive, report seed83 quoted, dispatch
seed97 quoted, dispatch seed97 archive. Both cases have128 counters, eight
initialization batches of16, sixteen steady batches of3 postings, and24 typed
questions. The report document and compiled task are copied byte-for-byte from
the frozen original packet, with hashes in `original-source.json`. The dispatch
case changes seed and posting wording together; this is not an isolated style
effect. Filler, ownership/review grammar and question-selection formulas remain
unchanged. Both cases have only2 of16 historical/join answers different from
the final value; the plan records every comparison instead of retuning questions.

Dispatch uses three explicit clauses: `Dispatch recorded NAME at a balance of
AMOUNT.`, `A credit of AMOUNT was posted to NAME.`, and `Dispatch posted a debit
of AMOUNT against NAME.` A separate source reader checks emitted postings,
states and answers; unknown lines are refused. Programmatic references are not
independent human annotation. An additional independent packet/native audit is
required before interpreting live evidence.

```sh
python3 runner.py --prepare-only --out /new/packet
python3 runner.py --validate-packet --packet /prepared/packet
python3 runner.py --packet /prepared/packet --out /new/stub-results --stub
python3 -m unittest test_replication -v
```

Default preparation uses the already installed local tokenizer and its Python
interpreter, never downloads. Missing local files block packet preparation;
portable tests still run while local integration tests skip. The receipt checks
actual reference response tokens and serialized prompt bytes, including all
initialization. It is not a model timing or completion prediction.

A separately reviewed host owner can invoke the same wrapper with `--execute
--endpoint URL --model NAME --identity FILE`. The wrapper launches no model
server, cannot resume an existing result directory, and makes no transport
retries. It owns/reaps its CPU subprocesses on cancellation. Bounded model
failures remain in the four-trial matrix; infrastructure failure aborts remaining
trials and retains the unstarted manifest rows.

All old caps and generation policies are fixed. Preparation and every trial
boundary verify source/packet/tokenizer identities. Native policies and artifact
hashes are checked. Quality independently requires every accepted state, ordered
quoted semantic event sequence, and final answer to be exact. All attempts count
toward initialization/steady/answer costs. Paired outcomes are grouped by case
identity, never by the shared counter count. Cache-unknown or nonzero-cache runs
cannot support the descriptive timing comparison. No speed or holdout promotion
is granted by this wrapper.

The outer protocol is `sparse-state-replication-v1`; schemas are
`sparse-replication-plan.v1`, `sparse-replication-trial.v1`,
`sparse-replication-summary.v1`, and `sparse-replication-budget-receipt.v1`.
Native semantic trial labels identify low-level compatibility only. CPU
validation returns `{plan,budget,tasks}` through `runner.validate_packet(path)`;
the host calls this in an isolated interpreter to avoid bare-module collisions.
Timing for repeated CPU packet validation lies outside the native trial elapsed
time; source/initialization, model calls and all trial overhead remain recorded.
