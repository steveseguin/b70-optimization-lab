# Main-only repository consolidation

Date: 2026-08-14 America/Toronto

## Policy

This repository now uses `main` only for active work. Do not create feature,
experiment, promotion, temporary, or agent branches or worktrees. Preserve
experimental states as focused commits, patches, bundles, configs, notes, and
result artifacts.

## Preservation checkpoint

Before consolidating the historical worktrees and branch refs, every local and
remote ref plus every worktree HEAD was captured in this verified external Git
bundle:

```text
/home/steve/git-archives/llm-optimizations-pre-main-consolidation-20260814.bundle
SHA-256 cfa88752fb941a7a426e32a9a7d0776b0eb9d10909b113b81068b0554189a216
size    559 MiB
```

`git bundle verify` reported a complete history containing 27 refs. The bundle
includes the pre-consolidation experiment, maintenance, operations, review,
remote-tracking, detached-worktree, and `main` tips.

## Consolidation findings

- The rebased research tip was a direct descendant of `origin/main`, so moving
  it to local `main` was a normal fast-forward with no merge or squash.
- The detached Laguna segmented worktree's 13 commits were patch-equivalent to
  commits already present in the rebased history.
- The Laguna BF16 audit worktree had one genuinely missing documentation
  commit. It was recovered onto `main` as `docs: rank Laguna BF16 optimization
  directions`.
- Twenty small untracked Muse service-restore health records were classified as
  durable experiment evidence and promoted to `data/`.
- Generated CMake build trees and Python bytecode remain local-only and are now
  ignored. Their source, configs, logs, summaries, and relevant binaries or
  hashes remain preserved elsewhere in the experiment record.

Do not delete the external bundle until the pushed `main` clone has been
independently verified and any old remote branch refs have been retired.
