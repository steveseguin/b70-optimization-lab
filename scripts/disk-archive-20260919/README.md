# Disk archive scripts (first run 2026-09-19)

The four runners that moved everything off the two-B70 host's fast disk on 2026-09-19, after
[`scripts/disk-cleanup-20260919.sh`](../disk-cleanup-20260919.sh) had removed the caches, build trees and
research images. They are kept here because the moves are the part that is worth repeating: the cleanup
script deletes, these four *relocate*, and the difference is the verify-then-remove discipline below.

Full account of that session: [`notes/2026-09-19-disk-review.md`](../../notes/2026-09-19-disk-review.md).

## The four runners

| Script | What it did on 2026-09-19 |
| --- | --- |
| `move-to-cold-storage.sh` | 17 model directories -- 12 from `/mnt/fast-ai/llm-models`, 5 from `/home/steve/llm-models` -- to the external SSD. Everything not on its two lists stayed: the Qwen3.8-27B FP8 lane, the INT4 lane and MiniMax-H3. All 17 verified; 13:06-13:15. |
| `archive-bench-results.sh` | Selected 1,250 campaign output dirs in `/mnt/fast-ai/bench-results` older than 2026-09-14 that no script references, then archived 902 of them. The other 348 failed because a user-level `rsync` cannot read container-written state; it writes their names to the failure list for the next script. |
| `archive-bench-results-sudo.sh` | The 348 leftovers, 78 GB, copied/verified/removed as root. Same destination. 0 mismatches. `/mnt/fast-ai` 412 -> 503 GB free. |
| `move-src.sh` | `/mnt/fast-ai/src` (26 llama.cpp worktrees, 14 GB of sources once tier 2 had removed the 168 build trees inside them). |

Each one takes its date and destination from environment variables at the top of the file, so a later session
is `DATE=20261101 ./move-to-cold-storage.sh` rather than a copy-edit. The model lists and the cutoff date are
plain arrays/variables in the same block; edit them, do not fork the script.

```bash
cd scripts/disk-archive-20260919
DATE=20261101 ./move-to-cold-storage.sh
DATE=20261101 CUTOFF=2026-10-25 ./archive-bench-results.sh --build-list   # review the list it prints
DATE=20261101 CUTOFF=2026-10-25 ./archive-bench-results.sh
DATE=20261101 CUTOFF=2026-10-25 ./archive-bench-results-sudo.sh
DATE=20261101 ./move-src.sh
```

Run them under `systemd-run --user` (that is how the 2026-09-19 units `move-cold-storage-20260919`,
`archive-bench-results-20260919`, `archive-bench-sudo-20260919` and `move-src-20260919` ran): a long rsync
outlives an agent session, and the harness kills child processes. `WAIT_UNIT=<unit>` makes a script wait for
an earlier unit to finish, because all of these write to the same USB disk and running them in parallel only
makes both slower.

## Verify, then remove

No script here removes a source on the strength of the copy command's exit code. Every directory goes through
the same three steps:

1. `rsync -a --no-inc-recursive src/ dest/` -- the copy.
2. `rsync -a -n -i src/ dest/ | grep -c '^>f'` -- a dry-run second pass. Zero files left to transfer means
   every file matched on size and mtime. This is the verification, and it costs a metadata walk.
3. Only on a zero count, remove the source.

A non-zero count logs `VERIFY MISMATCH (n)` and **keeps** the source; the run continues with the next
directory. A removal that fails leaves the copy in place and logs `REMOVE FAILED` -- nothing is ever reported
as archived because a command was issued.

## Root-owned state: why there are two archive passes

Torch-compile caches and state directories inside a campaign are written by the serving container, so they
belong to root. A user-level `rsync` reads past them and a user-level `rm -rf` prints `Permission denied` per
file without a non-zero exit for the run as a whole -- the copy is silently partial and the delete silently
does nothing. That is exactly what happened to tier 1 of the cleanup script earlier the same day: 744,805
permission-denied lines, and a summary that still claimed the space.

So: the first archive pass runs as the user and records every directory it could not finish in
`archive-failed-<DATE>.txt`; the second pass redoes those as root. The model and `src` movers, which touch far
fewer root-owned trees, fall back to `sudo` for the removal step alone. The sudo password comes from
`SUDO_PW` (default `/home/steve/SUDO_PASSWORD.txt`, the lab convention) via `sudo -S -p ''` with the file on
stdin; it is never echoed, logged or passed on a command line.

See [`experiments/qwen38-27b-b70/DO-NOT-REPEAT.md`](../../experiments/qwen38-27b-b70/DO-NOT-REPEAT.md),
"user-level rm/rsync over container-written state dirs".

## Cold-storage layout

```
/media/steve/extended-ssd/model-cold-storage/
└── b70-host-<DATE>/                        # one directory per host per session
    ├── llm-models-fast-ai/                 # from /mnt/fast-ai/llm-models
    ├── llm-models-root/                    # from /home/steve/llm-models
    ├── bench-results-pre-<CUTOFF>/         # campaign outputs, original directory names
    └── src-llama-cpp-worktrees/            # the worktree sources
```

The source disk is in the path, so a model that came off the root disk and one of the same name from the fast
disk cannot collide, and moving a directory back is a plain `rsync` in the other direction. Directory names
are never rewritten: a campaign dir keeps the name the scripts and notes refer to.

## The reference list

`archive-bench-results.sh --build-list` decides what is stale in two steps and subtracts:

* **candidates** -- `find bench-results -maxdepth 1 -type d ! -newermt $CUTOFF`, by mtime.
* **referenced** -- every `bench-results/<name>` path that appears anywhere under `experiments/*/scripts`,
  `packages/*/scripts` and `scripts/`, grepped out of the runners themselves.
* **archive** = `comm -23 candidates referenced`.

Two categories are never archived even when they are old and unreferenced: `gpu-fault*` and `host-oom*`
incident evidence, hard-coded as `KEEP_GLOBS`. On 2026-09-19 the subtraction protected 10 directories that
runners still name (`gemma4-26b-a4b-q8`, the two `qwen35-{4b,9b}-w4a16-20260913-rt2`, the `qwen38-fp8`
r147/r156f/r165 sets, `r304-real-content-depth-20260913b`, `rebase-v0290-rb1`, the INT4 r304 rebase and the
r307 qualification).

Always `--build-list` first and read what it printed. The list is the only thing standing between a stale
campaign and a referenced one, and a runner that names its state dir through a variable will not appear in
the grep -- check anything you are unsure of by hand before the move runs.
