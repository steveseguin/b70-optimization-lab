# Packet69 retention

The two 4 MiB `rope.bf16` files are byte-identical copies of packet64's frozen
arithmetic table. They are required by the local source/build identity and
retained explicitly; Git stores identical blobs once. Restore from the pinned
parent path and verify the SHA256 in each build receipt. No new weight file
was copied or downloaded. Source copies preserve the frozen parent trees.

Local `build/` directories contain generated mirrors, compiler logs, small
operator test executables, incremental entry/selection/head objects and linked
runtime binaries. Inherited large objects are hardlinks, not new copies.
`build_engine.py`, `engine-commands.json`, `parent-source-manifest.json` and
`build-device-receipt.json` retain the source, object and executable hashes.
Rebuild serially with the recorded toolchain and nice19/affinity/8 GiB ceiling;
never modify or delete the parent object paths. All own builds together stay
below 1 GB. Device execution is not part of rebuilding.

Small byte fixtures are tracked, including the equal expected/actual bytes
referenced by each selection seal. Raw future device runs and caches under
`screen/*/evidence/` stay local; promote only focused receipts/reports without
removing the raw evidence. The old packet64 attribution remains untouched.
