# Packet106 retained evidence

The frozen source copy includes `rope.bf16` (4,194,304 bytes). These exact
BF16 constants are required to reproduce the inherited arithmetic; restore
from packet105 commit `339d7017a9dae0e65123a7d89803d54c56600d44` and verify the
copy-lineage hash. This is not a generated cache to discard.

Compressed byte transcripts preserve every compared output byte, with GNU and
Intel process receipts. Full allocation censuses and every-window commands,
results and source identities are compressed under `evidence/` and checked by
their gate receipts. They are CPU proofs, not model performance evidence.

`retain_build.py` retains generated source and small CPU logs/receipts in a
round-trip-verified archive. It records each member's exact size and SHA256.
It never deletes originals. Rebuild objects/executables with `build_engine.py`
and the gate scripts using the recorded compiler commands; binary hashes in
receipts remain identity checks. Local `build/` and per-view binary hardlinks
are ignored by Git. No model weights or raw device benchmark tree is copied.

The final `evidence/generated-cpu-evidence.tar.gz` is 4,001,021 bytes and retains
233 exact generated source/log/receipt members. This exceeds the 1 MiB review
threshold intentionally: source identities in the seals must remain reviewable
and reconstructible after ignored local build scratch is lost. The verified
member map is `evidence/build-retention.json`. Verify the archive SHA256 there,
then restore missing members with `tar --keep-old-files -xzf
evidence/generated-cpu-evidence.tar.gz -C build` and check the listed per-member
hashes. The inherited `restore_links.py` is not a packet106 entrypoint. The file is evidence, not a cache. No duplicate or
large retained evidence was discarded.
