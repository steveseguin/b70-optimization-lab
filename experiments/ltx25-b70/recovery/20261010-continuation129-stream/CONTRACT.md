# Packet 129 CPU preparation contract

Parent: sealed 128, manifest
`bd6471f7e10d2ec3219879a281820056178556a3388f50fb7c2c7896199f5ead`.
This is a publication fix, not a numerical or performance qualification.

Every packet-owned HTTP evidence writer finishes a private file in the same
directory, flushes and fsyncs it, publishes with Linux
`renameat2(RENAME_NOREPLACE)`, then fsyncs the directory. Final files are
immutable: a repeated publication refuses instead of replacing the old inode.
This matters because the unchanged `session.read_regular` compares the open
file's device, inode, size, mtime, ctime and link count against the final path.
Neither a hard-link publication nor replacement of an existing final is allowed.
No reader guard, hash, byte gate, tensor, model arithmetic or precision changes.

Receipts, decodes, verdicts, halt records, diagnostics and latches share the
new atomic JSON primitive. Frame/latent/guide anchor bytes use it too. Capture
tensors and summaries publish only after serialization completes. Packet 123's
atomic MP4 and preview JSON path stays intact, including its existing bounded
preview-only read behavior. `/view` rejects private staging names, even through
resolved aliases. Startup identity and fault JSON uses the verified packet helper.
Absent final records return the existing clean 404; an existing final stays
complete while a duplicate writer is refused. I/O failures remain failures;
actual evidence mutation still trips the original strict guard.

There is no append-only manifest consumed by these HTTP routes. Sealed plan,
manifest and reference bytes remain immutable. External model-verification
status is a complete atomic snapshot, with its fresh per-prompt check retained.
See [route inventory](inventory129.md) for producers, readers and scope.

Packet identity changes to 129; client expectations require
`atomic_evidence_publication=true` and pin the inner plan hash. All 128 options,
reference/three-chain qualification, recorded hashes, memory/storage/fault
checks, immutable source closure and default modes remain. Recommended first
arm is 145/serial display3 with idle maintenance, GC60, digest1, background
storage and legacy auxiliaries. No live operation is authorized by CPU preparation.

CPU checks use nice19, OMP/MKL2, pinned bin/python -B with device, signal and
live-socket audit guards. Tests pause actual writers mid-write and invoke real
registered handlers (or AST-extracted upstream handlers) with CPU fixtures.
Native output, memory plateau and two fresh-server speed gates stay with the
coordinator. All author-owned scratch is removed after validation.
