# Packet150 retention

Keep the closed source copy, exact GNU/Intel binaries and immutable inherited
object symlinks, miniature CPU fixture, oracle inputs, CPU receipts and proposals.
`retention-census.json` records regular files of at least 1 MiB with their hashes
and purposes. No model weights are included. The original symlink objects and
packet136 history remain under `lineage-inputs/` as provenance, not live source.

Rebuild the native entries with `v5/p150_v5_build_engine.py`, controller mocks
with `v5/controller_gate.py`, and the miniature replay/restore fixture with
`v5/split_cpu.py`. Use nice19, cores8–15/24–31, Python `-B`, stdin `/dev/null`;
all native compilation goes through the shared ops compiler arbiter. Original
ELF inputs are verified against `immutable-binaries.json` before each link.
Exact commands, artifact hashes and source hashes are in
`v5/engine-commands.json` and `v5/evidence/build.json`.

The retained prompt inputs are required by the oracle manifest, not model
weights. Rope tables and generated headers are retained source dependencies.
The report-schema fixture is needed for CPU-only real report-path rehearsal;
its old times are never packet150 measurements. The original retained packet145
trace regression is read-only. Never remove frozen parent artifacts or replace
literal symlinks with dereferenced copies. Python caches are excluded.
