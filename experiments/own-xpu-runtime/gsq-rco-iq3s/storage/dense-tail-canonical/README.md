# Sixteen closed raw bundles with existing canonical copies

Metadata-only preparation identifies 1,773,945,344 bytes: six dense-Q6 initial/warmup bundles, four failed class-A initial/warmup bundles, and six successful class-B bundles. The exact raw roots and capture names are fixed in `reuse.py` and `closure-binding.json`. No drafts, JSON, indexes, seals, logs, or unindexed files are released.

Failed class-A remains failed. Its incident review proves cooperative owner closure and sealed metadata, not a successful measured request or a prior payload audit. Verification must read the complete held raw file and canonical compressed archive, verify the canonical member, and durably preserve its restore map before a separate release invocation rechecks both hashes and inode identities.

The frozen prompt01 helper supplies verification, hashing, durable restoration metadata and separate release unchanged. Only closed-authority joins, the exact multi-root allowlist and raw-path resolution change. The generic canonical helper remains hash pinned. `metadata_smoke.py` checks all sixteen actual metadata joins while refusing payload-opening calls; it performs no archive or release operation.

**Operational hold:** root must retain class-B raw bundles until the new dense-packed-block fixtures are extracted and authenticated. Root alone may invoke `evidence/root-execution.py --run --review-sha256 <review> --class-b-fixtures-preserved` after confirming that condition. The switch is an explicit operator attestation, not evidence that extraction occurred. Each verify/release phase uses exclusive logs and durable receipts; any failure stops the sequence without retry. Individual helper phases remain root-only and subject to the same hold.

The capacity appraisal projects only about 90 MB above the next full-suite admission threshold using its sampled free-space value. Recheck actual free space; this source checkpoint is not admission. All byte recovery remains conditional on actual full readback and separate release.
