# Retention

This packet vendors source, symlink identities and small immutable fixtures from
packet142c. `lineage-inputs/vendor-origin.json` binds every copied tracked file to its original
hash and commit; original bytes remain in that frozen packet and Git commit.
The source tree is intentionally large to keep the active import/include closure
local. Historical compressed CPU captures and oracle fixtures remain evidence.
Artifacts above 1 MiB are necessary exact-capture/byte or inherited reproduction
fixtures, not caches; restore from this commit and the vendor-origin commit.

Native builds are ignored artifacts, rebuilt with v5/p145_v5_build_engine.py
through ops/compile_turn.py. Native source and output hashes are recorded in
v5/evidence/build.json. Frozen external object links are allowed only under
immutable-binaries.json and the build receipt; never repin changed bytes.
Full-shape archives and GNU/Intel byte transcripts reproduce CPU gates only.
No model weights, credentials or driver cache is added to Git.
