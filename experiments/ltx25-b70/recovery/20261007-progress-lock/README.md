# Progress-display lock recovery candidate

**CPU regression reproduced and candidate passed; nothing is installed.**
The October 6 disk-full incident left the LTX sampler waiting for a `tqdm`
progress-display lock while the other pipeline workers were idle. This packet
preserves a small future-runtime fix and an executable reproduction. It does
not restart LTX or change packet 97, packet 98, the installed virtualenv or
any archived launcher.

## What the patch does

The installed `tqdm` 4.70.1 `refresh()` acquires its display lock, calls
`display()`, then releases the lock. If display raises an exception, including
`OSError(ENOSPC)`, the release is skipped. Another thread can then wait forever
on a progress update even though no model calculation is underway.

[`progress-lock.patch`](progress-lock.patch) puts display inside `try/finally`
and releases the acquired lock in `finally`. The original exception still
propagates, so a failed write is not hidden or reported as success. Successful
display behavior, return values, the disabled path, nonblocking `lock_args`
refusal and caller-managed `nolock=True` behavior are retained.

The patch is based on the **exact locally installed file**, not a claim that
the package is pristine upstream:

- Source: `/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/tqdm/std.py`
- Version: `4.70.1`
- SHA-256: `dd76d965de52c590819dec376644220cb35dc4831e40efb4c30944884fc57d86`
- Frozen source: [`std.py.original`](std.py.original), 58,047 bytes.
- Identity and patched-full-source digest: [`identity.json`](identity.json).
- Original tqdm authorship and license: [`TQDM-LICENCE`](TQDM-LICENCE), copied
  from the installed distribution alongside the preserved source.

## Reproduction

From the repository root:

```bash
timeout 15 /home/steve/.venvs/ltx25-baseline/bin/python -B \
  experiments/ltx25-b70/recovery/20261007-progress-lock/test_progress_lock.py
```

This uses only CPU code, the standard library, the already-installed `tqdm`
and the system `patch` utility. It creates a disposable source copy under
`/tmp`, applies the patch with zero fuzz, verifies the full candidate hash,
and checks that the candidate method is exactly the patched source. It does
not import Torch, read model weights, contact an endpoint, signal a process,
or alter the installed package.

**10 tests passed** in about 0.15 seconds. The tests:

- deterministically raise ENOSPC from display and demonstrate that the
  original leaves another CPU thread unable to acquire the lock;
- show that the candidate propagates the same exception, releases the lock,
  allows another thread through and supports a subsequent refresh;
- exercise `lock_args`, `nolock`, disabled display and `KeyboardInterrupt`;
- compare actual `tqdm` rendered output on successful updates using local
  subclasses with monitoring disabled;
- verify source, patch application and candidate hashes.

Results and the initial test-harness correction are in
[`result.json`](result.json); exact passing output is in [`tests.log`](tests.log).
The first attempt passed the behavioral tests but its source comparison
mistakenly compared differently indented docstrings. Comparing consistently
dedented source fixed that test; the candidate patch did not change.

## Limits and next use

The incident stack is consistent with this lock leak, and the CPU test proves
that this exact source can leak the lock after ENOSPC. It does not identify
the original lock owner or prove that this was the only cause of the incident.
The patch cannot release a lock already leaked in another running process.
It does not repair incomplete outputs or provide disk-space admission control.

This patch only repairs exception cleanup around `refresh()` display. It does
not change errors during lock acquisition/release, fix every other progress
display path, or certify model-output parity, GPU teardown or production
stability. Normal rendering is tested with a deterministic text format;
terminal-specific behavior is not exhaustively covered.

For future adoption, build an isolated successor runtime from the recorded
source and patch, verify the hashes and repeat the CPU tests before any model
work. Include disk-full admission and artifact-write failure handling in that
runtime's review. Preserve sealed historical packets and installed runtime
state; do not retrofit this candidate into them. The owner must resume the
LTX lane before any GPU validation or server launch.

Incident evidence:
[shutdown/source review](../../notes/2026-10-06-enospc-stop-review.md),
[nonblocking stack snapshot](../../../../data/maintenance/consolidation-20261006/ltx-python-stacks.txt).
