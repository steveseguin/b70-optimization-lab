# Historical accepted-state retrieval: development engine

This separate engine adds `state_at` to archive and quoted trials. It copies the
frozen semantic engine; `copied-source.json` identifies the original files.
No old engine is imported or modified. There is no outer study, server launcher,
holdout admission, or speed claim. Task schemas and scoring helpers remain
compatible with the copied semantic compiler; native trial evidence uses
`history-live-trial.v1` and protocol `historical-state-development-v1`.

`live.run_trial(task, arm, out, client, identity=None, retrieval_mode='history')`
runs a fresh trial with arm `archive` or `quoted`. The keyword-only retrieval mode
is `history` (default) or `source-only`, and is bound into native identity/results.
Both modes persist and verify exactly the same snapshots. Only the answer
instruction and permission to dispatch `state_at` differ. Source-only mode uses
the frozen semantic answer instruction byte-for-byte and rejects a guessed
`state_at` with ordinary protocol feedback, even if a cache entry exists.
The CLI currently permits CPU stub wiring only:

```sh
python3 live.py --task /path/to/compiled-task.json --arm archive --out /new/output --stub
python3 live.py --task /path/to/compiled-task.json --arm archive --out /new/control --stub --retrieval-mode source-only
python3 -m unittest test_history -v
```

Stub output uses an explicit oracle fixture and is always labeled `stub`.
The copied HTTP client is available to a future reviewed study wrapper; these
tests and preparation make no HTTP/model requests.

After each accepted batch, `SnapshotStore.save(batch_id, state, source_text,
raw_response)` persists the arm's actual local state. Archive tables retain all
accepted string keys and integer values, including incorrect, missing and extra
entries. Quoted tables come from the code ledger after accepted events. The
store receives no task, private reference, oracle or diagnostic metrics. It does
not read source text to reconstruct or correct values. Source text and raw model
content enter only as provenance hashes, alongside the state hash and previous
snapshot hash. Native call logs retain the original content separately.

Snapshots use exclusive creation and fsync, with in-memory hashes anchoring
subsequent reads. There is no update/delete/resume interface. A save failure,
including one after quoted ledger application, aborts as infrastructure without
retrying the batch. Rejected model attempts never produce snapshots. Native
results bind every snapshot file in their artifact hash map.
Before successful finalization, the engine verifies the exact snapshot inventory
and every immutable hash anchor, including snapshots the model never queried.
Missing, modified or unexpected snapshot files abort as infrastructure failures
while preserving the native trace, original acceptance receipts and available files.

The answer action is:

```json
{"action":"state_at","batch_id":2,"counters":["amber10"]}
```

It returns the accepted state at the end of exactly one batch, a receipt, and
explicit `missing_counters`; omission never means zero. Omit `counters` to fetch
the whole table. A filter accepts 1–256 unique nonempty strings, each at most 128
UTF-8 bytes, and at most 4096 bytes for the serialized list. Unknown batches
return an error. Invalid queries cannot multiplex several batches. Snapshot
integrity/read failures are infrastructure failures, not model feedback.

Source `search` and `fetch` remain available for ownership and narrative facts.
All three retrieval actions share the original 24 successful distinct retrieval
budget; cached repetitions consume another answer call, without another retrieval.
Counter selections are sorted before caching, so list reordering does not create
a new request. The 32-answer-call cap, 32768 prompt-byte cap, 6553 memory-byte cap,
three ingestion attempts, ingestion prompts, thinking-off 4096 ingestion tokens,
and medium-thinking 8192 answer tokens are unchanged. Only answer instructions
introduce the new action. Oversized evidence follows the existing bounded prompt
policy; the model can request a smaller counter selection.

The tests include wrong archive history, missing values, provenance receipts,
immutability/tampering, rejected-attempt exclusion, write-after-ledger failure,
read failures, bounded queries, shared budgets and all 24 authored-case/arm CPU
gold wiring trials. These are implementation checks, not evidence that model
accuracy or speed improves.

The separate [snapshot auditor](../audit_history_snapshots.py) reconstructs saved
states from raw accepted replies, checks snapshot provenance and returned
historical evidence, and retains failed-write gaps. Run it with `--result-dir`
and `--task`; its twelve CPU regressions include re-bound hashes and altered
refused replies. It checks evidence integrity only: `quality_passed` remains
unknown. Full trial quality and any study-level gate need separate native and
reference audits.
