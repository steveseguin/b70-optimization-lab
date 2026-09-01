# Qwen3.8 Flash-Next FP8 A36 Torch-cache verifier negative

Date: 2026-09-01
Status: preserved zero-request orchestration negative

A36 loaded the official FP8 checkpoint on all four ranks in 77.34--77.92
seconds, completed the size-1 full graph capture on all ranks in 51 seconds,
and became healthy. Its map-authoritative oneCCL and kernel-path rules passed.
The client then sent zero requests because the inherited A33 verifier treated
any file under the isolated `TORCHINDUCTOR_CACHE_DIR` as proof that the model
had been compiled.

That interpretation is too broad. The exact API and EngineCore configurations
both record `CompilationMode.NONE`, and the server log records twice that
Inductor compilation was disabled by user settings. Operator-level JIT,
autotune, and nested PyTorch helpers can still use Torch's isolated cache.

A37 keeps the cache inventory as evidence, requires the two mode-NONE/disabled
receipts, rejects known whole-model compilation receipts, and retains every
mapped-library, graph, quality, hash, and teardown gate. A36 has no quality or
speed credit. The server tore down, rank 0 returned to 42.88 MiB, host memory
and swap recovered, and no B70 error appeared in the bounded journal review.
Two corrected PCIe receive events named the local NVMe controller, not a B70;
they are retained as host-storage observations and did not interrupt the load.
