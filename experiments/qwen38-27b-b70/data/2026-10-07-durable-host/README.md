# Queued durable pilot: execution receipt

The service `ctx-durable-pilot-v1.service` entered `waiting` on 2026-10-07 at
00:31 UTC. The protected plan-E supervisor still owned the host. **No new model
trial had started at this snapshot.**

- [receipt.json](receipt.json): unit identity, source commit and CPU checks.
- [queue.json](queue.json): frozen supervisor, server profile and dependency hashes.
- [status.json](status.json): copied initial waiting state, not live progress.
- [execution-started.json](execution-started.json): coordinator start receipt.

Live status/results are in
`/mnt/fast-ai/bench-results/context-durable-v1-20261007`. The service owns the
handoff, qualification, development checks, held-out pilot and server cleanup.
It makes one attempt and records failures; it does not automatically restart.

Seventeen mocked CPU coordinator tests and independent operational review passed.
The frozen harness still passes 58 tests. These are software checks, not model
performance results. The pre-existing global pin audit remains 231 drifted pins
of 318, outside this change.

See [operation and cancellation](../../scripts/context/DURABLE-HOST-RUNNER.md)
and the [unchanged evaluation protocol](../../notes/2026-10-06-durable-context-prereg.md).
