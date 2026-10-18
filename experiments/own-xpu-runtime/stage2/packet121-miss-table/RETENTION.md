# Retained inputs and rebuild outputs

`rope.bf16` is the 4 MiB frozen packet118 RoPE constant (SHA-256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`).
The copied runtime resolves it relative to its source path. Keep its exact
bytes with this bundle; restore from packet118 and verify this hash. It is
an existing public runtime constant, not a new model-weight download.

`source-copy-provenance.json` pins the original frozen source inventory and
lists unused Python launchers and historical archive copies excluded from this
packet. Their originals remain untouched. The used native sources and mirror
helpers remain here. `v5/source-copy-provenance.json` separately pins the v5
wrapper origin, parent selection/dispatch/memory plan and generated mirror.

Build directories are ignored and bounded to 250 MB in total; the builder
refuses below 25 GB root free. GNU/Intel and fixture binaries are bound by
CPU receipts but restored by rebuilding, not by committing binaries. The
full-shape compressed archives verify every original member before retaining
their bytes. Byte-case evidence is gzip with a hash of the uncompressed case
stream. Keep failed CPU logs as the explanation for corrected test setups.

The verbose build receipt may approach 1 MiB because it pins every inherited
object/source and actual compile command. It is needed to distinguish the
new restore code from unchanged arithmetic; regenerate with `v5/build_engine.py`.
