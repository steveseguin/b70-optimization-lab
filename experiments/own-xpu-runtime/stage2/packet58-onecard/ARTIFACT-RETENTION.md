# Packet58 artifact retention

`rope.bf16` is the unchanged 4,194,304-byte deterministic RoPE table used by
packet56. SHA-256: `92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
It is retained beside the new runtime because the native loader resolves this
exact table relative to its source packet. Restore it from packet56/rope.bf16
only after verifying that digest. It is runtime input, not generated cache or
model weights; changing it would change the oracle identity.

The copied C++ sources form a separate packet. `base-source-manifest.json`
records parent file hashes. Historical parent Python helpers were excluded
when unused; they remain in their original packet and Git history. No parent
file or unique evidence was deleted.

`build/` is regenerable CPU compilation scratch and is excluded from Git.
Keep it below 1.5 decimal GB. Only packet58's own scratch may be removed.
Build receipts record binary and source identities; `build.py` reconstructs
host/device binaries with the installed compiler. Existing read-only packet56
fixture inputs are dependencies for inherited compilation mirrors. This is
an originating-host experiment, not a newly certified public recipe.

Compact CPU receipts, negative test findings and review notes are retained.
Full device outputs are produced only by coordinator windows. Do not delete
failed windows, fault records or raw suite timings during cleanup.
