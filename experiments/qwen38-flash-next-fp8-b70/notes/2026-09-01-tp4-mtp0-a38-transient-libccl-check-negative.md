# Qwen3.8 Flash-Next FP8 A38 generated-checksum negative

Date: 2026-09-01
Status: preserved pre-load generator negative; interpretation corrected

A38 reached the graph-safe oneCCL integrity gate and stopped before starting a
model server or loading any checkpoint. The original same-day interpretation
was a transient file read because five immediate direct reads matched the
frozen digest. A later source audit established the deterministic cause: the
broad `a37` to `a38` identity replacement also changed the `a37` characters
inside the literal SHA-256 value. The generated source expected a digest ending
in `d3a38fad6700`, while the unchanged library correctly ended in
`d3a37fad6700`.

This is a fail-closed generator defect, not an artifact-read, storage, or B70
failure. A39's three outer checks used the correct literal and all passed, but
its inner broad rewrite repeated the same defect with `a39`. A40 adds an exact,
counted restoration of the protected digest after identity substitution and
validates every generated launcher, client, and supervisor occurrence.
