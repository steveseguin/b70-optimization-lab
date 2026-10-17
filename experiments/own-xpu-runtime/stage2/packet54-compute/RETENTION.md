# Packet54 retention

Source, preregistration, tests, source/build/gate receipts and compact CPU logs
are tracked. Build and device evidence are ignored. The build has a strict
500000000-byte cap, including planned compiler scratch; cleanup removes only
new regenerable objects after gates. Existing packet45 objects and all other
packets are read-only. No source tree, model file or protected result is deleted.

Final binaries, mirrored sources and build logs remain locally for sealed
windows. CPU-BUILD.md restores removed compiler objects. Device windows allow
64 MiB of evidence each above the inherited8 GB floor; preparation maintains
18 GB free and spends no protected chain reserve. Raw timing streams, faults,
failed gates and partial windows are evidence, not disposable scratch.

The admitted controls inherit packet45's source-checked object/relink proof.
control-identity.json additionally pins the packet49c production control bodies,
SPEED6 map and exact p53b bank receipt. Fresh device equality is still required.

The compiler diagnostic byte dumps are retained as lossless `.bin.gz` files
in `evidence-cpu/`; `diagnostic-retention.json` records original and compressed
hashes. Each was decompressed and compared byte for byte before removing the
original scratch `.bin`. `cross-compiler-byte-range-proof.json` maps every
observed difference to the exceptional fixtures. The rejected HC/FFN helper
test source remains in `rejected_hc_ffn_test.hpp`.
