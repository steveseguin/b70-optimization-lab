# Workspace Artifact Inventory - 2026-07-01

Purpose: keep one active workspace while preserving historical experiment
artifacts without accidentally committing large raw logs, traces, model files,
or stale detached-worktree output.

## Active Workspace

Use `/home/steve/llm-optimizations` for all new optimization work. It is the
branch-attached `main` checkout and should track `origin/main`; run
`git status --short --branch` and `git log -1 --oneline` for exact live state.

Do not start new work from `/home/steve/qwen36-results-main`. That checkout is
a detached audit/back-reference worktree at `4b33bb2f`; the commit is reachable
from both local `main` and `preserve/gemma-mtp-postnormcombo-20260701`, and was
reported pushed to `origin/main`.

## Inventory Snapshot

Refresh on 2026-07-02 after pushing `606a4a4c`:

```text
/home/steve/llm-optimizations
  branch: main
  state: clean; origin/main matches local main
  visible untracked count: 0

/home/steve/qwen36-results-main
  branch: detached
  HEAD: 4b33bb2fda02d2f85c7101f5c5b34f4286d0e0db
  tracked dirty entries: 0
  visible untracked count: 2920
  top-level split: data/: 2920
  total worktree size: ~1.6G
```

The recent postnorm-combo/no-spec result clusters checked during this refresh
are already present in `/home/steve/llm-optimizations` and tracked on `main`.
Do not run new work from the detached checkout. Do not bulk-add or delete the
detached backlog; either promote named result packets into the active checkout
or archive/remove the entire detached worktree after explicit approval.

Branch cleanup follow-up: local branch labels now only include `main`. Two
remote Qwen `origin/codex/*-achieved` refs remain as remote archives. The local
artifact-heavy branch was converted to local tag
`archive/qwen36-artifact-heavy-20260628204326`; the tag was not pushed because
that history contains a multi-GB artifact object.

Measured again on 2026-07-01 after adding ignore rules for historical raw
`data/qwen36-*` and `data/xpu-recovery-*` backlogs. No files were moved or
deleted. The old artifacts remain on disk for audit, but they no longer swamp
`git status` in the active workspace.

```text
/home/steve/llm-optimizations
  tracked dirty entries before this update: .gitignore only
  visible untracked status entries after ignore cleanup: 41
  visible untracked payload walked from those entries: ~1.31 MiB
  visible untracked class: recent Gemma compact evidence only
  large/model artifacts visible to Git: 0

  previous visible untracked count before this cleanup: 2094
  previous split: data/gemma4* = 41, data/qwen36* = 2026, data/xpu-* = 27

/home/steve/qwen36-results-main
  tracked dirty entries: 0
  detached at: 4b33bb2fda02d2f85c7101f5c5b34f4286d0e0db
  visible untracked status entries: 2920
  visible untracked payload: ~114.76 MiB
  role: audit/back-reference only; do not run new work here

/home/steve/push-worktrees/b70-optimization-lab-pushable
  tracked dirty entries: 0
  visible untracked status entries: 0
  detached at: 0cb52e6999fadaf819440ad8b288b52ec0290cef
  role: legacy/unknown; audit before reuse
```

The 41 active-workspace Gemma files are compact run evidence for the same-day
record reproduction / long-context phase ladder / ncols8 control lanes. They
should be committed explicitly with their corresponding ledgers, not hidden by
broad ignore rules.

Largest historical heavyweight artifacts before earlier ignore cleanup were ten
Qwen EAGLE training checkpoints under
`data/qwen36-eagle3-rollout5-residualextra-oldonly-ckpt-trained-20260618s/checkpoints/`
(~214 MiB each). These are local audit artifacts, not Git payloads.

## Policy

- Commit curated summaries, ledgers, repro scripts, and source patch snapshots.
- Keep raw server logs, JSONL traces, model/checkpoint/tensor artifacts, and
  `.pause-*` files local-only unless a future task explicitly force-adds a
  small artifact as evidence.
- Do not run `git add -A` in mixed experiment worktrees. Stage explicit paths.
- Do not run `git clean` or delete the detached worktree until its untracked
  data has been reviewed or intentionally archived.
- All future Gemma 26B optimization output should be created in the canonical
  repo folders under `/home/steve/llm-optimizations`: `experiments/`,
  `patches/`, `data/`, `results/`, `repro/`, `scripts/`, and `notes/`.

## Safe Next Commands

```bash
cd /home/steve/llm-optimizations
git status --short --branch

# Stage documentation/policy changes explicitly.
git add .gitignore AGENT_HANDOFF.md CURRENT.md \
  results/gemma4-26b-a4b-q8-b70/reliability-protocol.md \
  notes/worktree-consolidation-20260701.md \
  notes/workspace-artifact-inventory-20260701.md

# For future experiments, force-add raw logs only if they are deliberately part
# of a small evidence packet:
# git add -f data/<specific-run>/<specific-log>.log
```
