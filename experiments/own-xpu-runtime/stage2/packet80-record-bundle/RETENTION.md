# Retention

Keep the new GNU/device binaries, compiler objects and full-shape mock evidence
under ignored `build/`. Build cap is 1.2 GB and each process has an 8 GiB address
space cap. Parent object reuse is recorded in `evidence/object-identity.json`;
new translation units compile serially. The checked compiler mirror and source
pins reconstruct the binary. CPU fixtures rerun with `cpu_gate.py`; the real
production initialization path is instrumented only in generated test copies
by `full_shape.py`. No model payload or numerical device memory is allocated.
The mock reserves logical extents and validates all copy bounds.

Reconstruction order, before any chain starts: `build_engine.py`, `cpu_gate.py`,
`composed_cpu.py`, `full_shape.py`, `prepare_chain.py`, `prepare_packet.py`, then
`fast_reseal.py --dense production --hc production --experts wide64`.
Run Python with `-B`, nice 19, CPUs `8-15,24-31`, stdin `/dev/null`, and an
8 GiB process limit. Compile serially. `all_view_plans.py` runs all 264 real
window plans and restores the starting selection. `plan_gate.py` checks
the selected chain, input census, storage, oracle and prefix prerequisites.
These scripts depend on the pinned local parent objects and fixtures; this is
a lab packet, not a standalone public recipe. Keep those parent artifacts.

Tracked CPU receipts, test logs and generated source hashes preserve positive
and failed attempts. Previous preliminary selection seals are retained as
byte-verified gzip archives; prior chain seals are retained under `evidence/`.
The numerical fixture uses 90 cases per composed view and includes the selected
choice identity in its byte stream. Expected and candidate bytes agree across
GNU, Intel and two fresh executions of each. The production-shape mock is a
separate structural test, not a model-output or device-speed measurement.

The two `evidence/pre-composition-seals-*.json.gz` archives are about 8.5 MB
each. Retain them as exact historical selection identities from before the
per-view execution gate was strengthened. They were never launched. The
[retention manifest](evidence/archive-retention.json) records compressed hashes,
uncompressed sizes and every original member hash. To inspect or restore,
decompress with Python `gzip.decompress`, verify the raw SHA-256 against the
filename, then parse JSON: each key is a relative original filename and each
value its exact UTF-8 content. Write into a separate inspection directory under
`build/`, verify each member against the manifest, and never overwrite active
selections. Full member bytes were verified during archive creation. These
archives preserve superseded evidence, not additional runtime dependencies.
