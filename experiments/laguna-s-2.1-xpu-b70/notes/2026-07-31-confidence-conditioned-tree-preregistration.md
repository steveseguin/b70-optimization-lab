# Laguna M12 — confidence-conditioned tree diagnostic preregistration

Date: 2026-07-31 America/Toronto

Status: **diagnostic only; no tree is enabled and no throughput claim is
authorised by this experiment.** The protected record remains
**125.461973 tok/s conventional** (126.729266 legacy), 13/13 bitwise exact,
BF16 KV, M=12/DFlash-11.

## Question

Can information already produced by the DFlash draft logits choose, before the
target forward, among three fixed-width verifier layouts often enough to make
a tree worth implementing?

1. eleven-node top-1 chain;
2. ten-node top-1 spine plus the position-0 rank-2 alternate;
3. nine-node top-1 spine plus rank-2 alternates at positions 0 and 1.

All layouts retain twelve target rows including the bonus row. Any eventual
implementation must still emit the target model's greedy token sequence; an
alternate is only another target-verified candidate, never a substitute for
target verification.

## Why the old evidence is insufficient

The 2026-07-26 probe used raw prompts instead of the benchmark's chat request
construction and recorded token ids only at draft position 0. It measured
257 rank-2 rescues among 588 position-0 misses (43.71%), but cannot evaluate a
position-1 alternate or a confidence policy. Its own correction note withdrew
the earlier tree projections.

The old joined cycles nevertheless provide a useful upper-bound screen. With
perfect hindsight, selecting the one-alternate layout only on its 257 rescue
cycles would add 0.125 emitted tokens/cycle. Applied to the current record's
3.9509 emitted tokens/cycle, that projects only about 129.4 tok/s before any
overhead. Therefore a one-alternate implementation cannot credibly target 130;
position 1 or an independent cycle-time saving is required.

## Diagnostic treatment

Starting from the protected vLLM commit `1a7f61fef`, make a separate diagnostic
worktree. Extend the already default-off cycle-attribution top-k probe to record,
for draft positions 0 and 1:

- top-1 and top-2 token ids;
- their unmodified logit values and margin;
- the next-cycle realised target token and rejection count needed for the
  existing offline join.

Run the exact benchmark chat request construction and fixed prompt order against
the protected record binaries/configuration. The run is diagnostic evidence,
not a scored throughput leg. It must fail closed unless prompt token counts and
generated token hashes match the protected record, all four rank files agree,
cache use is zero, and teardown is clean. Request boundaries must be explicit
or reconstructed and checked from the benchmark rows; joins may not cross a
request boundary.

## Analysis and gate

For every completed cycle, derive the observed reward of each of the three
layouts. Report:

- static-layout oracle values;
- a per-cycle hindsight oracle (an upper bound, never a deployable result);
- confidence-threshold policies using only values available before target
  verification;
- per-prompt counts and leave-one-prompt-out validation, so a threshold is not
  selected and evaluated on the same prompt;
- bootstrap or prompt-level uncertainty;
- the projected rate from the current 125.461973 tok/s record, with explicit
  zero-overhead and overhead sensitivity.

Tree integration is authorised only if both conditions hold:

1. the benchmark-matched hindsight oracle projects at least 131 tok/s at zero
   overhead; and
2. a leave-one-prompt-out observable policy projects at least 130.5 tok/s before
   integration overhead.

Otherwise preserve the diagnostic and close the route. No benchmark score from
an attribution-enabled process may be promoted or submitted.

## Safety

- Do not modify either protected record worktree.
- Do not reset, reload, FLR, or reboot hardware for this diagnostic.
- Stop on any collective failure and report the exact boundary.
- Preserve the diagnostic patch, identities, raw rank files, analyzer, and
  negative result if the gate fails.

## First diagnostic attempt: correctly rejected

Run:
`laguna-confidence-tree-diag-20260801T093915Z`

The exact endpoint leg itself passed: 13/13 token-and-text exact against q1,
cache-zero, the protected 146/145 target and 14/13 draft topology, 1,622 probe
rows per rank, clean teardown, and the full post-stop idle interval. The
analyzer nevertheless refused to emit a projection because rank 3 differed
from ranks 0--2 on one of 3,244 recorded draft positions. At cycle 719,
position 1, ranks 0--2 selected token 330 at logit 25.125 as rank 2; rank 3
selected token 585 at 25.375. The top-1 token and emitted output were unchanged.

This is a useful implementation finding, not grounds to weaken the gate: a TP
tree needs one canonical alternate identity. Diagnostic vLLM commit
`8546e88e4` now broadcasts rank 0's two top-k values and indices across the TP
group only while the non-scored probe is armed. One corrected diagnostic is
authorised. The rejected run and original `d4ad0ba2d` recorder commit remain
preserved.

## Canonical-broadcast attempt: rejected

Run:
`laguna-confidence-tree-diag-20260801T094924Z`

The extra in-loop TP broadcasts deadlocked after the first request. The engine
reported no shared-memory broadcast block for 60 seconds twice. The run was
interrupted through the launcher's normal cleanup trap; cleanup recorded
`original_status=130`, `stop_status=0`, `worker_status=0`, and `idle_status=0`.
No process or port survived, and no reboot, driver reload, device reset, or FLR
was used. Commit `8b8cd5227` removes the unsafe broadcast while retaining both
the failed commit and run as evidence. **Do not insert a new collective at this
point in the speculative loop.**

## Final offline screen: route closed

The complete first run was analyzed with rank 0 as an explicitly labelled
screening canonical source. This does not satisfy the four-rank agreement gate,
and the analyzer therefore keeps `integration_authorized=false`. It is still a
valid upper-bound screen because the benchmark output was 13/13 exact and the
single disagreement is fully reported.

Analysis:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/analyses/laguna-confidence-tree-20260801T093915Z-rank0-screen.json`

| quantity | result |
| --- | ---: |
| joined benchmark-matched cycles | 1,609 |
| position-0 rank-2 rescues | 157 / 438 |
| position-1 rank-2 rescues | 118 / 324 |
| static one-alternate projection | 126.350234 tok/s |
| static two-alternate projection | 125.915973 tok/s |
| per-cycle hindsight oracle | **130.890237 tok/s** |
| leave-one-prompt-out margin policy | **129.271627 tok/s** |
| prompt-bootstrap 95% interval | 128.384966--130.007626 tok/s |
| policy projection at 0.5% overhead | 128.628485 tok/s |

Both preregistered gates fail: the hindsight oracle is below 131, and the
observable policy is below 130.5 even before implementation overhead. The
conditional-tree route is therefore closed without integration. The protected
record remains **125.461973 tok/s conventional**, unchanged.
