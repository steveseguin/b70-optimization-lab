# Durable context pilot

This is a new, opt-in research harness. It does not modify the running Harbor
campaign or replace the original CLM implementations. No model result is claimed
from its CPU tests or scripted stub.

## What changed

`ledger.py` commits incoming text to a host-owned SQLite database before the
model sees it. Quotes are checked against that original, not an editable
conversation. Event IDs, canonical quote positions and batch IDs support ordered,
transactional application. Identical replay is harmless; conflicting or duplicate
application is refused. Original text, event receipts and state survive restart.
The model has no shell or filesystem tool and never receives the database path.

The supported operations are set, add, subtract, remove and reopen. A valid quote
and amount do **not** establish that the operation is semantically right or that
all changes were extracted. Identical repeated source sentences are currently
handled conservatively; explicit occurrence identifiers are future work. Host
administrators can still alter files: "immutable" refers to the application API
and database triggers, not protection from the machine owner.

`tasks.py` makes deterministic narrative streams with eight counters and exactly
24 final questions: eight current values, eight historical seals, and eight
cross-reference questions joining a late review ID to an early ticket and a past
counter value. Hidden reference states and events support independent grading.
The runner passes only source text and questions to the real model client.

`pilot.py` compares three complete systems:

| Arm | Working memory | Source access at the end |
| --- | --- | --- |
| summary | Periodic model-written summary plus recent batches | Literal search and fetch |
| archive | Model-written state table and short index | Same search and fetch |
| quoted | Quoted events applied by code, plus a short model-written index | Same search and fetch |

All arms receive identical original batches and final questions, have the same
32,768 **UTF-8 byte** prompt limit, use thinking off, and may make at most 24 final
retrieval calls. This is deliberately a byte budget, **not** a claimed 32K model
token window. Report actual prompt tokens separately when the server provides
them. There is no silent truncation of working memory or source records; a
retrieved excerpt says when it is truncated, and older retrieval results may be
evicted from the working prompt while the complete source remains in the store.

Model calls, malformed replies and refusals are logged. Retries after an event
validation failure are bounded at three attempts. A transport error ends the
attempt; no server is restarted. Recovery retains all logged calls and marks
elapsed timing incomplete, so a resumed run cannot earn a speed result. Only an
incomplete final JSONL record may be repaired after a crash; its bytes are kept.
An invalid complete record is an error.

## CPU validation and smoke

From the lab root:

```bash
D=experiments/qwen38-27b-b70/scripts/context/durable
python3 -m unittest discover -s "$D" -p 'test_*.py'
python3 "$D/tasks.py" --out /tmp/context-dev --seeds 7 --batches 12 --filler-words 150
python3 "$D/campaign.py" --suite /tmp/context-dev/suite.json --out /tmp/context-stub --stub
python3 "$D/extraction.py" --task /tmp/context-dev/report-seed7.json --out /tmp/context-extraction-stub --indices 1 2 3 4 --stub
```

The stub deliberately uses the hidden answer key to test plumbing. Its outputs
are labeled `measurement_kind=stub`, have no measured token usage and cannot
pass a model-quality or speed gate. Do not put them in model benchmark tables.

## Freeze the evaluation before inference

The checked-in pilot protocol is
[the preregistration](../../../notes/2026-10-06-durable-context-prereg.md).
The task files are checked in under `data/2026-10-06-durable-context`.
Seeds 101, 202 and 303 in both report and dispatch styles give six cases, eighteen
trials across the three arms. Each case uses 48 batches. These are new task seeds
for this harness, not evidence of generalization to natural documents.

```bash
DATA=experiments/qwen38-27b-b70/data/2026-10-06-durable-context
python3 "$D/campaign.py" --suite "$DATA/holdout/suite.json" --out /tmp/context-pilot
```

The campaign command writes a frozen plan and sends **no requests**. Plan and run
identities bind task bytes, module hashes, arm, budget and server identity. A
changed source or task requires a new campaign directory and a recorded revision.

## Run only after the protected campaign releases the endpoint

First use development seed 7 for the one-step extraction diagnostic. Each call
gets the true state before a batch; errors therefore measure extraction without
compounding memory loss. Its quote-format comparison is conservative and is not
a semantic-equivalence grader. The development gate requires 100% exact events in source order on batches
1, 2, 3, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 47 and 48, in both styles
of the frozen seed-7 task (53 events per style). A smaller diagnostic cannot
unlock the holdout. Keep the holdout unused if
that diagnostic fails; record a new implementation before trying again.

```bash
SERVER_IDENTITY=/path/to/qualified-server-launch.json
RUNS=/mnt/fast-ai/bench-results/context-durable-v1
python3 "$D/extraction.py" --task "$DATA/development/report-seed7.json" \
  --out "$RUNS/extraction-report" --endpoint http://127.0.0.1:18196/v1 \
  --server-identity "$SERVER_IDENTITY"
python3 "$D/extraction.py" --task "$DATA/development/dispatch-seed7.json" \
  --out "$RUNS/extraction-dispatch" --endpoint http://127.0.0.1:18196/v1 \
  --server-identity "$SERVER_IDENTITY"
python3 "$D/campaign.py" --suite "$DATA/holdout/suite.json" \
  --out "$RUNS/pilot" --execute --endpoint http://127.0.0.1:18196/v1 \
  --server-identity "$SERVER_IDENTITY" \
  --calibration "$RUNS/extraction-report/result.json" "$RUNS/extraction-dispatch/result.json"
```

The campaign checks both calibration results against the frozen task, code,
budget and server identity before it sends any holdout request.
The runner refuses a host with an existing Harbor process and serializes the new
pilots through one host-level lock. These checks complement the lab's process,
memory and GPU-health preflight; they do not replace it. The harness never starts,
stops or restores a model server. The experiment owner must use the qualified
server lifecycle and stop that server when the experiment is over.

## Evidence and decisions

Keep this pilot separate from legacy scores: assistance, retrieval permissions,
working-memory accounting and tasks differ. Compare arms only within its frozen
identity. Report final correctness by category, per-batch state checks where
observable, omissions/extra events in the extraction diagnostic, retries,
completions, total elapsed time and prompt/output usage. Summary state is not
silently treated as an exact table; its intermediate-state metric is unavailable.

The shared [legacy trial exporter](../evidence/README.md) currently supports
Harbor and the frozen review bundle. It does not ingest this new pilot format;
its native `result.json` and `summary.json` remain explicitly separate evidence
until a validated adapter exists. No new pilot rows are added to the website.
