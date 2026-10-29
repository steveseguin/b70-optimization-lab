# Speculation miss cost in the four-card TP service (2026-10-29)

CPU-only analysis of retained traces; no device work. `python3 -B analyze.py` regenerates
[analysis.json](analysis.json), which holds every number below.

Configuration analysed: SC117 IQ3_S, binary `b7786ad42675`, two pipeline ranks each split exactly across two
cards, both output heads split (`OWNRT_TARGET_HEAD_SPLIT=1`, `OWNRT_DRAFT_HEAD_SPLIT=1`), 65,536 context.
Inputs: the three fresh both-splits servers and the 36 suite runs of
[target-head-split-2026-10-29](../target-head-split-2026-10-29/RESULT.md) (raw runs on the RAID archive).

## What a miss costs

- **10.08 ms per miss** by replaying the kept controller traces (three servers, the 3,490-token request); a fit over
  the 36 suite runs gives 9.87 ms. The replay reproduces each measured decode span within 0.1 ms.
- Misses are **23.9% of guesses** and take **17.6–18.0% of suite decode time**.
- Breakdown: **9.41 ms (93%)** is rank 0 rerunning its 23 layers with the corrected token. Every layer depends on that
  token and rank 1 needs the result, so none of it can be skipped. 0.55 ms is the rollback; 0.10 ms is rank 1 running
  slower right after idling.
- Hit cycles take 10.82 ms. Since the head splits, rank 0 is the slower rank in 71% of them, and its 0.295 ms
  snapshot before each guessed half sits on that critical path.

## Candidates (projected suite gain, assuming zero implementation cost)

| Candidate | Projected gain | Why |
| --- | ---: | --- |
| (a) start the redo as soon as rank 1 finishes | 0.41% | the existing cancel already fires early; it hit 1 of 69 misses |
| (a') guess the correction token on rank 0 | negative | rank 0 has no slack; a second row costs 1.6× (packet166); closed in packet132 |
| (b) reuse work the corrected token does not change | 0 | nothing in the redo is token-independent |
| (c) overlap the redo with rank 1's next half | 0 | rank 1 needs the redo's output; moving the post-miss draft gives 0.13%; rank 1's post-idle slowdown 0.18% |
| (d) free snapshot and rollback | 2.48% (2.22–2.64%), ceiling 3.19% | a real version still copies, so likely 1–1.5% |

No single candidate reaches the 3% bar for implementation, so nothing was built. A DO-NOT-REPEAT row records this.

## What would pay

A faster rank-0 half: about **0.79% per 0.1 ms** until rank 0 stops being the slower rank (about 0.2 ms), then
0.18% per 0.1 ms. Exact steps, each gated as usual (bitwise full dump against one card, then fresh-server A/B/A/B):
1. drop the wait after the snapshot copy;
2. split the draft's large GEMVs by output rows across rank 0's two cards;
3. trim the rollback's waits.
Together these project to about 3%.
