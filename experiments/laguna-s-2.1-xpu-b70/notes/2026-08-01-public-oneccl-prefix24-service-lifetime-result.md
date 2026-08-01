# Laguna public-oneCCL prefix-24 service-lifetime result

Date: 2026-08-01 America/Toronto

Status: **FAIL; treatment closed. No score.**

## Result

The first and only preregistered 13x512 prefix-24 run failed on request 0
before producing a completion. The service loaded cleanly, all four workers
exclusively mapped the checksum-pinned public libccl, and the four-rank draft
graph captured and replayed at `14/13`. During the first target width-12
execution, the target `122/121` capture completed on ranks 0-2 but not rank 3.
No rank reached a target `122/121` replay. The request then stopped making
progress at one emitted token / 90 computed tokens.

The engine reported four one-minute shared-memory-broadcast starvation
warnings and ultimately raised `TimeoutError: RPC call to execute_model timed
out`. The HTTP client subsequently timed out. No token-rate or exactness result
exists for this run.

This is a fresh-start nondeterministic capture/liveness failure: the preceding
2x400 model gate completed target capture and replay on all four ranks and was
bitwise exact, while the matched full-lifetime start hung during target capture.
Therefore the bounded correctness pass does not qualify this runtime for
service-lifetime use.

## Artifact

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-public4ce-prefix24-full-exact-20260801T211021Z
```

Key hashes:

- `identity.txt`: `f2196b958c6362801879e0bc7c02cee5ce28d82720b03414dbf39a24d9ce9276`;
- `public-oneccl-worker-maps.txt`: `daf55f0c5b0fe43904753d0115f208ddf23fcccefbe5d076dad65abcb91d483b`;
- `server.log`: `adc8f3a9288ea9bbab88cfa9ffc90fa8f8a10bfe94de8b7a12e59a794edea309`;
- `cleanup-status.txt`: `621005e3d8f4e0443c8d076bb4e5104f2bab517cb45d97b03a1d7f2e66ba35c8`.

Cleanup was successful: `stop_status=0`, `worker_status=0`, `idle_status=0`.
No reset, reload, unbind, FLR, shared-memory deletion, or reboot was used.

## Decision

Close direct captured target gathers under this public oneCCL build. Do not
retry prefix 24, widen to 96, mint a production runtime lock, score, or submit
it. Any future reopening requires a narrower root cause for the cross-rank
capture liveness failure and a new preregistration—not another cold-start roll.

## Transferable learning

A changing-input replay oracle and one bitwise-exact model start are necessary
but insufficient for a communication-runtime upgrade. Capture itself is a
distributed protocol and must be stable across fresh service starts before a
runtime can be promoted. Preserve per-rank capture and replay markers: here
they distinguished a capture-time rank-3 liveness failure from replay data
corruption and prevented an invalid retry or throughput claim.
