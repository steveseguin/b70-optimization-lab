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
