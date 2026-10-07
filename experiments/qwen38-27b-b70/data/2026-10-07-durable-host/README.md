# Queued durable pilot: execution receipt

**Final status:** v2 stopped after sixteen completed trials and a retrieval-cap
failure. Its server stopped and GPU release was confirmed. No run is active.
See the [pilot result](../../notes/2026-10-07-durable-pilot-result.md).

**Update, 01:50 UTC:** v1 failed its passive port check before device work.
[Failure records](v1-failure/status.json) remain preserved. A bounded port-release
wait passed 20 CPU tests and independent review; the explicit
[v2 attempt](v2/receipt.json) is now active at
`/mnt/fast-ai/bench-results/context-durable-v2-20261007` under unit
`ctx-durable-pilot-v2.service`. The original receipt below remains historical.

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
