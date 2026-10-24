# Retained arithmetic bytes and failed attempts

The final attempt's `stdout.json` and promoted `evidence/arithmetic-proof.json`
are each about 1.77 MB. They retain complete BF16 output and status/error bytes
for all seventeen cases, plus selected/scalar/candidate hashes and actual decode
counts. The authority tests and independent review reconstruct and compare
these bytes; summary hashes alone would not support that independent review.

Keep the original attempt output and its byte-identical promoted copy. The build
receipt binds the original stream; the final authority and documentation bind
the promoted proof. Both are tracked and can be restored from this packet's Git
commit without rerunning arithmetic. They are synthetic test data, not model
weights or user conversation content.

Both failed source snapshots, logs and receipts remain under their original
attempt directories. The diagnostic failure preserves the differing NaN bits
and positive CPU owner teardown. Original failed executables and dependency
files are locally retained under ignored build paths recorded in
`evidence/first-failure-retention.json`; their source/build provenance is tracked.
Do not silently replace failures with the passing attempt or reinterpret safe
cleanup as successful arithmetic.
