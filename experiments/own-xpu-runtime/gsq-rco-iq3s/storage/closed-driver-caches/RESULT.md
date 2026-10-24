# Closed driver caches preserved on USB

All 440 files from older, fully closed per-run driver caches were archived and
verified before their root copies were released. This recovered 271,221,744
bytes on root. The retained USB archive is 50,553,269 bytes, SHA-256
`b980e3ac01a77a8e24a281073bb720a1b6d93e34c7509dbd2ae0c9ae1d892bb7`.
The latest failed F32-A cache, model files, source objects and state evidence
were excluded. No power, memory, GPU or application setting changed.

[Manifest and restoration paths](manifest.json), [full readback](verified.json),
[independent review](verified-independent-review.json), and
[release receipt](released.json) retain the file hashes and closed-owner bindings.
The archive FD remained held through complete member verification and release,
with identity checks and directory fsync. Restore members under
`/home/steve/own-xpu-runtime-results`; bytes and tar metadata are retained,
not original inode or ctime identities. The archive is now protected evidence.
