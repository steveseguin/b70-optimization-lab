# Draft depth for agent traffic (2026-10-17, context lane)

## Why look again

Depth 5 was chosen on general text: on 2026-10-03's servers each later draft token was accepted about 67 % of the
time, and depth 6 was 2 % slower over whole answers (`2026-10-03-fp8-comm5b-result.md`). Agent traffic drafts far
better. Campaign 27's server log (c27a, K32 + K64 + edit probe, 11,516 check steps): mean acceptance length 5.27 of
6, per-position acceptance 0.960 / 0.912 / 0.863 / 0.801 / 0.737, i.e. each later token accepted 92-95 % of the time
given the one before. A sixth token at the same trend (about 0.66) adds about 12.5 % tokens per step; the cost is one
draft pass and one verify row, about 0.7-1.0 ms of a 40 ms step (2026-10-03: 3.5 ms for five of each). So writing
could be about 9 % faster at depth 6, and a seventh token (about 0.6) adds about 10 % more for the same cost again.
Writing is about two thirds of an agent run's model time (K32: 30,249 tokens written, about 250 s of 367 s).

Exactness at depth 6 and 7 rests on: the verify rows (7 or 8 per step) each computed as plain one-token decode
(`b70-fa-verify-rows`, max 8 rows by default, one launch); every two-card W8A16 GEMM shape row-invariant up to 16 rows
(`data/2026-09-15-fp8-one-card-r309/gemm-row-census-r304.json`, `-r309.json`, TP2 shapes, M 1-16 all equal); the
other per-row kernels as at depth 5. The one-launch verify has only been censused at 6 rows.

## Test (registered 04:54 EDT, before any run): campaign 28, `scripts/run-20261017-campaign28.sh`

1. Census on card 0 (`scripts/census-verify-rows.py`, R314, split counts from the overlay file), 7 and 8 rows, pages
   of 832. Must hold: the one-launch rows equal the lone rows at every length where it is used. Any mismatch stops
   the campaign before a server starts.
2. Two servers in turn, each campaign 27's (tail, one launch, piece 832, one sequence) with `--mtp 6` (c28a), then
   `--mtp 7` (c28b); each runs K32 and K64 on the 240K rules stream, seed 0.

- **Must hold:** every call equal to c27a's (and so c26a's) in everything but time and cached count; 39/39; server
  prompt and generated totals equal. A difference at a depth stops adoption of that depth and is traced.
- **Predictions:** mean acceptance length about 5.9 (depth 6) and 6.4 (depth 7); model time against c27a (K32
  367.3 s, K64 393.2 s) about -5 to -8 % at depth 6 and -8 to -12 % at depth 7; prompt reading unchanged within 2 %.
- **Decision:** adopt for the context lane the deepest exact depth whose model time is at least 3 % below the next
  shallower depth's on both arms. The packages are not touched (their depth was chosen on general text; a change
  there needs its own sweep and the owner's go).
