# Disk cleanup, 2026-10-18 (root 14 GB free before the packet 84 record chain, which needs 14.32 GB)

## Packet 45 closed GPU window trees → RAID archive (01:11–01:13 UTC)

- Moved: `packet45-merged3/build/{speed3-c4096-dr1-gpu, speed3-c4096-dr0-s24-gpu, speed6-c4096-dr1-s23-cards01-gpu, speed6-c4096-dr1-s23-cards23-gpu, speed7-c4096-dr1-s23-cards01-gpu, speed7-c4096-dr1-s23-cards23-gpu, k2probe-c4096-dr1-s23-cards01-gpu}` (exact directories, no globs).
- Archive: `/mnt/raid-models/own-xpu-runtime-archive/packet45-merged3/window-trees-20261018T011112Z.tar.gz` (3.0 GB), with its sha256 and a per-file SHA manifest `window-trees-20261018T011112Z.sha256` (261,242 files, hard links included).
- Verified before deletion: member count equals the manifest; every member's content hash was recomputed from the archive and matched.
- Kept on root (referenced by packet 78 seals): `speed6-c4096-dr1-s23-cards01-gpu/K2/run0/dispatch-measured.json` (hash re-checked after restore). `fusion-rope.hpp` and `fusion-fixtures` were not touched.
- Root free: 14 GB → 20 GB.
- The first attempt stopped at its member-count check (it did not count hard-link entries); nothing was deleted, and its partial archive files were removed.
