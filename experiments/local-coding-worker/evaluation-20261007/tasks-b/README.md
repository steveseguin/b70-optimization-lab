# Historical coding cases B — October 7, 2026

Four new task IDs, each using an actual historical bugfix's immediate parent
as its baseline and the actual fixed commit as a positive control. No bugs
were injected. The requested `ml-bottleneck` checkout was absent on this host,
so these cases use older lab command-line and reporting fixes instead.

| Task | Observable failure | Acceptance scope |
| --- | --- | --- |
| `lab-oracle-request-ids` | Separate benchmark runs cannot namespace their request IDs | Real CLI main; isolated/default namespaces, uniqueness, normalized IDs, invalid-input rejection, unchanged counts and output qualification |
| `lab-oracle-pinned-subset` | A larger valid frozen oracle is refused | Real CLI main; reordered superset/equal set, selected order, digest binding, no regenerated oracle, missing/changed/duplicate/invalid IDs rejected before transport |
| `lab-stream-token-identity` | Streamed token values are discarded | Real stream parser; ordered IDs, compact digest, chunk independence, same text/different IDs, incomplete and absent metadata |
| `lab-release-query-failure` | Failed release queries are reported as empty releases | Real lookup and package scanner; unavailable versus empty, warnings, cache, missing-asset findings only when established |

`tasks/*.json` uses the existing `worker/tasks` schema. Mount only
`acceptance/` at `/acceptance`; both oracle cases also need its shared
`oracle_fixture.py`. Acceptance code is Python standard library only. HTTP
transport and GitHub CLI queries are mocked; no model, network, GPU, Docker
or system service is used by these acceptance checks. They run from the
baseline workspace root and do not require `.git`.

The independent acceptance fixtures use different inputs and broader behavioral
checks than the historical commit tests. They do not require copying a golden
patch or matching a specific implementation. Public API/output-field contracts
needed by acceptance are stated in each issue.

## CPU controls and evaluator separation

**All eight controls passed:** each baseline fails with its declared diagnostic
marker and each fixed commit passes. See
[`evaluator-only/controls-01/receipt.json`](evaluator-only/controls-01/receipt.json)
for exact commits, source hashes, selected archive paths, sizes and test output.
The largest disposable archive was well below 1 MiB. No full repository
snapshot was created, and original repositories were not modified.

Reproduce controls with a new output directory:

```bash
python3 -B experiments/local-coding-worker/evaluation-20261007/tasks-b/evaluator-only/verify_controls.py \
  --repo /home/steve/llm-optimizations \
  --out /tmp/coding-controls-b-new
```

The verifier uses `git archive` for the exact relevant source files and their
runtime import dependencies, extracts to disposable directories without Git
metadata, and invokes the independent acceptance checks with 30-second limits.
It checks selected Git blob sizes before archiving and enforces a 32 MiB archive
cap. The cap-enabled verifier was replayed successfully for all eight controls;
new receipts additionally record source bytes and the cap.
The archive scope is recorded explicitly; this is not validation of the whole
historical repository or its unrelated tests.

**Keep `evaluator-only/` out of the model's task input and sandbox.** It contains
the fixed commits and validation receipts. Task JSON contains only the baseline
commit, natural issue, acceptance command and expected failing marker. The
canonical worker's full snapshot policy is unchanged; model runs still require
separate disk-budget admission and an authorized endpoint.

These cases are new relative to the eight existing `worker/tasks` IDs and do
not overlap set A's catalog, worker-reasoning, action-latency or number-boundary
cases. The two oracle cases share a source family and should not be described
as independent repository coverage. Historical source may have been publicly
available or encountered in earlier unrelated work; these are not a claim of
training-data secrecy or guaranteed model-unseen code. No model trials have
been run for this packet.
