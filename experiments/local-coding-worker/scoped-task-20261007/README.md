# One explicitly scoped worker task

**Closed: 0/1 completed repairs, empty patch after 12 steps.** See [closeout](CLOSEOUT.md).
The following records preparation before that attempt.

This packet preserves the unused `lab-worker-action-ready-latency` issue and its
exact pinned bug commit unchanged. It adds an explicit dependency projection in
`task.source_paths` and one permitted new regression file,
`worker/test_action_ready_latency.py`. Existing collector and stream regression
tests remain available. The selected pinned root/ancestor instructions are added
automatically; no source snippets are edited or selected around a proposed fix.

This is a new, narrowed protocol with coordinator-supplied file locations and
smaller source exposure. It is not the original full-repository held-out evidence
class and cannot establish a controlled quality improvement over earlier failed
tasks. At preparation time no model attempt or GPU action had occurred. The authorized pinned CPU
container controls passed on both scoped snapshots and both containers stopped;
see `preparation.json` for the receipts and isolation checks.

The original acceptance command remains unchanged. Only its exact acceptance
script may be mounted at `/acceptance`; never mount the original evaluation
folder, historical validation receipt, fixed snapshot, gold patch or review-only
controls. Model input is the unchanged issue plus the worker's explicit scope
notice and the selected baseline workspace. `source-scope.json` and
`preparation.json` are coordinator receipts, not additional model instructions.

The source set includes the named implementation, its direct standard-library
module dependencies and the exact source files hashed by existing collector
regressions, plus three existing regression files. No model/server is started
by this preparation. The worker retains its default 50 GiB storage reserve;
scoping reduces initial source writes but does not reserve disk or limit later
tool writes. Actual planning and CPU closure controls are recorded in
`preparation.json`; the main runner owns clean-source admission and any later
real CPU-sandbox/model trial.
