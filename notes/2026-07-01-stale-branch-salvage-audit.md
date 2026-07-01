# Stale Branch Salvage Audit

Date: 2026-07-01

Scope: reviewed old `codex/*` remote branches against current `main` by
content, not just by commit ancestry. Several branches are ahead of `main`
because they were squash/merge-commit merged or because later work continued on
stale branches. Direct branch merges are unsafe: the old branches would delete
thousands of current `main` files and reintroduce stale shared docs.

## Branch Review

| Branch | PR | Status | Decision |
|---|---:|---|---|
| `codex/qwen36-quark-int8-tracking-achieved` | #8, closed unmerged | preserved old Qwen tracking ref; stale shared-file edits | Do not merge. Additive artifacts were salvaged into `main`. |
| `codex/qwen36-quark-int8-tracking-pushable-achieved` | n/a | preserved stale branch with a much larger raw-data dump | Do not merge. Compact summaries were salvaged into `main`. |
| `codex/minimax-json-quality-20260522` | #5 | merged, remote branch deleted | No branch merge needed. The only branch-only addition was a redundant monolithic compressed copy of a harness already represented by tracked part files. |
| `codex/minimax-website-quality-followup` | #4 | merged, remote branch deleted | No missing additive files found. |
| `codex/minimax-rebuild-recovery-20260520` | #3 | merged, remote branch deleted | No missing additive files found. |
| `codex/minimax-89tps-repro` | #2 | merged, remote branch deleted | No missing additive files found. |

## Salvaged Into Main

This audit recovered only files that were absent from `main` and additive:

- compact Qwen data summaries, LocalMaxxing payloads/responses, leaderboard
  snapshots, and summary logs;
- Qwen/B70 notes that preserve transfer lessons and experiment-coverage
  decisions;
- Qwen/vLLM/vLLM-XPU patch snapshots and timing/build notes;
- helper scripts for B70 host-link auditing, vLLM XPU kernel partial builds,
  W8A8/oneDNN parity, endpoint concurrency, D2H token-copy timing, Gemma
  dashboard transfer summaries, and XPU decode timing logs;
- the missing MiniMax structured 94 tok/s repro README.

The first Qwen salvage commit already recovered the larger promoted
script/patch/note set. This pass adds the compact result/evidence layer that
was still stranded on stale branches.

## Intentionally Excluded

These were deliberately not brought into `main`:

- stale shared files from old branches, including `README.md`, `CURRENT.md`,
  `AGENTS.md`, `AGENT_HANDOFF.md`, docs indexes, and promoted-result ledgers;
- destructive diffs that would delete current `main` files;
- the redundant Gemma 26B `repro/gemma4-26b-a4b-q8-b70-current-20260701/`
  record-identity folder, because `main` already has a richer current Gemma
  result packet and repro folder;
- repo-root `identified-mistakes/` copies from the Qwen pushable branch, because
  the canonical files already exist outside the repo at
  `/home/steve/identified-mistakes/`;
- raw Qwen trace dumps and hidden-state/EAGLE corpora. The Qwen tracking branch
  has about 299 MB of branch-only data, and the pushable branch has about
  971 MB across 46k+ branch-only data files. Most of that is raw trace,
  recovery, and hidden-state material. It should be archived separately or
  summarized before GitHub import.

## Cleanup Guidance

After this salvage landed on `main`, the merged MiniMax branches were deleted
from the remote:

- `codex/minimax-json-quality-20260522`
- `codex/minimax-website-quality-followup`
- `codex/minimax-rebuild-recovery-20260520`
- `codex/minimax-89tps-repro`

PR #8 was closed unmerged because its useful additive artifacts were salvaged
and the branch diff remains stale/destructive relative to current `main`.

The two Qwen refs were renamed to end in `-achieved`:

- `codex/qwen36-quark-int8-tracking-achieved`
- `codex/qwen36-quark-int8-tracking-pushable-achieved`

Keep these achieved refs only until the owner confirms that the excluded raw
trace/corpus dumps are no longer needed or have been archived somewhere outside
GitHub. The useful compact artifacts have been recovered, but deleting the
achieved refs would make the large raw dump harder to revisit.
