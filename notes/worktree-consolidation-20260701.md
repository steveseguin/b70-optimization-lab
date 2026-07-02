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
  `/home/steve/llm-optimizations` through the verifier-top2 diagnostic and
  candidate-proof diagnostic preservation commits. At this refresh the active
  branch-attached checkout is `d3bee04a` and tracks `origin/main`; use
  `git log -1 --oneline` for exact live state.
  `/home/steve/qwen36-results-main` remains detached at `4b33bb2f` and is
  still archive/back-reference only.
- Removed the legacy detached `/home/steve/push-worktrees/b70-optimization-lab-pushable`
  worktree after confirming its state had already been preserved/reachable.

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

No other linked worktree is active. Do not create another one unless the task
explicitly requires isolation; if one is created, document why, how to merge it
back, and when it should be removed.
```

## Untracked Backlog

Refresh on 2026-07-02:

- `/home/steve/llm-optimizations` is clean on branch-attached `main` at
  `606a4a4c`, with `origin/main` matching after push.
- `/home/steve/qwen36-results-main` remains detached at `4b33bb2f`, with no
  tracked dirty state.
- The detached worktree still has a large untracked `data/` backlog:
  `2920` visible untracked files, total worktree size about `1.6G`.
- The newest useful postnorm-combo/no-spec packets checked during the refresh
  are already present in the active checkout and tracked on `main`, including
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-mtp-postnormcombo-full512.md`
  and the `20260701T143822Z-mtp-postnormcombo-full512` result packet.

No recent `20260701T140828Z-nospec-retest` or
`20260701T143822Z-mtp-postnormcombo-full512` artifacts were stranded as
untracked files; those result files are tracked in the pushed commits.

Current untracked inventory:

```text
/home/steve/llm-optimizations
  current visible untracked count: 0 after `d3bee04a`
  role: clean active workspace for new work
  historical note: pre-ignore raw artifact payload was ~2.663 GiB, mostly Qwen
  JSONL traces and local .safetensors checkpoints now ignored by default.

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
- Do not create new worktrees as scratch space by default. Prefer branches,
  patch snapshots, and standard result folders inside the active workspace.
- Keep active experiment output in the standard repo folders:
  `notes/`, `patches/`, `data/`, `results/`, `scripts/`, `experiments/`, and
  `repro/`.
- Commit focused changes regularly from the active workspace.
- Preserve failed and successful patches/results with enough run identity to
  reproduce them.
