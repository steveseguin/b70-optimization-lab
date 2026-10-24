# Additive extractor/build checkpoint

The earlier README and startup review remain frozen historical checkpoints. The
archive-aware `extract.py` and compile-only `build.py` now exist; neither has run
its action mode. The read-only native command plan is retained in evidence.

Extraction is fixed to the original prompt00 target archive03. It opens a held,
no-follow, canonical regular file of exact90,040,912-byte length, hashes that
compressed FD against the completed archive ledger, rewinds it, then streams all
2,113 members. Every name/length/content hash must match the independent original
baseline index. No arbitrary archive path is unpacked. The stream is bounded at
231,442,500 uncompressed bytes, and only the four named64,160-byte fixtures are
retained. Physical compressed bytes read are counted (at most two compressed-file
passes). Thus the proposal is not merely a64KiB storage read.

All ten original routes remain intact. Only valid nonempty consumed expert IDs
are deduplicated for weight extraction. The containing GGUF shard is held open,
its current stat and exact header prefix are checked against the frozen census,
and at most ten921,600-byte slices are read from the exact tensor/expert offsets.
The original512×2560×640 type20 descriptor is mandatory. All copied fixtures and
slices are reread, hashed and fsynced; `fixed.hpp` is exclusive and durable before
the success flag. Failure preserves partials and prevents an automatic second
extraction. No whole-bank or whole-model payload hash is asserted.

The build retains the existing64MiB forecast,4GiB compiler address-space limit,
helper placement and compile-turn serialization. It rebuilds one new micro TU
and links39 unchanged original runtime objects. The original p6 control is the
exact hash-bound integration `3.o` compiled from the frozen kernels.cpp; the new
TU's device image must contain `DirectKernel` for type20/SG32. Linked symbols must
retain the original p6 routed entry and micro entry. CPU/source/fixture hashes,
actual compiler depfile, compiler identity and offline image/symbol logs are
retained. The helper never invokes its native output.

Prerequisites remain separate: reviewed bounded extraction, successful full
native build, final sealed schedule/manifest, independent wrapper review, then
root operational admission. Current `once.py` intentionally cannot form an
operational plan without those missing receipts. No GPU permission is implied by
source preparation or the eight tiny ACK tests.
