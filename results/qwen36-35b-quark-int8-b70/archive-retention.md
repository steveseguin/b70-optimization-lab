# Qwen 3.6 35B Archive Retention Plan

Date: 2026-07-02

Purpose: keep Qwen 3.6 lessons available for future work without carrying stale
branches, detached worktrees, or multi-GB model/checkpoint artifacts in normal
`main` history.

## Policy

Use `/home/steve/llm-optimizations` on `main` as the active workspace. Preserve
Qwen knowledge in compact tracked artifacts:

- result summaries and promoted ledgers under `results/qwen36-35b-quark-int8-b70/`;
- chronological notes under `notes/`;
- reusable scripts under `scripts/`;
- patch snapshots under `patches/`;
- repro recipes under `repro/` and `configs/`.

Do **not** commit or push raw model/checkpoint/tensor artifacts, large JSONL
traces, or raw server logs unless a future task explicitly promotes a small
artifact as evidence. The repo `.gitignore` already excludes the relevant heavy
classes: `*.safetensors`, `*.gguf`, `*.pt`, `*.pth`, `*.ckpt`, checkpoints,
`data/**/*.log`, `data/**/*.jsonl`, and historical `data/qwen36-*` raw backlog
paths.

## Current Tracked Qwen Pointers In `main`

Primary orientation files:

- `docs/qwen36-research-map.md`
- `docs/current-reproducibility-map.md`
- `docs/vllm-intel-upstream-candidates.md`
- `docs/feedback-for-intel.md`
- `results/qwen36-35b-quark-int8-b70/README.md`
- `results/qwen36-35b-quark-int8-b70/2x-b70-reference.md`
- `results/qwen36-35b-quark-int8-b70/4x-b70-results.md`
- `results/qwen36-35b-quark-int8-b70/reproduce.md`
- `results/qwen36-35b-quark-int8-b70/validity-gates.md`
- `results/qwen36-35b-quark-int8-b70/bugs-failed-paths.md`
- `results/qwen36-35b-quark-int8-b70/intel-vllm-suggestions.md`
- `results/qwen36-35b-quark-int8-b70/next-model-carryover.md`

Tracked Qwen notes and patches are intentionally numerous; use:

```bash
git ls-files 'notes/*qwen*' 'patches/*qwen36*' 'scripts/*qwen36*'
```

for the exact live inventory.

## Local Artifact-Heavy Branch Audit

A stale local branch `local/qwen36-artifact-heavy-20260628204326` was converted
to local annotated tag `archive/qwen36-artifact-heavy-20260628204326` during
cleanup, then audited. The tag points at history containing large binary
artifacts and should **not** be pushed.

Tree summary for that local tag:

```text
files: 48,351
total bytes: 6,329,196,612
largest directories:
  data/:        6,306,012,146 bytes
  patches/:        13,240,232 bytes
  notes/:           4,139,196 bytes
  scripts/:         1,925,273 bytes
  docs/:            1,634,234 bytes

largest extensions:
  .safetensors: 5,331,481,680 bytes
  .pt:            502,076,462 bytes
  .jsonl:         248,985,616 bytes
  .json:          123,673,868 bytes
  .log:            96,403,456 bytes
  .patch:          11,248,328 bytes
  .md:              8,293,430 bytes
```

The large blobs are mostly Qwen EAGLE draft checkpoints and traces, for example:

```text
224,418,608 data/qwen36-eagle3-rollout5-*/model.safetensors
155,203,432 data/qwen36-eagle2-*/model.safetensors
 85,988,264 data/qwen36-eagle1-*/model.safetensors
 32,385,384 data/qwen36-k2-nopreempt-trace-20260617e-server.log
 16,747,703 data/qwen36-quark-int8-tp4-routecapture4-routes-20260611.jsonl
```

These artifacts are useful only as raw audit/checkpoint material. They are not
required for the main Qwen lessons, and pushing them would make the repo heavy
and awkward for future Gemma/Qwen work.

## Detached Worktree Backlog

`/home/steve/qwen36-results-main` was a detached audit worktree at
`4b33bb2f`. It had no tracked dirty files, but it still had a local untracked
`data/` backlog:

```text
visible untracked files: 2920
all under: data/
tracked in active main: 0/2920
```

The backlog was archived locally and the linked worktree was removed on
2026-07-02 so normal work has a single active checkout:

```text
archive: /home/steve/qwen36-raw-archives/qwen36-results-main-detached-4b33bb2f-20260702.tar.zst
compressed size: 187M
uncompressed payload verified by zstd -t: 1,600,215,040 bytes
sha256: 0a474341b4360209559938c8fbeee84d86e1f9be28f16aa0b7dcb22fd6523517
```

Do not run new work from restored copies of that archive. If a future Qwen task
needs a raw packet, extract the archive into a temporary non-worktree location,
promote a compact summary or selected small evidence file into `main`, then
delete the extraction.

If disk pressure or final cleanup is needed, first either:

1. promote named result packets into `main` as compact summaries; or
2. explicitly discard the raw archive after confirming no future Qwen work needs
   those packets.

## Recommended Cleanup State

For day-to-day work:

- keep only local branch `main`;
- keep `origin/main` as the normal remote target;
- leave remote `origin/codex/*-achieved` refs as historical remote archives;
- do not keep local archive tags that point at multi-GB artifact history;
- keep raw Qwen checkpoints/traces out of Git and rely on this manifest plus the
  tracked Qwen notes/results/patches for future restart context.

## Future Qwen Restart Checklist

When returning to Qwen 3.6:

1. Start from `docs/qwen36-research-map.md` and this folder.
2. Re-read `results/qwen36-35b-quark-int8-b70/bugs-failed-paths.md` before
   repeating graph/speculative work.
3. Reproduce only from documented configs and scripts, not from stale detached
   worktrees.
4. If a raw local artifact is needed, locate it from the detached backlog first;
   promote a compact summary afterward rather than committing the raw file.
5. Keep headline results under the fresh-response validation policy: no warmed
   repeats, no cache/history acceleration, and full run identity recorded.
