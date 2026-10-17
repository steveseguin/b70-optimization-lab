# Packet64 retention

The owned build and all selection files total about 352 MB when hardlinks are
counted once. `cpu-validation.json` records the exact count and enforces the
400 MB preparation limit. Storage admission separately reserves future chain
outputs and preserves the 8 GB root free floor. This is a local lab packet,
not a published deployment recipe.

Native sources, compiler commands, object identity, CPU gate receipts, small
byte fixtures, all eight selection seals and wrapper seals are tracked.
`build/` and each selection's `build/` are ignored. Model weights, compiler
objects and full executable images remain local. `build-device-receipt.json`
binds their hashes. `engine-commands.json` gives the exact commands; inherited
objects are hardlinked only after checking the packet61x source/build receipt.
Only the main entry and selection dispatch objects were recompiled, in both
host and device modes. The CPU production-width draft fixture was also built.

`build_engine.py`, `prepare_selections.py`, `cpu_gate.py`, `seal_packet.py`,
`prepare_chain.py`, `record_validation.py` and `fast_reseal.py` retain the
preparation sequence. Build and selection creation are fresh-only and refuse
to overwrite sealed evidence. For lost build artifacts, replay the recorded
compiler commands into fresh scratch, verify the original receipt hashes, then
restore only the missing files; do not regenerate or silently replace a seal.
A different compiler/library output requires a new packet. The parent fixture
binaries are read-only symlinks. `prepare_chain.py` restores their links and
hardlinks all 74 input fixture files after verifying their bound hashes.

The eight views hardlink the device executable and exact CPU fixture bytes.
`evidence/object-identity.json` records inherited object source paths and hashes.
`flat_fixture.cpp` preserves the exact CPU copy-tile test source;
`evidence/flat-build-commands.json` records its build. It checks 975 descriptors,
unaligned tails and sentinel gaps over 11,899,255 bytes.

The two prior placement allocation censuses are retained losslessly as
`evidence/batch-memory-*-census.json.gz`. `memory-admission.json` records original
paths, raw and archive hashes, and the conservative descriptor bound. They are
historical read-only memory evidence, not packet64 device results.

Large input-check reports are gzip archives with exact raw-byte hashes in
`evidence/input-checks.json`. They enumerate every path, its role, producer,
size and bound hash where applicable. The checker stats model shards without
reading their payloads. Their plain summaries and chain command plans remain
JSON. Older CPU-preparation chain seals are kept under
`evidence/prior-chain-seal-*.json`; later explicit resumes retain the old seal
and every original early receipt. No historical evidence was removed.
