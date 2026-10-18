# Packet76 artifacts

Keep all source copies, seals, byte fixtures, input hashes, plans and negative
decisions. No old packet, receipt, shared wrapper or live queue was modified.
The raw packet69/64/70 receipts remain at the paths and hashes in
`ATTRIBUTION.json`; they are read-only research inputs, not copied model files.

`rope.bf16` is a 4,194,304-byte copy of packet70's exact model RoPE constant.
It is required by Engine initialization and its original hash check, including
the full-shape dry run. Its source hash is in `parent-source-manifest.json` and
the build closure. Retain it as a required source constant; restore from
packet70's identical `rope.bf16` and verify SHA256 before use. It is not a cache
or new model download.

Generated `build/` trees, inherited-object hardlinks and native executables are
ignored, including selection-local hardlinks. The local build is 138,872,656
logical bytes (below 1 GB). Its exact binary hashes and compile/link commands
are in `build-device-receipt.json` and `engine-commands.json`; the unchanged
objects have their packet65 source paths and hashes in
`evidence/object-identity.json`. Packet70 explicitly reuses packet65's build.
Do not silently substitute a compiler, object, source tree or binary on restore.

The GNU/Intel mock byte fixtures are retained under each selection's `fixture/`.
The generated full-shape test translations, all eight censuses/results/teardowns,
and build/test logs are byte-verified gzip snapshots under
`evidence/retained-build/`, mapped by `evidence/build-retention.json`. Restore
each member with gzip decompression to its listed original path and check its
uncompressed SHA256. Original local files were not deleted. Four paired
production/candidate censuses are byte-identical; see
`evidence/allocation-identity.json`.

To reconstruct a missing build, first preserve the old receipts and seals, and
verify the exact parent source/object manifests. `build_engine.py` expects a
fresh local build receipt; it creates the checked include mirror and rebuilds
only main, the selector, retirement and the SYCL owner. `cpu_gate.py`,
`fullshape_gate.py` and `python_gate.py` recreate the CPU gates. Keep existing
seals immutable; compare rebuilt binary/source hashes to them and stop if any
differs. `seal.py` creates new selection views only when none exists. No GPU
is needed for these operations. Preparation uses nice19, cores 8–15/24–31,
python3 -B, stdin /dev/null and an 8 GiB address-space cap; compiles are serial.

The filesystem already had about 27 GiB available at entry. This task added
only the bounded packet, used hardlinks for inherited objects and made no
cleanup, cache, memory or storage-setting changes. Device screen admission
still checks its own current storage floor before launch.
