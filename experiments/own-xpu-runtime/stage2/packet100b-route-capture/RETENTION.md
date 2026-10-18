# Packet100b retention

The build is 66,437,347 logical bytes, below the 300 MB task ceiling. Build
binaries, generated include views, dependency lists and temporary compiler
products stay local under ignored `build/`. Rebuild with the ordered commands
in [README](README.md). They use hash-bound packet97 implementation headers and
objects and packet100's unchanged micro binary. No parent cache was removed.

Tracked source, snapshots, compiler commands, build receipt, CPU test transcripts,
compressed full-shape censuses and seals describe the exact preparation. The
mutable parent selection and orchestration files are not verification inputs.
Existing source changes and state from the concurrent record chain are preserved.

The proposed capture allows at most 50,000,000 bytes under
`evidence/capture-B/`, checked during supervision and after drain. Its four raw
route files total 737,280 bytes. The two prompt input snapshots, startup logs,
output/oracle receipts, rank metadata, and window/drain receipts fit the same
budget. Full model-state dumps are not requested or written. It keeps a 12 GiB
root free-space floor plus that output budget, matching the task's constrained
disk allowance; it does not delete existing evidence to make room.

Future device outputs are ignored until reviewed. Retain all four raw route
files, their metadata, the capture manifest, derived 46,080-byte micro input,
raw micro samples, qualification and lifecycle receipts together. The micro
uses its inherited 64 MiB log allowance and root reserve. Its route sample is
deterministic and independent of timing. No cleanup is authorized by this note.
