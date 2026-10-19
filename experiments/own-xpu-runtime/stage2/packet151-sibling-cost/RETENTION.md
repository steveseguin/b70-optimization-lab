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
