# Retention

The vendored packet136/packet149 source closure and original RoPE constants are
retained to reproduce compilation without mutable source dependencies. Large
copied constants and source-history fixtures retain their originating packet's
bytes except explicit local path relocation in text. Compiler objects and
binaries remain ignored and are rebuilt with v5/p151_v5_build_engine.py; parent
ELF inputs are hash-bound by immutable-binaries.json. Pair fixtures use synthetic
weights, regenerate their expected/actual bytes, verify matching hashes and
remove only those task-created transient outputs. No external model is copied.
Historical template metadata is provenance, not packet151 qualification.

packet151c retains two large `fusion-rope.hpp` headers (12,582,900 and
12,583,130 bytes) in the private vendor/checked-source closures. They are
compiler input constants, not caches: the checked copy includes the relocated
local guard. Their current exact hashes, the original 4 MiB RoPE table and
retained parent report fixtures are in retention-census.json. Restore their
tracked bytes from the source commit named by READY-FOR-DEVICE.json; do not
substitute mutable sibling files. The original first-build census and payload
inventory remain byte-identical under lineage-inputs/p151-first-build/.
