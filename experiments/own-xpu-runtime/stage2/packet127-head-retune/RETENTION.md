# Packet127 retention

This is a separate source copy of packet124, with packet105b micro helpers
and packet120 residency/receipt helpers. Frozen parents are read-only inputs.
`copy-lineage.json` pins the original copied bytes; `build-device-receipt.json`
and the view seals pin the actual compiled closure and unchanged inherited
object files. `integration.patch` records the focused runtime delta.

Large retained source includes are required for exact builds: the copied rope
constant headers under `lineage-inputs/` and the prototype reference fixture
must retain their original bytes. They are not generated caches. Restore them
from the packet124 paths named in copy-lineage or rebuild the copied source
closure from this commit. Local native binaries and generated build mirrors
are ignored. Small compressed CPU fixtures, allocation censuses and startup
reports remain tracked, bound by hashes in the view seals.

CPU reproduction, from the repository root, uses
`nice -n 19 taskset -c 8-15,24-31 python3 -B` and stdin `/dev/null`.
Use `cpu_prepare.py` for `build_engine.py cpu_gate.py full_shape.py
test_gates.py build_microbench.py startup103.py`; then `cold_worker_gate.py`;
then `cpu_prepare.py prepare_packet.py`. Run `launch_limit_gate.py` directly
with unlimited inherited address space (its intercepted native boundaries
must reject a finite cap). Finally run `cpu_prepare.py queue_plan.py`.
No command here runs a GPU program. Micro and grid proposals require the
coordinator's separate device window.

On a clean checkout, restore immutable host fixture executables and input
metadata from packet124's `build/gnu-host`, `build/input` and
`build/fusion-fixtures` before the startup gate. Rebuild inherited native
objects through the pinned ancestor recipes when their local caches are
absent. Rebuilding changes source-bound receipts; do not overwrite a sealed
view or claim that a new compiler output has the old identity.
