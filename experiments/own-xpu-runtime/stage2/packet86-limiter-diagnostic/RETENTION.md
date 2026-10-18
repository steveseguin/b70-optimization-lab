# Packet86 retention

The build is below 1 GB (about 157 MB before seal-history retention), with one
compiler at a time, nice 19, cores 8–15/24–31, stdin closed, and an 8 GiB address
space ceiling. There was no GPU execution, service, sudo, setting change or kill.
No existing packet, screen, or ops source was edited.

Keep all copied source, provenance manifests, receipts, fixture outputs and
negative/fix evidence. `build/` contains local compiled artifacts and generated
checked/full-shape mirrors; it is ignored by Git. Rebuild requires the exact
packet75 receipt/object pins and Intel 2026.0 toolchain recorded in the commands.
`build_engine.py` refuses replacing its build receipt; preserve any existing
build/receipt before a deliberate rebuild. Run the scripts with the CPU limits
above, then `fullshape_gate.py`, `OMP_NUM_THREADS=2 ... cpu_gate.py`,
`operator_gate.py`, the Python tests, `seal.py`, and `queue_plan.py`. Never execute
the device binary during CPU preparation. Seals are local preparation receipts,
not a publicly deployable recipe.

The retained `evidence/superseded-seals-*.tar.gz` is intentionally over 1 MiB
(about 7.9 MiB). It preserves the first seals, their native binary and fixtures
before the queue-output collector and summary labels were corrected. Its adjacent
manifest records every member's original SHA256 and the archive hash. `reseal.py`
verified every member before replacing our own generated views. Restore into a
scratch directory, verify against that manifest, and keep its old identity
separate; do not overlay current views. Tar hardlinks preserve the one shared
binary rather than storing eight independent images. This is recovery evidence,
not a release asset or a measured result.

The first Intel compile rejected two implicit signed-to-unsigned conversions in
a raw-byte initializer; explicit unsigned casts fixed it. GNU and Intel then
built successfully. An initial CPU-gate invocation refused before execution
because OMP_NUM_THREADS=2 was absent; the corrected invocation passed. The first
queue collector expected one JSON object; the planner actually emitted eight
successful JSONL records. The collector was corrected, the prior seals retained,
and both lanes replanned. No device or driver incident occurred.

Two seal-history archives are retained (about 7.9 MiB each). The second also
preserves the revision before standalone reporting required explicit completed
drain, released-lane and device-isolation proof. The final build's logical size
is 150,190,781 bytes, independently checked in `evidence/final-check.json`.
