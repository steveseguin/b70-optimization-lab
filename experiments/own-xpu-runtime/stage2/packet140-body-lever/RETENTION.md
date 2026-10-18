# Packet140 retained analysis inputs

`inputs.json.gz` is about 1.9 MiB, above the repository's 1 MiB review threshold.
Retain it: it freezes the twelve exact WS128 receipts needed to recompute the
class-balanced record and projections, all 164 negative indexes, the mutable
closed ledger, and the small source/timing inputs used for this decision.
Some inputs were already dirty or can change as other work proceeds. A list
of hashes without original bytes would not reproduce that point-in-time audit.
No model weights, secrets, device build, compiler cache or full raw run tree
are included. No originals are removed or replaced.

The archive is deterministic gzip (`mtime=0`) containing JSON. Its `files`
and `receipts` members each store `bytes`, `sha256` and `base64`. The top-level
`archive_sha256` identifies the source packet124c evidence bundle; its receipt
member hashes were verified before copying. `analysis.json:inputs_sha256`
binds this retained archive. `analyze.py --check` verifies every embedded
member and reproduces both generated reports without accessing live inputs.

Restore a selected member to **new scratch**, never over a frozen packet:
gzip-decompress the JSON, select its exact `files` or `receipts` key,
base64-decode it, verify its SHA-256 and byte count, then write those bytes.
`prior_paths` enumerates the negative indexes and `search_output` preserves
the original `rg` matches. The archive plus tracked `analyze.py` suffices to
regenerate `analysis.json` and `prior-search.txt` with the documented CPU
command (omit `--check` to write those two packet140 outputs).

This is evidence retention, not an executable runtime or publication packet.
