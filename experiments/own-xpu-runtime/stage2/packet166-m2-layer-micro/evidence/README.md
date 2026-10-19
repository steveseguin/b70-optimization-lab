# Evidence status

Current qualification is `build.json`, `cpu-real-parity.json`,
`preparation.json`, `private-rehearsal.json`, `private-report.json`, their raw
outputs, `parent-device-replay.json` and `analyzer-tests-166b.log`.

The successful real CPU receipt points to two identical 414-buffer traces and
`real-oracle.tsv`. It binds the current GNU/Intel binary hashes. All three current
native builds bind their C++/header closure. No GPU kernel was executed here;
`micro-device` ran only `--help` and the Landlock-confined CPU transport.

The initial `gnu-synthetic*.jsonl` files and the earlier synthetic CPU receipt
are developmental checks. They predate the final scheduler/sensor changes and
are not current readiness evidence. Failed build logs and earlier rehearsal
attempts are retained. `cpu-real-1792396078967435483` has a GNU pass followed by a
conservative Intel refusal when the CPU preparation process appeared as
`micro-device`; it is superseded by the successful real CPU receipt.

The historical shared report gate remains failed because its fixtures are packet162
matrix events, not packet166 layer events. Its original `rehearsal.json` and
`shared-rehearsal.*` bytes are preserved. The private adapter replaces only that
report requirement and records the limitation in READY. `rehearsal-attempt1/` also records
fixed packaging issues: lineage metadata was initially mistaken for active
cross-packet pins, and the help probe needed an explicit output marker.

Synthetic streams exist only in temporary test directories. Compact analysis,
briefs and negative-index tails are retained in `private-report-cases/`, explicitly
as synthetic adapter tests. Their serialized byte size is retained to justify the 32 MiB planned write allowance
(less than three times the measured fixture stream size). They are never
native timing evidence. No layer speed, prefill rate or verifier-cost result
has been measured by this preparation.

Packet166b retained all three unchanged native builds and rechecked both original
414-buffer real CPU traces against their binary/source hashes. The fresh preparation
receipt covers the current proposal, all help flags and 2,412 real arm/reset steps.
`private-rehearsal.json` binds a temporary lanequeue plan, the real entry plan and
the private adapter. `private-report.json` binds the analyzer, real report entry,
fixture generator, real CPU traces, real parent stream, source-note snapshots and
all synthetic report tails. READY is written only after this complete closure
passes the real pin guard. Its final execution gate is then checked without
launching or accessing a device.
