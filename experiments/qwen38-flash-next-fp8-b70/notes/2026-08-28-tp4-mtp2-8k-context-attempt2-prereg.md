# Flash-Next TP4 MTP2 active-8K attempt-2 preregistration

Date: 2026-08-28

## Why this is a new attempt

Commit `96303b3a7` permanently preserves the attempt-1 packet. The detached
command environment ended its supervisor process while leaving the
supervisor's bounded child alive. This was detected before the matrix client
ran. The exact owned launcher and server were stopped, all four B70s returned
to 42.875--42.883 MiB, port 19667 and temporary paths were absent, and the
bounded kernel window contained no B70 event.

Attempt 1 has no exact-depth output, client request log, before/after request
metrics, or classification: no matrix request was sent and it earns no result
credit. Its raw directory remains at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp2-8448-r1-attempt1`;
the raw manifest SHA-256 is
`12562da78fbd39379e94985cf8681af2068c4969439cd53c0749d5b999f00841`.

Attempt 2 changes only the controller identity and fresh paths: attempt 2,
port 19668, state `/tmp/q38-mtp2-8448-attempt2-supervisor`, and corresponding
attempt-2 run/cache/compile/RPC/evidence paths. Run the supervisor in a
persistent managed execution session, not as a detached shell job. All model,
runtime, cache, request, authority, classification, timeout, lifecycle, and
host gates from
`2026-08-28-tp4-mtp2-8k-context-prereg.md` remain unchanged.

## Frozen executable identities

- delegated base launcher:
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- attempt-2 launcher wrapper:
  `18203bcb7a2f59c685785edec5e0c6f2fb54f467fcc8cf46eff975b0d233f1a5`;
- attempt-2 one-request client:
  `e9053aaf041361ed074febe8ce31f021cf8d47d4ae0c3e48bef42a80cb231ab2`;
- attempt-2 lifecycle supervisor:
  `f3eecf24f34db7d71d4f033c41ea8c894d5a50afa562d7c99dabe095ab730daa`.

These identities are frozen before attempt 2 executes. Existing featured and
certified speeds remain protected regardless of this arm's outcome.
