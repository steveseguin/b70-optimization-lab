# Laguna M8 in-process replay: 128-token insufficient-sample abort

Date: 2026-07-25 America/Toronto

Status: **failed closed after the graph generation; no complete graph telemetry
or cross-arm result**.

Sealed root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-inprocess-replay-27a09399b-8cf58ed0f-20260725T000824Z
```

The canonical q1 and optimized eager DFlash arms each completed exactly one
fresh 128-token greedy generation with `cached_tokens=0`. They matched
bitwise:

- token-ID SHA-256:
  `9e17797a21ee55f6cc0bbe31eaee35299f120c877c7d9a1e9c48570b8e3850de`;
- text SHA-256:
  `71b947e096974fd3fe2456a0addb6b73c796d526af3168655c6ae0cb93bed632`;
- finish reason: `length`.

The graph arm loaded and completed its generation. All four ranks captured the
audited M8 topology with 146 graph segments and 145 eager boundaries, and all
four logged at least one replay. The profiler writes its rank files only after
31 sampled replays, however, and the profile directory remained empty.
Therefore the only supported replay-count statement is that the graph arm
completed fewer than 31 sampled replays. The driver rejected the arm with:

```text
graph generation did not close all four replay profiles: []
```

No graph `driver.json` or campaign analysis exists, so the graph output was not
sealed and no q1/eager/graph correctness, timing, performance, benchmark, or
LocalMaxxing claim can be made from this root.

The campaign and every arm passed their strict pre/post worker and device-idle
checks; all post-worker reports are empty. The sealed root is an abort artifact
only and must not be reused.

Disposition: preserve the profiler's 31-sample contract and start a new,
preregistered campaign with a longer single generation. No retry or extra
request is permitted within any arm.
