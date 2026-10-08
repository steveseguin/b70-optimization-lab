# LongMemEval retention study, stage 1: control and pilot (2026-10-08, interim)

Preregistration: [2026-10-07-longmemeval-retention-prereg.md](2026-10-07-longmemeval-retention-prereg.md).
Data: `data/2026-10-08-longmemeval-stage1/`. Raw: `/mnt/fast-ai/bench-results/context-longmemeval-20261007/`.

**In plain words:** on an outside benchmark of long chat histories (about 110K tokens each, 56 questions
sampled across all seven kinds), the 27B reading the whole history in one call answered 46 of 56 (judged).
In the 7-question pilot of the methods that work inside a 32K budget, summarising answered 6 of 7 but took
17 minutes a question and wrote 62K tokens; archive-and-recall with free-text notes answered 4 of 7 in 6
minutes and 10K tokens; the plain files agent answered 1 of 7. Pilot numbers are development data (one
question per kind); the full 56-question comparison of the two deciding arms is running (stage 2).

## Judged scores (judge = the 27B itself with the official prompts: a SECONDARY score; the headline needs GPT-4o)

| Arm | n | ssu | ssa | pref | multi | temporal | update | abstain | judged | built-in grader | median wall | median tokens written |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| F: whole history in one call (131K window) | 56 | 8/8 | 8/8 | 5/8 | 7/8 | 7/8 | 7/8 | 4/8 | **46/56** | 32/56 (preference judge-only) | 74 s | 432 |
| C32: summarise at 75 % of 32K | 7 | 1/1 | 1/1 | 1/1 | 0/1 | 1/1 | 1/1 | 1/1 | 6/7 | 5/7 | 1,027 s | 61,677 |
| B32ira-free: archive-and-recall, free notes, 32K | 7 | 1/1 | 1/1 | 0/1 | 0/1 | 1/1 | 1/1 | 0/1 | 4/7 | 4/7 | 343 s | 10,292 |
| E32r: files allowed, plain agent, 32K | 7 | 1/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 1/7 | 1/7 | 113 s | 5,303 |

No invalid or void trials (pilot continuation rule met). Abstention counts a refusal as correct.

## What to make of it (so far)

- This is the opposite of the synthetic-ledger picture: on real multi-session chat, summarising kept more of
  what the questions asked for than the free-notes archive agent did, at three times the time and six times
  the writing. The archive agent's misses were a preference question (needs a judgement about the user, not a
  fact), a multi-session question and an abstention (it answered instead of refusing).
- The full-history control at 46/56 is the in-window reference the 32K methods are measured against.
  A self-judged score can be generous; treat it as an upper estimate until GPT-4o judges the same pairs
  (`longmemeval_judge.py` with `OPENAI_API_KEY`, verdict files are append-only and the summary prefers them).
- Host RAM, not the cards, limited the run: the 131K-window server left 2.8 GiB beside the one-call client
  but only 2.2 GiB beside a Harbor trial; stage 1b moved to a 65K window (2.4 GiB) after a clean STOP.

## Stage 2 (running)

`B32ira-free` and `C32` on all 56 questions as fresh trials (pilot trials not pooled), then the local judge;
unit `ctx-lme-stage2`, out `/mnt/fast-ai/bench-results/context-longmemeval-20261007/{campaign-c2,stage2-client}`.
Expected about 19 h. `Ar` (keep everything, 262K window) and `E32r` on all 56 follow if the deciding pair
warrants it.
