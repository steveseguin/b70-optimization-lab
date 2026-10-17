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

## Result so far, depth 6 (c28a K32, 05:09-05:16 EDT)

- Census before the servers: one launch = lone rows at every used length, 7 rows (all) and 8 rows (4,183 / 4,183).
- **Not exact against depth 5:** 171 of 182 calls equal to c27a's; the first difference is call 63 (prompt 6,070
  tokens, identical; depth 5 wrote 331 tokens, depth 6 wrote 345), and the stream re-joins after the next notes
  update (calls 74 on equal). Score 39/39. Server totals: prompt 1,932,054 (c27a 1,932,094), generated 30,345 (30,313).
- Acceptance as predicted: mean acceptance length 5.98 (5.27 at depth 5), sixth position 0.692. But model time fell
  only 3.9 % (main -2.4 %, notes -6.4 %): each step costs about 7 % more at depth 6, not the 2-2.5 % assumed.
- **Decision (as registered): depth 6 is not adopted; depth 7 is not run** (the wrapper skips it when c28a differs).
  The lever is closed on speed alone too: under the 3 % bar on main calls, and depth 7 would add about 10 % tokens per
  step for about 7 % more step time.

## Which depth is right at call 63? (registered 05:18 EDT, before the run): campaign 28c

The difference says some kernel treats a 7-row check step differently from plain decoding, or a 6-row one does and
depth 6 happens to avoid it. The agent stream at depth 5 has never been compared with a server that does not draft.
One server like c27a with `--mtp 0` (no drafter; everything else the same), K32 on the same stream, seed 0
(`RUN=c28c MTP=0`, about 20-25 min: writing about 3x slower).

- **Prediction:** no-MTP equals c27a (depth 5) in every call: depth 5 has been exact against no-MTP on every suite
  run (strict 12/12, context, the 64/64 sequential oracle) and campaigns 24-27 repeat each other exactly.
- **Decision:** no-MTP = depth 5 everywhere: depth 6's difference is a 7-row check defect, recorded as the reason
  depth 6 is not exact (traced only if a later lever needs depth > 5). No-MTP = depth 6 at call 63: depth 5 has a
  defect on this stream: the context lane's exactness claim is suspended until it is traced (call-63 request
  captured and replayed). Neither: a third behaviour, traced the same way.

## Result, campaign 28c: no drafting (05:31-05:50 EDT; `data/2026-10-17-context-campaign28/`)

- **No-MTP equals depth 5 in all 182 calls** (everything but time and cached), 39/39, and the server totals are the
  same to the token (prompt 1,932,094, cached 1,564,160, generated 30,313). Depth 5 with every overlay of the
  context lane (one-launch verify, exact cache with tail, align cache) gives the same agent stream as a server that
  does not draft at all: the first such comparison on a whole agent stream.
- So depth 6's call 63 is a 7-row check defect (some kernel's row 7, or a 7-wide state path, is not plain decoding),
  recorded as the reason depth 6 is not exact; not traced, since no lever needs depth > 5 now (the census rules out
  the one-launch attention at 7 and 8 rows; the GEMMs are row-invariant to 16; candidates left: the GDN spec path
  after a 7-token acceptance, the conv-state width 3 + 6, the drafting buffers).
- What drafting is worth on this stream: model time 1,075.7 s without it, 367.3 s at depth 5 (2.9x); wall 18 min 49 s
  against 6 min 58 s.
