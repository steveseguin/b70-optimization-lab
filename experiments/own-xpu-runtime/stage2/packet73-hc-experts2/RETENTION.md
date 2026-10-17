# Packet73 retention

Retain source copies, parent pins, rejected source variants, compressed offline
assemblies, compiler/fixture receipts, all selection seals and private wrapper
tests. These are local screening artifacts, not a public deployment recipe.

`build/` is ignored. The final logical tree occupies about 303 MB, including
retained offline scratch from rejected attempts and all host/device objects.
Peak child RSS during the engine build was 726,108 KiB. The preparation imposed
an 8 GiB address-space limit and used one compiler command at a time. Five
view directories hardlink the same two engine artifacts and CPU fixture bytes;
they do not allocate five independent builds. No parent artifact was deleted.

Restoration requires the pinned packet65 object files, generated rope header
and their source closure, retained locally under their recorded paths in
`evidence/object-identity.json` and the build receipt. `build_engine.py` rebuilds
the four changed translation units under both GNU-host and Intel-device modes,
then links inherited objects verified by hash. A clean checkout without those
parent objects must reproduce packet65 first. Do not claim cross-host or clean
build certification from these receipts.

`cpu_gate.py` reconstructs the small fixture bytes using GNU and Intel, with
two fresh CPU processes each. The expectation and candidate hashes must agree
with the receipt. No model payload or backend is used. The original fixture
logs are mirrored under `evidence/cpu-runs/` for review.

`inspect_registers.py` plus the checked source mirror reconstructs the current
offline assembly using pinned Intel tools and linked device libraries. Gzip
assemblies are tracked and hash-bound. Rejected report paths predate archive
renames; `evidence/rejected-artifact-map.json` resolves each original path by
its exact recorded hash, preserving the original reports unchanged. Older
unlinked dumps are diagnostic failures, not accepted spill evidence.

The full binary and intermediate build files are local, ignored artifacts.
The five `screen-seal.json` files are immutable once handed off. Changed code,
configuration, fixtures or wrapper sources require a fresh named packet/view;
never overwrite evidence from a started device screen.

`rope.bf16` is the 4 MiB inherited fixed rotary table required by the source
closure and runtime. It is deliberately retained byte-for-byte for local
reproduction, not a generated cache. Restore it from the pinned packet70 copy;
`parent-source-manifest.json` records its original SHA-256. Its size alone is
not permission to discard it.
