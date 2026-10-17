# Retention

Keep copied sources, source manifests, byte/timing accounting, compiler reports,
compressed assembly, CPU fixtures and seals. Build outputs are reproducible
local artifacts, not public release assets. The build is about121 MiB; three
view binaries and fixture files use hardlinks. No allocation over8 GiB or
model payload read is part of preparation.

The initial-wide source and offline reports are historical negative evidence:
13 static loads versus9 production, corrected to7 before screening. Its old
build receipt is an archival identity, not an active passing seal against the
current source tree. Assembly paths in its original report are relocated from
`evidence/registers/` to `evidence/initial-wide/registers/`; their bytes and
SHA256 remain unchanged. The initial offline build remains in
`build/offline-initial/`. Do not use its stale source hashes to qualify a run.
