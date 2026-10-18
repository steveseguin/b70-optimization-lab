# Packet92 artifact retention and rebuild

The 4,194,304-byte rope.bf16 is a required runtime constant, not a cache.
Restore it from frozen packet84-record-bundle/rope.bf16, SHA-256
92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390.
Native sources are copied from packet84; parent-source-manifest.json records
those bytes. Packet90 supplies only the compile-turn and screen scaffolding,
including the direction pattern from commit 1a55e9c5d. No packet90 arithmetic
or frozen source is modified. packet92-host.patch retains the host-only delta.

build-device-receipt.json and evidence/object-identity.json bind the reused
objects, changed entry/selection objects, checked include closure and both
linked binaries. engine-commands.json contains exact commands. This is a local
lab bundle; it needs pinned parent build artifacts and installed GNU/Intel
compilers, and does not claim public clean-clone reproducibility.

Raw mock state bytes and full-size startup censuses/operation lists are retained
as hash-bound gzip files. Miniature token/layer/draft-state identities and timing
rows remain as JSON. Every successful fixture's scratch is removed after its
gate; scratch-cleanup.json records the leftover failed setup directory removed.
Generated full-size source and binary remain for verification. build/ and view
build/ hardlinks are ignored, not evidence intended for Git.

Rebuild under a new authorized packet identity with historical receipts kept,
using nice -n 19, taskset -c 8-15,24-31, OMP_NUM_THREADS=2, python3 -B and stdin
/dev/null: build_engine.py; cpu_gate.py; mini_gate.py; full_shape.py;
memory_plans.py; python_gate.py; seal.py; final_check.py; queue_plan.py.
Never overwrite an existing seal. Build/gates enforce an 8 GiB address-space
limit, compiler turns and a 12 GiB root-free floor. Compiles run one at a time.
Final build logical size is 138,053,853 bytes (under 1 GB); root had more than
17.5 GiB free at final preparation. No other packet's scratch was removed.
