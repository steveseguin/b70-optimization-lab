# CPU qualification

CPU qualification completed on 2026-10-12. All 91 required gate receipts passed.
The final authority is `build-receipt.json`, bound to source, binary and evidence
hashes; this summary does not replace it.
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
- Timing metadata: eighteen synthetic-clock checks, including early-EOS
  event counts, endpoints and per-rank fields. Window wrapper: 36 tests.
  Full-disk/stop cleanup and state-retention checks passed; exact counts and
  source identities remain in their individual receipts.

- Actual miniature Engine/controller equivalence: all 1,109 cases passed,
  including the 1,093 exhaustive scripts, twelve long requests and four mode/end
  cases. All tokens, guesses, hit/miss events, fixtures and final states matched.
- Request reset: three prompts in two orders for Python/native and none/MTP,
  24 requests and twelve prompt comparisons. Every comparison matched all
  32 fixture files and 210 target state entries (216 with MTP).
- All fixture and model window receipt paths passed end to end on CPU. The
  suite checker schema was checked against all twelve available oracle requests.
  These oracle-derived checks are distinct from actual runtime execution.
- The actual two-process miniature receipt path measured a 3.15 ms native
  median forward gap and 4.05 ms Python gap, eight samples each with full state
  capture enabled. This is a diagnostic with no cross-server speed verdict;
  see `cpu-handover-cost.json`.
- The real-model no-draft CPU receipt path measured a 1.85 ms native median
  forward gap and 2.16 ms Python gap, eight samples each. These include host
  capture and scheduling work and are diagnostics from one fresh pair each,
  not a speed verdict or a prediction of GPU hand-over cost.
- All fifteen real-model mode runs passed: GNU/Python, Intel/Python and
  GNU/native, each in none, n-gram, all-hit, all-miss and MTP. Each matched eight
  emitted tokens and all 384 retained layer fixtures. Native/Python additionally
  matched guesses, hit/miss events and both ranks' complete target/draft state.
- Four fresh draft captures passed and match the parent streams and fixtures.

## Persistent real CPU suite

The Intel host binary ran native control with MTP and the packet38 candidate
map through one distinct two-token warm-up, then three 64-token requests in the
same two rank processes. All 192 tokens and 1,152 retained fixtures matched the
read-only suite oracle exactly. Both ranks shut down cleanly. Each request's
2,070 state-evidence files were hash-verified and archived before scratch removal.
The final export rechecked every request. See `suite-real-cpu.json`.

| Prompt | Exact tokens | Exact fixtures | Draft hits / guesses |
| --- | ---: | ---: | ---: |
| incident-retrospective | 64 | 384 | 53 / 63 |
| code-review | 64 | 384 | 43 / 63 |
| customer-email | 64 | 384 | 51 / 63 |

This is the preregistered three-request snapshot, one repeat. Its partial scope
is explicit: `complete_frozen_suite=false`. The twelve-oracle schema checks and
miniature reset-order proof are separate evidence. CPU decode rates are null;
these results do not establish a speed or GPU latency result.

## Remaining coordinator qualification

Run the exact sequence in `WINDOW.md`: device build/admission and identity,
model-shape K2 selection, fresh-owner draft validation, both controllers on the
single-prompt modes, and the full twelve-prompt WS/WSs suite with two repeats.
All twelve oracle entries were available and passed schema checks at final seal.
Only coordinator windows can close device exactness, controller latency, kernel
selection, cache behavior and model speed. No CPU timing substitutes for them.

## Independent review

The resumed controller, reset and token-authority reviews are in
`review-resume-controller.json`, `review-resume-reset.json` and
`review-resume-authority.json`. Their source hashes are checked again by the
seal. Historical reviews/failed or interrupted attempts remain evidence and
cannot substitute for a current gate. See `RESUME.md` for disk recovery and
`ARTIFACTS.md` for retention.
