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
`planning/`, `release/`, `profiles/` and `deployment/` files when present. Required inputs must match `HEAD`;
uncommitted changes are refused. A deterministic generated build manifest retains
the compiler, translation units, compile flags, link order and link flags. It omits
historical binary/object locations and consolidation metadata, whose original
committed file hash remains in the provenance manifest. Engine source bytes are
unchanged, including required source-tree lookup data. The Host-only fixture header
`gsq-rco-iq3s/integration/host-support/device_validation.hpp` is an explicit
supplemental input: its committed bytes are included as `src/device_validation.hpp`
and separately hash-bound. It is not misclassified as a system header.

`SOURCE-MANIFEST.json` records the Git commit, all original input hashes, all
exported payload hashes, local include edges, external system headers, literal
Python import edges, standard-library modules and toolchain requirements. A companion `*.tar.gz.manifest.json` additionally records the archive
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

When the committed portable live adapter is present, the exporter explicitly
requires its shared `tools/pipeline_driver.py`, `wavefront_driver.py`,
`live_wavefront_driver.py`, `persistent_live_suite.py` and
`persistent_wavefront_driver.py`, plus the dynamically loaded
`planning/wavefront.py` and `live_draft.py`. This includes lazy imports even when
a one-shot path does not call them. Literal Python imports throughout the selected
corpus must resolve to packaged local modules or the Python standard library;
untracked/missing modules and undeclared external packages fail export. Tests
also check the portable adapter imports from an isolated extracted layout.
See [the portable live research recipe](../deployment/LIVE.md) for its scope;
packaging shared tools does not make their historical lab launchers portable.

Committed ring entrypoints now activate additional explicit dependency groups:
target-only ring, actual recursive-provider ring, pending-provider qualification,
and rolling qualification each require their complete predecessor closure. The
rolling group includes `tools/rolling_ring_driver.py` and all four
`planning/rolling_provider` package modules, including `__init__.py`. Missing or
untracked package members are refused even if another source tree happens to
make an import work locally. Older source trees without these entrypoints retain
the earlier portable-live requirements.

The ring CPU test helpers used by committed planning/review modules are also
included when tracked. An import of an untracked fixture still fails export;
there is no fallback to the developer's working tree. The tests cover package
relative imports, an isolated extracted package import, deterministic archive
bytes, and refusal of missing runtime members or untracked helper dependencies.
This change does not alter previously published source snapshots, including the
9d snapshot, and does not itself build or upload a replacement. The independent
v6 comparator/finalizer and external model/run evidence require their own
closure before claiming a complete rolling qualification replay package.

The compiler is Intel oneAPI 2026.0 at the path in the build manifest. C++20 system
headers, OpenSSL and Level Zero development libraries are also required. The
bundler does not validate their installation or modify them.

Model weights, tokenizer inputs, external loader authority files, service adapters,
host admission snapshots, receipts, objects and executable binaries are excluded.
Existing hardcoded runtime defaults remain in the source and their locations are
listed in the manifest. The profile/preparer and portable target/live recipes
provide separate generated deployment paths; their actual build/runtime evidence
is distinct from source export. A new deployment still needs clean-source build,
runtime smoke, independent quality qualification,
public asset upload and remote hash verification. Packaging source closes none of
those gates and supplies no new performance result.
