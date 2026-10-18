# Packet95 retention and rebuild

Sources are copied from frozen packet90 and bound by `parent-source-manifest.json`.
The compiler turn helper is copied verbatim from packet94's coordinator-patched
version. `inspect_registers.py` adapts the lab's packet81 linked offline tool,
with compiler-turn locking and zero-spill checks. No outside code is adopted.

All commands run at nice19, cores8–15,24–31, `python3 -B`, stdin `/dev/null`,
8GiB address-space cap. Keep root free>=12GB and build<1GB. No GPU/device binary
execution, service, sudo, settings change or foreign cleanup is part of rebuild.

Sequence: `e2_memory.py`, `cpu_gate.py`, `build_engine.py`, `full_shape.py`,
`memory_plans.py`, `cleanup_fixture.py`, `inspect_registers.py`,
`inspect_schedule.py`, `python_gate.py`, `seal.py`,
`propose_jobs.py`, `final_check.py`, `queue_plan.py`. Run compiles serially; the
helper waits for existing compilers and whole-host lane holds. Do not recreate
or overwrite an existing seal/build receipt: use retained immutable artifacts
or a separately authorized successor packet. The new build reuses unchanged
parent objects by verified hash and rebuilds all changed translation units.

`build/` and the hardlinked view binaries are local ignored artifacts. Their
exact commands and hashes are retained in the build receipts. This is an
internal reproducible experiment, not a publicly released binary recipe.
Raw CPU comparison bytes and linked assembly are retained compressed, with
hashes. Fixture payload scratch is deleted after its evidence is retained;
source mirrors and generated full-size fixture sources stay because seals bind
them. No existing packet's evidence or scratch is deleted.

Large tracked artifact review: `rope.bf16` is a 4,194,304-byte fixed BF16 rotary
constant table copied byte-for-byte from packet90. Native startup and the
arithmetic identity need its exact bytes; it is not a generated compiler cache
or model-weight payload. Restore it from packet90's `rope.bf16` and verify the
SHA-256 in `parent-source-manifest.json`, or restore this packet's committed
copy. Duplication is retained to keep the frozen source packet self-contained;
no existing artifact was removed or consolidated.
