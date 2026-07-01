# Worktree Consolidation - 2026-07-01

Purpose: preserve current Gemma work and stop fragmenting active optimization
across detached worktrees.

## Actions Taken

- Confirmed `/home/steve/llm-optimizations` had no staged or unstaged tracked
  changes and was one commit behind `origin/main`.
- Confirmed `/home/steve/qwen36-results-main` had no staged or unstaged tracked
  changes and was detached at `4b33bb2f`.
- Confirmed `4b33bb2fda02d2f85c7101f5c5b34f4286d0e0db` is reachable locally
  and remotely:
  - `/home/steve/qwen36-results-main` detached `HEAD`;
  - `origin/main`;
  - local branch `preserve/gemma-mtp-postnormcombo-20260701`.
- Checked the fast-forward from `7e57a90b` to `origin/main` for untracked path
  collisions in `/home/steve/llm-optimizations`; result: `0` collisions.
- Fast-forwarded `/home/steve/llm-optimizations` to `4b33bb2f`.
- Later same-day canonical Gemma documentation/result commits advanced
  `/home/steve/llm-optimizations` through `46b4733d`, then the verifier-top2
  diagnostic preservation commit advanced it to `261300e0`. Subsequent
  workspace-policy commits keep the branch-attached checkout tracking
  `origin/main`; use `git log -1 --oneline` for exact live state.
  `/home/steve/qwen36-results-main` remains detached at `4b33bb2f` and is
  still archive/back-reference only.

## Current Worktree Topology

```text
/home/steve/llm-optimizations
  branch: main
  HEAD:   branch-attached main; verify exact commit with `git log -1 --oneline`
  role:   single active workspace

/home/steve/qwen36-results-main
  branch: detached
  HEAD:   4b33bb2fda02d2f85c7101f5c5b34f4286d0e0db
  role:   audit/back-reference only; do not run new work here

/home/steve/push-worktrees/b70-optimization-lab-pushable
  branch: detached
  HEAD:   0cb52e6999fadaf819440ad8b288b52ec0290cef
  role:   legacy/unknown; audit before reuse
```

## Untracked Backlog

No recent `20260701T140828Z-nospec-retest` or
`20260701T143822Z-mtp-postnormcombo-full512` artifacts were stranded as
untracked files; those result files are tracked in the pushed commits.

Current untracked inventory:

```text
/home/steve/llm-optimizations
  visible_untracked_count_after_ignore_cleanup: 2035
  visible_untracked_payload: ~0.041 GiB
  top-level split:
    data/: 2035
  pre-ignore raw artifact payload was ~2.663 GiB, mostly Qwen JSONL traces
  and local .safetensors checkpoints now ignored by default.

/home/steve/qwen36-results-main
  visible_untracked_count: 950
  visible_untracked_payload: ~0.307 GiB
  top-level split:
    data/: 950
```

These files may contain older useful benchmark evidence. Do not run
`git clean`, delete the detached worktree, or bulk-stage this backlog. Future
cleanup should classify the untracked `data/` files, promote valuable result
packets explicitly, and then archive/remove stale artifacts only after the
classification is recorded. See `notes/workspace-artifact-inventory-20260701.md` for the current inventory and ignore policy.

## Policy Going Forward

- Use `/home/steve/llm-optimizations` for all new optimization work.
- Treat linked/detached worktrees as read-only unless a task explicitly
  designates one as active.
- Keep active experiment output in the standard repo folders:
  `notes/`, `patches/`, `data/`, `results/`, `scripts/`, `experiments/`, and
  `repro/`.
- Commit focused changes regularly from the active workspace.
- Preserve failed and successful patches/results with enough run identity to
  reproduce them.
