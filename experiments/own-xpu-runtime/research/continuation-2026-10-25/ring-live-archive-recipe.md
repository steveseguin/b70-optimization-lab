# Ring-live evidence archive support

These commands accept a PASSED `ownrt.ring-live-proof.v1`; the
[actual recursive proof](ring-live-depth2-proof/RESULT.md) has now been archived
and restore-tested using them. Keep the run,
proof, complete archive and restoration directory; no helper deletes originals.

Create a complete archive in tmpfs after the proof passes:

```bash
python3 archive_ring_live_proof.py full \
  --run RUN --proof PROOF \
  --archive /dev/shm/sc117-ring-live-complete.tar.gz \
  --receipt FULL_RECEIPT.json
```

Then optionally create a compact packet using the already durable portable-live
archive. This authenticates the durable archive and checks every referenced raw
member, seal, index and state JSON. Any mismatch is embedded as new raw data.
Omitting `--source-durable-receipt` embeds every payload.

```bash
python3 archive_ring_live_proof.py reuse \
  --full-receipt FULL_RECEIPT.json \
  --source-durable-receipt portable-live-durable-archive.json \
  --archive /dev/shm/sc117-ring-live-compact.tar.gz \
  --receipt COMPACT_RECEIPT.json \
  --restore-check /dev/shm/sc117-ring-live-restore-check
```

The compact receipt records exact sizes and hashes, the full mapping, embedded
and reused byte counts, and a strict sealed-reader check of every independently
restored bundle. A later durable copy needs its own copy-and-rehash receipt;
creating a tmpfs archive does not establish durable retention.

The distinct pending-target survival proof uses
`archive_pending_provider_proof.py --run RUN --proof PROOF --archive ARCHIVE --receipt RECEIPT`
for its full archive. It requires the explicit v5 proof, both newer-provider
survival checks and the complete target/draft comparison. The same `reuse`
command and restoration reader then preserve all its raw bytes. The old
quiescent full-archive gate remains unchanged.

Restore from the compact packet using its independently retained digest:

```bash
python3 restore_ring_live_archive.py \
  --archive COMPACT_ARCHIVE --sha256 EXTERNALLY_TRUSTED_SHA256 \
  --source-archive DURABLE_PORTABLE_LIVE_ARCHIVE \
  --out FRESH_RESTORATION_DIRECTORY
```

The new mixed format is `ownrt.ring-live-reuse-archive.v1`; existing target-only
archive and restoration semantics are unchanged. It preserves all discovered
raw bundles, including the extra `draft-final-state-sealed` written at FINISH.
Only the proof-listed DUMP target/draft bundles are labeled qualified. Repeated
reuse creates separate single-link files rather than hardlinks.

CPU coverage: six new tests exercise exact mixed reuse, new-data fallback,
metadata-only differences, missing/unlisted/duplicate raw payloads, corrupt
source identity, path traversal, and refusal of failed or older proof schemas.
The five existing target-only restoration tests also pass unchanged.
