# Private entry frames for multiblock compilation

The first multiblock adapter (`4d99f69734d0759464b1571dd59593bfac18a9912a25b259e6e9ab4168ac55c5`)
failed the actual CPU five-block capture at its ninth graph: the shared forward
frame reached Dynamo's unchanged recompile limit of eight, with differing
backend callables. The failure receipt is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/multiblock-capture-cpu-01.json`.
The exact failed adapter is preserved in
`../patches/multiblock-compile-01.original.py`.

Candidate v2 compiles a private `invoke(x, **kwargs)` closure over the original
block. Each route retains its own function and cloned code object; a monotonic
source-local counter gives the code distinct `co_name` and `co_qualname` values
as well. The target still calls the original block with the original arguments.
It is not assigned to a module registration or `forward`. The intended result
is two native stage captures per private entry frame instead of competing
backend guards on one shared entry frame. The actual CPU capture now confirms10 graphs across five private entries;
native GPU/full-checkpoint gates remain pending.

No weight, model math, native backend, compiler options, lifecycle validation,
routing, cache contents, or Dynamo configuration was changed. All adapter
methods except the constructor, and all other top-level functions/classes,
are AST-identical to v1. No Torch import or native execution was performed for
this source change.

Final adapter SHA256:
`12ffb29cb4c8a61e8d9a22586a5f9f96ad170de882d62bfb4981f269d3b1bd3f`.
Exact diff: `../patches/multiblock-private-entry-02-reviewed.patch`.
Source checks: `../data/multiblock-private-entry-02-reviewed-source-check.json`.
The unexecuted intermediate version using only bare `code.replace()` remains
in `../patches/multiblock-private-entry-02.pre-review.py`, with its original
diff and source-check receipt preserved. Root owns CPU testing, packet sealing,
and any later deployment. This change carries no speed or XPU quality claim.


The unchanged five-block capture harness passed99 checks:20 block/stage/seed
cases,40 video/audio outputs, all finite and byte-identical to eager and compiled
repeats. Ten graph receipts qualify two stage graphs per block under unchanged
limits8/256. The two physical generated wrappers (shared across same-shape tiny
blocks) retain15 RMS, six sigmoid and two tanh-GELU native calls. The54-check
native CPU lifecycle test also passed on v2. [Results and exact commands](../data/multiblock-cpu-02/summary.json).

Packet06 is prepared and inactive: manifest
3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394.
Its copied launcher passed check-only with no device discovery or process change.
All inherited single-block files remain byte-identical; added multi-block source
and graph templates have their own identities. Only the packet checker changes
among inherited files, retaining prior validation through reviewed ancestry.
[Packet preparation](../data/multiblock-runtime-06/preparation.json).

The node now records/enforces actual8/256 runtime limits and uses explicit
extension names/module paths when loaded as a custom_nodes __init__.py. Original
node snapshots and narrow correction patches remain preserved. Twelve receipt
contracts, three plugin-layout regressions and seven in-memory builder tests
passed without Torch imports. This establishes packaging/source checks only.

The first builder attempt used system python3 and failed before packet creation
because Torch was absent there; the recorded venv command then passed. No
runtime setting changed to work around that interpreter error.

Passive postflight confirmed unchanged PID17769/packet05, empty queue, no fault
latch and no kernel fault match in the last30-minute window. No LTX application
reload, GPU request, host reboot or settings change occurred in this work.
Next: finish/review the bounded native client, then one controlled application
reload and actual selected-block/full-output qualification and paired timing.
