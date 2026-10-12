# Packet29 preparation evidence retention

`preparation-logs-p29.json.gz` is retained despite exceeding 1 MiB because it is
the byte-verified record of 2,465 CPU preparation text artifacts: compiler logs,
argument-validation traces, integration/sanitizer and fixture receipts, CPU
model timing/ownership logs and failed diagnostic logs. `scratch-cleanup.json`
binds its compressed and uncompressed SHA-256 hashes and records the removed
scratch directories. It supports review of the newly sealed gates and the
nonfinite limitation. It contains no downloaded model checkpoint or native
benchmark result. Consumers are the packet29 gate receipts and closeout.

Restore a member by decompressing the gzip file, parsing the JSON array,
locating its `path`, decoding its `base64` bytes and verifying its `sha256` and
`bytes` before writing under this packet's `build/`. Each member was verified
this way before disposable scratch was deleted. Preserve the archive while
this packet remains an evidence or reproduction dependency; no timed deletion
is authorized. The original packet27 archive is an inherited provenance record.

The small initial diagnostic executables/logs in
`expert-down-nonfinite-initial/` preserve the failed exceptional-value evidence;
their hashes and extents are listed in that directory's manifest.
