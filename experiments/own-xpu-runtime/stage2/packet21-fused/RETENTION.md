# Packet 21 evidence retention

The 4,567,685-byte measured launch census intentionally retains all four real CPU executions:
per-site counts, per-layer totals, output hashes, runtime arguments, timings,
and the owner allocation census. This permits independent checking of totals,
remaining unfused sites, and descriptor-memory admission. It is evidence, not a
generated cache. `build.py` binds it into `cpu-tests.json`, and README.md uses
its measured rows. Keep the tracked JSON even if it exceeds one MiB; a size
warning is not permission to delete this record. Reproduction is
`measure_census.py` after `build.py --phase build`, using the admitted local
model store and the prepared input manifest. New runs produce new timings and
allocation identities; their bytes cannot replace this historical receipt.

The complete frozen/R5 CPU receipts, fixture receipts, dependency reports,
interrupted-attempt records, compiler commands and source hashes remain tracked.
Their output hashes preserve comparisons after temporary output trees are
removed. `rope.bf16` is an exact copy of packet18's table, recorded in source
provenance, and is retained because native arithmetic must use those bytes.

Ignored `build/host`, `build/icpx-host`, `build/device`, `build/sanitized` and
`build/guard-tests` are build artifacts. Retain the compiled binaries and their
manifests. `build/input`, `build/fusion-fixtures` and `build/fusion-rope.hpp` are
sealed runtime/fixture inputs, not scratch. Do not delete or regenerate them
before a prepared device window. Native binaries have never run here.

Temporary mini, real-model, fixture, sanitizer and census output directories
are removed only after their comparisons, output hashes and timing summaries
are retained and the build is sealed. `scratch-cleanup.json` records the
removed directory names and sizes. `build.py --phase all` reconstructs and
requalifies CPU preparation from the retained source and approved weight store;
it does not recover historical wall times or create device evidence.
