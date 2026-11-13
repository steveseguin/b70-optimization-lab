# Round 19, long-context status lc107 / lc107b (build tp107, 2026-11-13 00:20-00:22 and 00:33-00:44)

tp107 with the best prompt mode (`OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 OWN_PX_BCS=1`), the long documents
x19k / x34k / x69k / x95k (dsv41-work/prompts/xl), 256 answer tokens each checked against the e82 plain references;
guessing (BEST + draft vocabulary) after x19k and x69k. Speed runs only, no traces, no sampler. Before: r1 (tp73,
2026-11-10/11, blocks of 16). lc107 ran x19k, then the host reset at x34k's first prompt block (tenth event,
CURRENT.md 2026-11-13); lc107b ran the rest after the restart.

## In plain words

Every answer the same as the references (4 of 4 plain, 2 of 2 guessing SAME AS the plain run), no fault.

| document | read now | read before (r1) | writing now | before | guessing now | before |
|---|---|---|---|---|---|---|
| x19k (18,692 tokens) | 29.72 s (628 tok/s) | 66.90 s | 91.43 tok/s | 69.10 | 138.58 | 89.76 |
| x34k (33,815) | 56.11 s (603) | 123.29 s | 91.66 | 68.39 | | |
| x69k (68,506) | 120.06 s (570) | 255.85 s | 87.28 | 67.16 | 125.80 | |
| x95k (95,497) | 173.75 s (549) | 362.28 s | 87.13 | 65.20 | | |

Reading is 2.1-2.25x faster than on tp73 and slows only ~13 % from 19K to 95K tokens; writing drops only from 91 to
87 tok/s between 19K and 95K (the sparse attention keeps the step nearly flat). Guessing after a long document:
138.6 (19K) and 125.8 tok/s (69K) against ~147-165 on short prompts (fewer guesses kept: 2.41 / 2.26 per cycle;
checks 15.6 / 16.2 ms). Card memory: at least 2.59 GiB free per card after load at 95K + 1K tokens.

## Files

`lc107-summary.txt` (x19k), `lc107b-summary.txt`, `lc107b-marks.txt`, `spec/` (guess logs). Scripts in
`../round18-scripts/strategy/` (lc107.sh, lc107b.sh).

## Decode profile at 3K vs 69K (lp107, card 2, `OWN_GPROF=2`, tp107, 64 answer tokens, answers same)

GPU time per step 9.64 ms at 3K, 10.21 ms at 69K (+0.57): index scoring `IndexerScoreB` / `BC` +0.37, top-k
selection (`TopKSelQ` / `CQ` / `BQ`) +0.32; nothing else grows. (Round 18 at 69K: top-k 1.66 + index 0.99 ms; the
candidate lists and the new selection forms removed most of it.) The timed runs' 3K -> 69K gap (10.3 -> 11.46 ms per
step) is the 0.57 ms plus the engram rows read from disk for the long documents' answers (532 us per step at 69K
against 54 us warm at 3K). So long-document writing has no big lever of its own left; long-document reading gains
from the prompt kernels (rux4) like short prompts. Files: `lp107-*-decode-profile-card2.txt`, `lp107-summary.txt`.
