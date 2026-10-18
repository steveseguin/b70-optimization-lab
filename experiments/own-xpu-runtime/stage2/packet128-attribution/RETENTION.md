# Retention and reproduction

All existing packet, screen and ops trees remain frozen. Parent native/text
files were copied; their original bytes are bound in `parent-manifest.json`.
`instrumentation.patch` preserves the observation delta. Arithmetic objects are
inherited by hash from packet124b and its frozen provenance, never edited.

The generated build is intentionally ignored. Rebuild with `cpu_prepare.py
build_engine.py cpu_gate.py reset_gate.py full_shape.py`; then seal the diagnostic
view, run `argument_gate.py`, reseal with `seal_view.py --reseal`, and validate the
proposal in a temporary queue. Never run copied historical entrypoints as new
packet128 campaigns. Only README's diagnostic entrypoints are registered here.

`rope.bf16` is the inherited deterministic numerical constant table and exceeds
1 MiB. It is required by the exact engine include/data closure; retain its original
bytes and restore from packet124b at the hash in the parent manifest. No model
weights or binaries are committed. Generated mirror/startup source hashes in
receipts bind the local build; rebuild at the documented repository path.

Retain all device event and per-request native receipts after the coordinator
run. No timings from CPU test fixtures are retained as device measurements.
