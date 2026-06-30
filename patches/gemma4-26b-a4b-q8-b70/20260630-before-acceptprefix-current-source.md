# Gemma 4 26B Q8 Source Snapshot Before Accept-Prefix Work

Date: 2026-06-30

This snapshot preserves the local dirty llama.cpp Gemma record worktree before
starting the next source-level verifier-cost experiment.

Source repo:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926
```

Upstream base:

```text
c926ad098
```

Artifacts:

- `20260630-before-acceptprefix-current-source.patch`
- `20260630-before-acceptprefix-current-source.diffstat`

Why this snapshot exists:

- The current dirty tree is not identical to the previous
  `20260629-vdr2-selected-down-reordervdr2-source.patch` snapshot.
- It contains the promoted Gemma Q8 record stack plus accumulated default-off
  experiment code paths.
- Before attempting the next verifier-cost source lane, this file provides a
  rollback and review anchor for the known working state.

Do not treat this cumulative patch as a clean upstream PR. It is a recovery
artifact for local optimization work.
