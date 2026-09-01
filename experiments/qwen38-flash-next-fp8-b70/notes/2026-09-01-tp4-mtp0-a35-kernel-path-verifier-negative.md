# Qwen3.8 Flash-Next FP8 A35 kernel-path verifier negative

Date: 2026-09-01
Status: orchestration negative; zero inference requests

A35 reproduced A33's successful 78-second model load, 51-second all-rank graph
capture, and healthy endpoint. Its corrected preload check passed. The client
then stopped before the recovery canary because the live EngineCore did not
retain an exact `CCL_KERNEL_PATH` environment string. The verifier had already
hashed the pinned kernel file; the launch identity also records that path and
digest. No request, quality test, or benchmark ran.

The service tore down cleanly, all four GPUs returned below 43 MiB, host memory
and swap recovered, and the kernel journal was clean. A35 has no quality or
speed credit. A36 validates any retained oneCCL path/threshold/graph values and
rejects contradictions, but permits those launch-only strings to be absent
after exec once the mapped library, artifact hashes, server configuration, and
graph-capture receipts have passed. Protected results remain unchanged and no
reboot is required.
