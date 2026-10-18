# Retention

Keep copied sources, source manifests, byte/timing accounting, compiler reports,
compressed assembly, CPU fixtures and seals. Build outputs are reproducible
local artifacts, not public release assets. The final build is about132 MiB; three
view binaries and fixture files use hardlinks. No allocation over8 GiB or
model payload read is part of preparation.

The initial-wide source and offline reports are historical negative evidence:
13 static loads versus9 production, corrected to7 before screening. Its old
build receipt is an archival identity, not an active passing seal against the
current source tree. Assembly paths in its original report are relocated from
`evidence/registers/` to `evidence/initial-wide/registers/`; their bytes and
SHA256 remain unchanged. The initial offline build remains in
`build/offline-initial/`. Do not use its stale source hashes to qualify a run.

The six selection-view executable paths were initially captured in commit
`11debf5eb`. They are now ignored generated files, retained unchanged locally;
removing them from the index does not remove any local bytes. Their exact
historical bytes remain recoverable with `git show 11debf5eb:<repository-path>`
and must match each view's artifact SHA256 before use. The build script also
recreates them from pinned source/object inputs. CPU expected/actual bytes are
tracked explicitly in each selection's `fixture/` directory; the native run
logs and case summaries are retained under `evidence/cpu-runs/`.
