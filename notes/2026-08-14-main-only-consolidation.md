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

## Remote-ref classification

The pre-deletion audit classified every non-`main` ref:

- `origin/experiment/laguna-kernel-loop-20260728` had 497 patch-equivalent
  commits, seven superseded commits, and no paths absent from the final `main`
  snapshot.
- The detached Laguna segmented worktree had 13/13 patch-equivalent commits.
- The community, validation, topology, reboot-state, and storage refs were
  already ancestors of the consolidated history.
- `origin/codex/qwen36-quark-int8-tracking-achieved` at `a84d08e6a` and
  `origin/codex/qwen36-quark-int8-tracking-pushable-achieved` at `0cb52e699`
  retained old raw Qwen log backlogs. Those logs were intentionally not copied
  into the modern source snapshot because current repository policy keeps raw
  benchmark backlogs outside Git. Both complete histories and blobs are in the
  verified external bundle above.

The first consolidated push advanced `origin/main` normally, without force,
from `ce51350b8` to `6a64ba62f`. Local obsolete branch refs and secondary
worktrees were removed only after this push and archive verification. Remote
non-`main` refs can be retired after this ledger update is itself visible on
`main`; their recovery authority is the external bundle and checksum above.
