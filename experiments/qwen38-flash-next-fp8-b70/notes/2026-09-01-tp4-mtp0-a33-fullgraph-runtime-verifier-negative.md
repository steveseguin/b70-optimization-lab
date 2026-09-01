# Qwen3.8 Flash-Next FP8 A33 runtime-verifier negative

Date: 2026-09-01
Status: preserved orchestration negative; zero inference requests

A33 passed every static, storage, source, stage, public-oneCCL, four-card, and
collective preflight. All 131 local-NVMe shards loaded in about 78 seconds per
rank, all four ranks completed the size-1 full graph capture in 51 seconds,
and the endpoint became healthy.

The frozen client then stopped before its recovery canary. The runtime verifier
first proved that the EngineCore mapped exactly the expected public libccl and
that its bytes matched the pinned digest, then rejected the process because
its `LD_PRELOAD` environment value did not equal the launch path string. The
loaded process map is the execution authority; `LD_PRELOAD` is only launch
provenance and may be absent or augmented after a subprocess exec. Requiring
both as identical strings was redundant and incorrectly strict.

The failure sent zero requests, so A33 has no quality, reliability, speed, or
promotion credit. The supervisor tore the service down; the kernel journal was
clean, all four GPUs returned below 43 MiB used, host memory/swap recovered,
and no reboot is required. Protected `5.515783 tok/s` MTP0 and
`20.727176 tok/s` MTP4 results are unchanged.

A34 retains every A33 model/runtime/graph/placement/quality selector. It uses
new attempt, port, cache, RPC, lifecycle, and evidence paths. Its verifier
still requires every collective process to map only the exact public libccl
and verifies that file's digest. If `LD_PRELOAD` declares a libccl path, any
different path is rejected; an absent string no longer rejects an already
verified live mapping.
