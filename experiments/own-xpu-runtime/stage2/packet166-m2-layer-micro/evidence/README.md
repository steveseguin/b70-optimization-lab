# Evidence status

Current qualification is `build.json`, `cpu-real-parity.json`,
`preparation.json`, `entry-plan.json`, `rehearsal.json`, the corresponding raw
outputs, `parent-device-replay.json` and `analyzer-tests.log`.

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

The shared report gate remains failed because its fixtures are packet162
matrix events, not packet166 layer events. `rehearsal-attempt1/` also records
fixed packaging issues: lineage metadata was initially mistaken for active
cross-packet pins, and the help probe needed an explicit output marker.

Synthetic report receipts exist only in temporary test directories. Their
serialized byte size is retained to justify the 32 MiB planned write allowance
(less than three times the measured fixture stream size). They are never
native timing evidence. No layer speed, prefill rate or verifier-cost result
has been measured by this preparation.
