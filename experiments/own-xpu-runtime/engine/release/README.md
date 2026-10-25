# Canonical engine source bundle

This CPU-only exporter packages committed canonical engine sources. It does not
compile the engine, run a model, access GPUs or publish anything. The result is
**research source**, not a complete portable runtime or a quality-qualified release.

From the repository root, after committing the intended source changes:

```bash
python3 -B experiments/own-xpu-runtime/engine/release/source_bundle.py /tmp/ownrt-source.tar.gz
python3 -B -m unittest discover -s experiments/own-xpu-runtime/engine/release -p 'test_*.py'
```

The archive includes tracked `src/`, `build.py`, the engine README and committed
`planning/` and `release/` files when present. Required inputs must match `HEAD`;
uncommitted changes are refused. A deterministic generated build manifest retains
the compiler, translation units, compile flags, link order and link flags. It omits
historical binary/object locations and consolidation metadata, whose original
committed file hash remains in the provenance manifest. Engine source bytes are
unchanged, including required source-tree lookup data. The Host-only fixture header
`gsq-rco-iq3s/integration/host-support/device_validation.hpp` is an explicit
supplemental input: its committed bytes are included as `src/device_validation.hpp`
and separately hash-bound. It is not misclassified as a system header.

`SOURCE-MANIFEST.json` records the Git commit, all original input hashes, all
exported payload hashes, local include edges, external system headers and toolchain
requirements. A companion `*.tar.gz.manifest.json` additionally records the archive
hash and size. Archive names, ordering, permissions, ownership and timestamps are
fixed. Repeated exports of the same inputs yield identical bytes in the same Python
and zlib environment. Existing output files are refused.

The exporter checks literal includes throughout the source corpus, including
inactive preprocessor branches. Missing or untracked local dependencies, escaping
paths, symlinks and nonliteral includes fail closed. External angle-bracket headers
must belong to the named C++/Linux/platform header families; they are inventoried,
not compiled or certified. Unknown project headers fail closed even with angle
brackets. The manifest's historical file hashes
describe consolidation; current committed source hashes are the exported identity.

The compiler is Intel oneAPI 2026.0 at the path in the build manifest. C++20 system
headers, OpenSSL and Level Zero development libraries are also required. The
bundler does not validate their installation or modify them.

Model weights, tokenizer inputs, external loader authority files, service adapters,
host admission snapshots, receipts, objects and executable binaries are excluded.
Existing hardcoded runtime defaults remain in the source and their locations are
listed in the manifest. Those dependencies still need a portable runtime recipe,
followed by a clean-source build, runtime smoke, independent quality qualification,
public asset upload and remote hash verification. Packaging source closes none of
those gates and supplies no new performance result.
