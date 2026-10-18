# Review 15: standing screen cleanup and packet97 record-lane veto

CPU preparation is complete. No real cleanup, GPU work, service operation,
queue edit, sudo command or host setting change was performed. Commands used
nice 19, idle I/O priority, cores 8–15/24–31, Python `-B` and detached stdin.

The new [cleanup tool](../experiments/own-xpu-runtime/ops/screen-cleanup/README.md)
requires explicit packet closure and a reviewed DONE job. It archives only
driver-cache and input-bundles, preserves receipts and live references, reads
back every archived file including hard links, then rechecks the complete live
reference set before deleting exactly the verified files. One tar.gz and a
per-file SHA-256/size manifest are retained per run. Interrupted deletion can
resume using the verified full archive. Existing missing bulk is a no-op.

The [coordinator closure sample](../experiments/own-xpu-runtime/ops/screen-cleanup/closed.json)
includes packets76/78, packet86 diagnostics, packet90 H1 only, packets95/96,
83/81/79 and packet84s. Packet82 and packet90 E1/production remain live, along
with packets91–94 and 97–101. Packet84's record chain is not packet84s.

The final [dry run](../experiments/own-xpu-runtime/ops/screen-cleanup/plan-20261018.json)
read **1,100 live window/identity documents**. It found **156,771,508 bytes**
(156.8 MB) eligible across **22 runs**, **24 runs** already clear of eligible
bulk, and one refused packet84s run to skip. It retained 312 JSON receipts and
22 additional files protected by live references. These sizes reflect the
coordinator's earlier removals; they are not the size of the whole screen tree.
No archive was written to the real RAID destination by this task. The earlier
manual archive remains `/mnt/raid-models/own-xpu-runtime-archive/screen-bulk-20261018/`.
The coordinator must run a fresh plan before any execution.

Packet97's [review-15 entry](../experiments/own-xpu-runtime/ops/packet97-orchestration/README.md)
now checks completed lane-A confirmations as well as source grids. An inexact
result, loss or tie against either A control excludes the source choice from a
new decision. Source windows are checked again at decision time; a completion
or mutation during collection refuses the stale decision. Exclusion reasons,
comparison rows and evidence hashes remain in the decision.

The new CPU-only decision
[`584dea5a4fe379f1`](../experiments/own-xpu-runtime/ops/packet97-orchestration/decisions/584dea5a4fe379f1.json)
selects packet91's route/recurrence and packet90's half-cache. Packet93's
head-transpose is excluded: its completed A candidate is 53.906391 tok/s,
between controls of 54.959464 and 55.469037, **2.8171% below the stronger
control**. Its earlier B win does not override that result. These are existing
screen receipts, not new measurements or a record. No proposals or readiness
files were changed when recording the decision (`--decision-only`).

Both frozen decisions, `d27742791d5b859d` and `f1e5d7f47fc0fe54`, retain their
original bytes. Every original Python tool they pin also retains its bytes.
The amendment lives in a `review15/` subdirectory because the original helper
enumerates its immediate Python files when reconstructing a decision. Tests
check complete reconstruction of both old decisions, as well as their pins.
The corresponding new readiness verifier and manual entry preserve the new
exclusion evidence through later CPU preparation. Neither entry was launched
for device work.

**92 CPU tests pass** using the requested
`/home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest` with no pytest cache.
Tests cover actual mock archives, hard links within/across runs, byte recovery,
missing bulk, receipt retention, linked live evidence, partial closure, corrupt
archives, changed sources/live references, interrupted unlink/resume, latest A
losses, inexact results, pending screens, decision-time changes and frozen
decision compatibility. Shell syntax validation also passes. The
[test log](../experiments/own-xpu-runtime/ops/screen-cleanup/tests-review15.log)
and [validation receipt](../experiments/own-xpu-runtime/ops/screen-cleanup/validation-20261018.json)
bind the cleanup code and plan.

The initial `git pull --rebase` was blocked by existing staged and unstaged
work. A fetch confirmed local main matched origin/main. Other workers' commits
arrived during the task; their changes were preserved. Only this task's explicit
paths are included in its commit; live queues, running jobs and the existing
packet97 proposal/readiness changes remain with the coordinator.
