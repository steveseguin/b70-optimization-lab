# Durable context revision 2

This separate implementation preserves the failed first pilot and its frozen
`../durable/` sources. The [plan](../../../notes/2026-10-07-durable-context-r2-plan.md)
records the repair, development gate and fresh held-out seeds.

All three arms (summary, archive, quoted events) retain identical original source
in a transactional SQLite store. Quote checking establishes provenance and exact
application of accepted updates; it does not prove complete semantic extraction.
The model has no shell or filesystem tool and receives no hidden answer key.

The final-answer protocol saves partial answers independently of the bounded
working prompt. Replies choose `search`, `fetch`, `update` or `submit`. A mixed
legacy `answers` and `search` response saves its answers and retrieves evidence;
it never finishes implicitly. Submission requires all question IDs, with null
accepted as an explicit unknown and scored wrong. Values may be revised.

Exact batch fetch and search with numeric boundaries avoid confusing batch 2
with batch 20. Duplicate retrieval restores cached evidence without consuming
another retrieval slot; each reply still consumes an action. Valid zero-hit
searches count, refused batch IDs do not. Questions, saved answers, missing IDs,
feedback and budgets stay visible. Older retrieved evidence can leave the prompt
but remains cached. If the newest evidence cannot fit even after dropping working
memory, the prompt explicitly asks for a narrower search.

There are at most **32 answer calls** and **24 distinct retrieval operations**.
An action slot is saved before sending the request. Logged replies replay after a
crash; saved partial answers and budgets survive restart. A resumed trial cannot
earn a speed result. Transport failures end the attempt without server retries.
Malformed replies consume an action and receive format feedback, never correctness
feedback. The working input budget is **32,768 UTF-8 bytes**, not 32K model tokens.

The frozen tasks contain eight current, eight historical and eight cross-reference
questions. Development is seed 7 in report and dispatch styles, all three arms,
48 batches and 320 filler words. All six full model trials must complete cleanly
with 24/24 answers, after both fixed extraction diagnostics pass. The holdout gate
regrades native answers and binds tasks, source, runtime, budgets and history.
Fresh held-out seeds are 401, 502 and 603 in both styles (18 trials). Seeds 101,
202 and 303 belong to the inspected first pilot. No general-document or unlimited
context claim follows from either synthetic pilot.

CPU checks:

```bash
python3 -m unittest discover -s experiments/qwen38-27b-b70/scripts/context/durable_v2 -p 'test_*.py'
python3 -m unittest discover -s experiments/qwen38-27b-b70/scripts/context -p 'test_durable_v2_host_runner.py'
```

Freeze without any model request:

```bash
D=experiments/qwen38-27b-b70/scripts/context/durable_v2
DATA=experiments/qwen38-27b-b70/data/2026-10-07-durable-context-r2
python3 "$D/campaign.py" --stage development --suite "$DATA/development/suite.json" --out /tmp/context-r2-development-plan
python3 "$D/campaign.py" --stage holdout --suite "$DATA/holdout/suite.json" --out /tmp/context-r2-holdout-plan
```

A stub may exercise the complete workflow but deliberately reads the oracle;
its results are labelled and never pass the model gates. Actual GPU work uses
`../durable_v2_host_runner.py`: passive `--prepare`, then one supervised `--execute`
with the lab's qualified server profile and health/strict checks. It stops its
server on success or failure. Never execute beside another GPU owner.

Native `result.json`, campaign summaries and partial-failure summaries remain
separate from legacy site rows. No speed comparison qualifies without complete,
correct, unresumed paired trials. Keep failed outcomes as part of the record.
