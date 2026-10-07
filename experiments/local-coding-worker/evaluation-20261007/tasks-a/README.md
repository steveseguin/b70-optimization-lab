# Worker evaluation: four historical bug repairs, set A

Four new task cases, with real buggy parent commits and real fixing commits.
**All four baselines fail their registered marker; all four fixed snapshots
pass. No model attempt has run.** These cases were not in the prior worker task
set. They measure repair ability on held-out historical issues, not four new
production fixes or broad autonomous reliability.

| Task | Intended behavior | Acceptance |
| --- | --- | --- |
| `lab-catalog-pending-headlines` | Render null/absent metrics honestly; keep sorting/filtering working | Node DOM/transport stubs execute the real inline UI |
| `lab-worker-canonical-reasoning` | Preserve assistant reasoning identically for tokenizer and generation | Actual adapter query with fake transport, no endpoint |
| `lab-worker-action-ready-latency` | Reject impossible action timing while accepting valid evidence | Actual collector with valid and invalid timing records |
| `lab-context-number-boundaries` | Keep narrative amounts separate; exclude identifier digits | Actual number parser with punctuation, identifiers, signs and compounds |

The task JSONs match `worker/run.py`'s task schema. They contain natural issues
and baseline commits only. `acceptance/` contains independent checks without
solution code. `validation/` contains the **separate evaluator-only gold fixes**,
fixed-commit identities and complete CPU stdout/stderr receipts. Do not mount
that directory into a worker task or copy it into a source snapshot. Baseline
commits predate this evaluation packet; normal `git archive` snapshots contain
neither this packet nor later fix history. The gold patch for action timing and
the number-parser patch come from broader real commits; the task/check scopes
only the behavior described in the issue.

Run all controls from the repository root, using Python 3.12+ for safe archive
extraction and an installed Node:

```bash
python3 experiments/local-coding-worker/evaluation-20261007/tasks-a/validate_controls.py --repo .
```

This verifies task/acceptance/gold hashes, then extracts each pinned source
projection into a temporary directory and executes acceptance. It never
creates a branch, checks out the live repo, starts Docker or contacts a model.
Each archive and extracted tree is limited to 32 MiB; temporary files are
removed after each control. `validation_paths` records exact source scope:
catalog checks use `guides.html` and `packages/catalog.json`; reasoning uses
`worker/model.py`; action timing uses `worker/` plus its two ordinary Python
helper modules; number parsing uses `ctxfold.py`. Every file is unmodified
`git archive` content. No buggy source was manufactured.

Recorded host controls used Python 3.12.3 and Node 18.19.1. Acceptance scripts
use standard libraries compatible with the worker's Python 3.11 / Node 22
image, but **container replay has not run**. `controls-replay.json` records
the independent repeat. Scoped controls establish behavior and dependencies
for these checks, not complete repository test coverage or full-snapshot size.

Integration remains with the campaign harness: mount only these acceptance
files read-only, enforce the baseline commit/expected failure before generation,
and retain failed attempts. Do not let a task run modify shared runtime/GPU
settings; this is CPU software work. Independent patch review must reject
hardcoded fixture answers, disabled validations or edits to acceptance checks.
The reasoning case is intentionally small; report per-task outcomes rather
than letting a high aggregate score hide harder failed tasks.
