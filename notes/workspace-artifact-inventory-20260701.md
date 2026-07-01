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

Measured after adding ignore rules for raw benchmark traces/logs/checkpoints.
No files were moved or deleted.

```text
/home/steve/llm-optimizations
  tracked dirty entries before this note commit: docs/.gitignore only
  visible untracked status entries: 2035
  visible untracked payload walked from those entries: ~0.041 GiB
  root split: data/: 2035

  previous pre-ignore raw artifact payload: ~2.663 GiB
  heavyweight class now ignored by default: .safetensors checkpoints, .jsonl
  traces, raw .log files, data/**/checkpoints, .pause-* files

/home/steve/qwen36-results-main
  tracked dirty entries: 0
  visible untracked status entries: 950
  visible untracked payload: ~0.307 GiB
  root split: data/: 950
```

Largest active-repo heavyweight artifacts before ignore were ten Qwen EAGLE
training checkpoints under
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
