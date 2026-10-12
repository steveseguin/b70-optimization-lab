# Retained large artifacts

`rope.bf16` is a 4,194,304-byte arithmetic constant. It is required to rebuild
the runtime and preserves the old table byte for byte at its prefix.
`generate_rope.py` reproduces it; `rope-receipt.json` records its identity and
prefix comparison. It is not a generated cache to discard.

The capacity CPU ledger and its compressed case archives retain source,
binary, oracle, token, layer and cleanup identities. Repeated identity maps
make the aggregate ledger large, but let each case stand on its own and prevent
a stale partial pass from qualifying a changed runtime. `CPU-REPRO.md` rebuilds
these receipts. Raw fixture scratch is deleted only after hashes and the gate
receipt are written; compression preserves the retained log bytes.

Ignored build output is not part of the Git packet. Coordinator binaries,
compile/link provenance, the checked source mirror, fusion fixtures, input
bundle and GNU draft references are needed for the prepared windows. Regenerable
objects and disposable CPU fixture directories are removed. The local build
ceiling during preparation is 4 GB; every large-write admission reserves an
8 GB root free-space floor.

`evidence/draft-baseline-rows.jsonl.gz` preserves the full original bytes of
63 frozen packet38 draft fixtures. These are the independent baseline for all
six new draft arms. `draft-baseline-oracle.json` retains their full and valid
prefix hashes and compressed original source receipts. `draft_baseline.py`
verifies every archived member; each JSONL member's `data_b64` restores the
original file bytes. Keeping the original tails makes cropping auditable.
