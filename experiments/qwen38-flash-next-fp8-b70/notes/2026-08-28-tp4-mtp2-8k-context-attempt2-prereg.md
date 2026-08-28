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

## Result

Attempt 2 passed every source, runtime, four-rank, placement, health, and cache
admission gate. The 32-block pool exposed 11,264 tokens. Its one authorized
p8192/o128 request passed the complete generic contract with exact
8192/128/8320 usage, zero cached tokens, a length stop, and 128 returned token
IDs. MTP2 was active: 53 drafts produced 106 draft tokens, 76 were accepted,
and positions zero/one contributed 41/35 accepted tokens.

The candidate output hash
`d3ce0631eb382e39168ee6bbbf177b0d49fbb27bc6c6466bcf215f16db8d0220`
diverged from the frozen MTP0 authority at zero-based generated-token index
26. Under the frozen interpretation this classifies the active-8K MTP2 cell as
a Grade-D cross-runtime parity quarantine, not as an MTP2-causal failure. The
`6.234518099 tok/s` conventional rate and `649.717302 s` TTFT are diagnostic
only; no protected speed or quality row changes.

The exact stop produced supervisor rc 0, no listener or recorded server group,
no compile/RPC paths, four rediscovered B70s at 42.871--42.883 MiB, and no B70
event. The bounded journal retained 22 corrected APEI records: 21 source-514
records associated with local NVMe `0000:01:00.0` and one source-512 record for
root port `0000:00:03.1`. These block clean-host/deployment wording but are not
relabeled as B70 failures. The verified `evidence.sha256` manifest hash is
`63b43c92ee2ee1e23055eab2fc4391d12466d4dae14d3a15b5107825ea6e998f`;
the compact receipt is
`../data/20260828-tp4-mtp2-8448-context-attempt2-parity-quarantine.json`.
