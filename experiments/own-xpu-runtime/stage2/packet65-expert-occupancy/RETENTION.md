# Retention and restoration

This packet is a host replay candidate, not a publicly reproducible release.
It keeps copied packet64 C++ source, strict build/mirror helpers, candidate
source, commands, receipts, offline assembly and small CPU byte streams.
The source snapshot manifest records original parent hashes. Unneeded parent
chain/publication scripts were omitted so they cannot accidentally launch an
inherited chain under a new packet name; see the omission inventory in evidence.

`build/` and selection-view `build/` paths are ignored. The source build uses
read-only hardlinks to packet64 objects and rebuilds the model entry, selection
parser and expert submission translation units. It never modifies inherited
objects. No frozen tree is an output destination. The build receipt binds every
inherited object, rebuilt source and output binary. Original compiler/object
dependencies must exist to repeat this incremental build.

CPU byte fixture originals are retained outside Git at:

- `/home/steve/own-xpu-runtime-results/packet65-expert-occupancy/cpu-byte-fixture-wide64/`
- `/home/steve/own-xpu-runtime-results/packet65-expert-occupancy/cpu-byte-fixture-wide64-intel/`

The first three-arm preparation is superseded, not a failed speed experiment.
Its initial register/build receipts and assembly are retained as preparation
history. Current receipts and seals alone identify the five-choice binary.
Do not try to verify historical source hashes against subsequently expanded
source files and call them current qualification.

To restore a clean *new* unsealed working copy on this host, use nice19,
`taskset -c 8-15,24-31`, Python `-B`, `OMP_NUM_THREADS=2`, stdin `/dev/null`:

1. Restore the pinned packet64 objects and compiler dependencies.
2. Run `build_engine.py` (serial CPU compilation, no device execution).
3. Run `cpu_fixture.py --output <fresh-path>` with GNU, then Intel host compiler;
   compare all raw output hashes across both fresh runs of each compiler.
4. Run `inspect_registers.py`, `validate_engine.py`, and `selection_tests.py`.
5. Run the wrapper tests and `seal_selections.py` with the fresh CPU fixtures.
6. Run only CPU `--plan` checks. Device windows belong to the coordinator.

Build/seal scripts intentionally refuse to replace a completed build or seal.
Preserve an existing packet and its outputs; reconstruct elsewhere rather than
editing a sealed selection. The coordinator campaign always requires a new
output directory. Raw model weights are never copied into Git.

Large-artifact review: `rope.bf16` is 4,194,304 bytes, byte-identical to
packet64’s engine constant. The native engine reads this table adjacent to its
bound source path and checks its hash. It is retained to preserve exact RoPE
arithmetic and prevent a missing-input replay; restore it from this commit or
the identical frozen packet64 file. It is not a model checkpoint or a cache.
Git can share its existing identical content object. No evidence was removed
on the basis of size.
