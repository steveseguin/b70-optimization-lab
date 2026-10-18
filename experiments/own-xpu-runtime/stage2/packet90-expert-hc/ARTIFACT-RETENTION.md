# Packet90 artifact retention and rebuild

The 4,194,304-byte `rope.bf16` is required by the source-relative loader. It is
an immutable runtime constant, not a generated cache. Restore from frozen
`../packet84-record-bundle/rope.bf16`, SHA-256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
Copied source identities are in `parent-source-manifest.json`; changed code is
local to this packet. No frozen source was edited.

`evidence/cpu-byte-identity.json` binds twelve fresh executions: two compilers,
two repeats, three views. Each raw byte stream is retained once, compressed
under `evidence/cpu-bytes/`, with its compressed and uncompressed hashes. Each
case ledger is retained. Full-shape censuses and native plans are gzip archives;
their hashes are in `evidence/full-shape.json`. Short/misaligned and selection
refusal logs, build commands, Python gates and temporary-queue plans remain.
Fixture scratch was deleted after gates; `evidence/scratch-cleanup.json` lists
only this packet's removed directories. Generated test sources and executables
remain locally for seal verification. No other packet's scratch was removed.

`build/` and each view's hardlinked `build/` are ignored. The checked source
mirror, inherited objects, compilers and packet84 build are local dependencies,
recorded by `build-device-receipt.json`, `engine-commands.json` and
`evidence/object-identity.json`. This is a lab screen bundle, not a public recipe.
Rebuilding requires those pinned dependencies and installed GNU/Intel compilers.
The serial build driver refuses changed parent sources/objects. A rebuild may
change binary hashes: retain old receipts and seal a new identity, never alter
these historical gates to match a different build.

For a clean reconstruction, copy the tracked packet into a fresh authorized
packet identity, preserve the old receipts separately, and run these CPU stages
in order with `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin `/dev/null`:
`build_engine.py`, `cpu_gate.py`, `full_shape.py`, `memory_plans.py`,
`python_gate.py`, `seal.py`, `final_check.py`, `queue_plan.py`.
The build uses an advisory compile-turn lock and waits for packet58g compiler
owners; one compiler at a time. Each stage enforces the 8 GiB address-space cap.
The final checked build was below 146 MB logical before fixture cleanup, well
below the 1 GB bound. No device executable is run by these preparation stages.
