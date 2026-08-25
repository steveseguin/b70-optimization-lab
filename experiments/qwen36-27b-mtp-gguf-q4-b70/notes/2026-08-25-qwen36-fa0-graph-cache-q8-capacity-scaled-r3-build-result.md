# Qwen fa0 graph-cache Q8 capacity-scaled R3 build result

State: **build passed; parent retry pending**.

The affected SYCL backend rebuilt successfully with `-j2`. The first thin
launcher relink was invoked from a shell without oneAPI link-library paths and
failed at the linker after removing `llama-cli`; the backend itself had already
completed. Re-running only the launchers after loading the oneAPI environment
restored `llama-cli` and relinked `llama-bench` without recompiling the backend.

The thin launcher hashes remain unchanged. The new graph backend is 329,322,096
bytes with SHA-256 `7d03bc06...`; the final source hash is `25152136...`.
The proven graph-off source/build tree remains untouched. A newly sealed DSO
closure and distinct parent sentinel are still required before any depth curve.
