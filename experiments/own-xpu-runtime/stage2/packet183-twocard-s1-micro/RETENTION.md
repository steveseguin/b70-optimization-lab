# Packet183 retention

The vendored source closure (`native-base/`, `lineage-inputs/vendor/`) and private packet136/150/153
lineage inputs make this packet independent of mutable sibling trees, as in packet153. Parent ELF
objects (packet136's build, resolved into packet103's) and the packet49 oracle are the only shared
immutable runtime inputs; both are hash-pinned (`immutable-binaries.json`, `oracle-binding.json`).

`lineage-inputs/packet153-own/` holds packet153's own README, closeout, DO-NOT-REPEAT, retention,
readiness marker, proposals and `v5/evidence/` byte for byte. They certify packet153, not this
packet. Its `device-static-v5-B-p153b/bracket-summary.json` is the real two-card device evidence
the S1 decision rule is tested on (`v5/test_s1_decision.py`).

All generated `v5/build/` files (engine binaries, S1 byte/census/full-shape fixtures) stay local
and ignored; rebuild through `v5/qualify_cpu.py` (about 5 min end to end, the real-weight census
reads 3.33 GB of Q6_K payload once). Full-shape run directories are retained as hashed archives
`v5/evidence/shape-*.tar.gz` (8 files, 4 MB, all original bytes verified before the scratch was
dropped); superseded archives from earlier iterations were removed before sealing. Device output
directories named in the proposal (`v5/evidence/device-metadata-*-p183`) must stay fresh.
