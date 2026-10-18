# Retention and rebuild

Retain copied sources, parent hashes, commands, CPU byte-comparison receipts,
full-shape allocation/operation receipts, compressed offline assembly and
selection seals. Build products and hardlinked view binaries stay ignored.
No old packet or evidence was removed. No model payload or secrets are copied.

The serial incremental build reuses hash-verified packet84 objects listed in
`evidence/object-identity.json`, recompiles entry-main and p49d_submit, and
links GNU-host and Intel-device binaries. The latter is compiled but never run
during CPU preparation. This is an in-lab research screen, not a standalone
public release. Rebuild requires those retained parent objects.

`cpu_gate.py` restores ignored raw NaN snapshots and compact SHA256 transcripts
after comparing every state/output/control byte. `full_shape.py` restores the
payload-free mock entry, allocation census and captured operation lists.
`inspect_registers.py` restores offline BMG-G31 products. These commands are
CPU only, sequential and bounded by 8 GiB. The final check enforces a logical
build-size limit of 1,000,000,000 bytes.

`seal.py` restores the view fixtures and hardlinks; seal only a fresh packet
after evidence hashes pass. Pinned build paths are local evidence identities,
not claims that another machine will reproduce identical binary hashes.

## Large tracked artifact

`rope.bf16` is the unchanged 4,194,304-byte BF16 rotary table required by
the copied engine. SHA256: `92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`. Its bytes already exist
in packet84 (and share the same Git blob); it is retained here to keep the
copy self-contained at runtime. Restore by copying
`../packet84-record-bundle/rope.bf16`, then verify that SHA256 before building.
This is a deterministic runtime constant table, not model weights or a cache.
