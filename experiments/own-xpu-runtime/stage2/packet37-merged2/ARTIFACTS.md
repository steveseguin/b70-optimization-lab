# Evidence retention

Keep `p33-candidate-gates.json` even though it exceeds 1 MiB. It contains the
per-class, format, reduction-split, tail and exceptional-value outcomes from
four fresh compiler processes. A total alone cannot reconstruct those checks.
Regenerate it with the CPU-only `p33_candidate_gates.py` command in the build
driver; its source, fixture and compiler binary hashes are recorded inside it.

Keep all `evidence/real-*-rank*-arguments.jsonl.gz` files, including members
larger than 1 MiB. They retain the actual reconstructed-versus-prepared argument
blocks for every audited real-model launch, in all four GNU guess modes and both
ranks. Aggregate equality counts cannot show which buffer parity or pointer was
compared. Each corresponding `real-*.json` binds both compressed and raw SHA-256.
Decompress with Python's gzip module, verify the raw hash before using the bytes,
and inspect the JSONL records. Regenerate through the GNU full-model campaign;
never substitute another run's pointer-bearing records or hashes.

`evidence/fixture-gates-full.json.gz` retains the full fresh-owner teardown
sequences summarized by `fixture-gates.json`. That receipt binds compressed and
raw hashes. `evidence/preparation-logs-p37-*.json.gz` archives preparation scratch
as JSON records with original relative paths, lengths, SHA-256 and base64 bytes.
`scratch-cleanup.json` binds that archive. To restore a member, decompress the
JSON, base64-decode its bytes and verify its length/hash before writing into a
new packet-local scratch directory. Cleanup verifies every archived member
before deleting its source. Raw generated mini state is reproducible through
`gates.py` and is not a retained measurement.

The ignored build directory retains compiled binaries, compiler build trees,
checked mirrors and coordinator input manifests/fixtures. The binary seal
records SHA-256; these host-local binaries are not a public release. No model
weights, copied full lookup trees or outside-packet scratch are added to Git.
