# Bounded coding-worker and lab-memory preparation

Owner direction: take charge of the agreed priorities, eventually connect the
coding worker and context/memory work, and avoid getting lost in narrow tuning.
The four-card host remains idle; the two-card context owner was not contacted.

## Delivered

The [evaluation packet](../experiments/local-coding-worker/evaluation-20261007/README.md)
contains eight genuine historical repair tasks and ten source-backed lab
questions. The coding tasks use real pre-fix commits, not manufactured bugs.
Independent checks cover both valid behavior and important negative cases.
Evaluator-only historical fixes/receipts and memory reference answers are
separate from model-facing material. They must remain outside worker mounts.

The first trial is deliberately two tasks, once each, with the existing readable
observations profile and bounded effort. Correct, independently reviewed patches
are the primary measure. No model-quality or long-context capacity result has
been claimed from the CPU preparation.

Added `worker/run.py --acceptance-dir` without changing its default directory or
inference profile. It validates regular files, records their exact identity,
mounts them read-only, checks identity before generation and after the sandbox
stops, and refuses acceptance after a host-side check change. Independent review
caught the need for those final identity checks; that correction is included.
The receipt is for inspection; old overnight collectors do not yet validate it.
Host checks are not an immutable filesystem snapshot or protection against a
concurrent writer that changes and restores files between checks.

## Validation and limits

- All eight historical baselines fail their registered bug marker and all eight
  historical fixed revisions pass: sixteen CPU controls. These run bounded,
  explicitly scoped Git archives; no branch, checkout, Docker or GPU work.
- Fourteen runner tests pass; seventeen sandbox tests pass with one optional
  Docker test skipped; nine cycle-guard tests pass.
- Memory integrity checks pass for five full frozen documents, ten questions,
  thirty rubric criteria and eleven negative response/citation cases. Structural
  validation deliberately does not assign semantic correctness.
- Broad worker discovery attempted106 tests but could not complete: fourteen
  error reports arise from missing `minisweagent` in this host Python, with one
  Docker test skipped. Do not report the whole suite as green. The targeted
  dependency-free checks above cover this change; pinned-environment and
  container replay remain required before actual trials.

At review, root available space was57,749,237,760 bytes (53.78GiB), with a50GiB
reserve. The intended worker venv, sandbox image, official27B FP8 model and R314
runtime inputs are absent here. Full worker snapshots need three source copies
plus run output. No runtime installation, model download, server launch or
protected-host request was performed to work around these constraints.

## Decision

Stop expanding the evaluation tooling now. The next useful measurement is the
small coding trial when an admitted qualified runtime is available, then the
source-backed memory baseline. Connect them only after useful behavior is
measured. Keep the next package milestone as real end-to-end TP2 qualification;
LTX and Flash-Next retain their existing resume records and remain parked.
