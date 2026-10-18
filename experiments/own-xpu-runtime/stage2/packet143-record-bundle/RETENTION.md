# Packet143 retention

Retain the local source/vendor closure, every original symlink, all16 seals, CPU receipts, negative controls, component registration and parent submission rehearsal. Source and fixture hashes define identity; historical receipts under lineage-inputs are evidence only.

The large `lineage-inputs/fixture-archive.tar.gz` is the unchanged immutable fixture restoration archive. Its exact hash and individual members are in input-fixtures.json. It is needed to restore ignored build fixtures without relying on mutable packet source. The copied packet136 evidence bundle and generated replay evidence retain raw receipts needed for independent submission validation. Duplicated rehearsal bundles are intentionally retained as separate replay outputs; they are not new measurements.

Host-local immutable fixture bytes and ELF aliases use verified hardlinks where safe, preserving original files and symlinks with no extra payload storage. `lineage-inputs/fixture-storage.json` records every deduplicated member and digest. The full-shape fixture brought retained logical build size to302,374,633 bytes, above the requested300MB cap; this was caught at the next admission. Only our own reproducible entry/parser objects were removed, with hashes and rebuild commands retained, bringing it to296,269,057 bytes. No frozen evidence was removed. See `lineage-inputs/generated-object-retention.json`.

Build outputs, ELF hardlink aliases and caches stay out of Git. Rebuild native outputs with v5/build_engine.py and byte_gate143.py --build-intel, under the shared compile-turn arbiter and4GiB CPU process limit. Full-shape generated sources and fixture are reproducible with full_shape143.py after checking that no one-card hold is active. Regeneration must respect the300MB retained build budget, retiring its own reconstructible objects after recording their hashes.

The complete CPU queue test passed with explicitly simulated operational storage availability. Its retained real disk precheck refused the full chain reserve. Launch/readiness continue to check real storage. All182 copied symlinks remain present and unbroken.
