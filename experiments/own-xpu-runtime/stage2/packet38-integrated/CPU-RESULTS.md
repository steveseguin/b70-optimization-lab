# CPU qualification

Qualification is still running. This file is not a seal. The final authority
will be `build-receipt.json`, bound to the source, binary and evidence hashes.
No device executable ran, and no model speed is claimed.

## Verified during the resumed session

- Rebuilt GNU host, Intel host, address/undefined-sanitized and device variants.
  Device compilation alone is not device qualification.
- Native standalone controller: 1,123 comparisons per normal, ASan/UBSan and
  LLVM22 ThreadSanitizer build. Each covers all 1,093 ternary guess scripts
  through length six, 24 longer random cases and six mode/end cases.
- Native mailbox failure/lifetime gate: five checks and 32 repeated requests
  in each of the same three configurations. No bounded spin was used.
- CPU controller hand-over: median 11.04 microseconds, p95 17.78 microseconds;
  mailbox wake-up median 4.11 microseconds. This is a two-thread CPU diagnostic, not a cross-process rank,
  GPU latency or model-throughput claim.
- Parent miniature runtime gates: 130 cases per GNU/Intel/sanitized build;
  draft gates: seven per build. Prepared capture invalidation: 15 tests;
  argument block guards: 16 checks. Owner/lifetime: ten suites.
- Packet33 linked fixtures: 1,296 checks, 9,072 output rows, six fresh owners.
  Full non-GEMV fixture identity passed in four fresh host processes.
- Capacity256 attention: 528 full-array comparisons across two compilers,
  with 66 workloads per compiler covering contexts88–152 and256.
- Timing metadata: ten synthetic-clock checks. Window wrapper: 36 tests.
  Full-disk/stop cleanup and state-retention checks passed; exact counts and
  source identities remain in their individual receipts.

- Actual miniature Engine/controller equivalence: all 1,109 cases passed,
  including the 1,093 exhaustive scripts, twelve long requests and four mode/end
  cases. All tokens, guesses, hit/miss events, fixtures and final states matched.
- Request reset: three prompts in two orders for Python/native and none/MTP,
  24 requests and twelve prompt comparisons. Every comparison matched all
  32 fixture files and 210 target state entries (216 with MTP).
- All fixture and model window receipt paths passed end to end on CPU. The
  suite checker schema was checked against five available oracle requests.
  These oracle-derived checks are distinct from actual runtime execution.
- The actual two-process miniature receipt path measured a 3.15 ms native
  median forward gap and 4.05 ms Python gap, eight samples each with full state
  capture enabled. This is a diagnostic with no cross-server speed verdict;
  see `cpu-handover-cost.json`.

## Remaining qualification

GNU/Intel/native real-model modes, four final MTP captures, and the persistent
real CPU suite are running or queued. The real CPU suite uses the three-request
snapshot frozen when those were the available complete oracles. Its partial
coverage is explicit. Twelve-prompt device qualification remains separate
coordinator work.

## Independent review

The resumed controller, reset and token-authority reviews are in
`review-resume-controller.json`, `review-resume-reset.json` and
`review-resume-authority.json`. Their source hashes are checked again by the
seal. Historical reviews/failed or interrupted attempts remain evidence and
cannot substitute for a current gate. See `RESUME.md` for disk recovery and
`ARTIFACTS.md` for retention.
