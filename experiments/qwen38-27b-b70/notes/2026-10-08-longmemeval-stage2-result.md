# LongMemEval retention study, stage 2 result (2026-10-08)

**Decision: archive-and-recall with free-text notes is the retention method to recommend inside a 32K
budget.** It matches summarising on accuracy and costs a third of the time and a sixth of the tokens.
Reading the whole history in one call is still best whenever it fits the window.

Pre-registration: [2026-10-07-longmemeval-retention-prereg.md](2026-10-07-longmemeval-retention-prereg.md).
Stage 1 (pilot): [2026-10-08-longmemeval-stage1-result.md](2026-10-08-longmemeval-stage1-result.md).
Benchmark: LongMemEval_S, 56 questions (8 per stratum), ~110K Qwen tokens of chat history each.
Judge: the 27B itself (`longmemeval_judge.py --local`, secondary score; the official judge is GPT-4o and
was not available). Server: R314 image, two cards, 65,536 window, drafting, exact prefix cache.

## Numbers

All 56 questions (judged):

| method | correct | median time per question | median tokens written |
| --- | ---: | ---: | ---: |
| F, whole history in one call | 46/56 | 74 s | 432 |
| B32ira-free, archive-and-recall, free notes, 32K budget | 42/56 | 341 s | 10,506 |
| C32, summarise at 75 % of 32K | 19/23 (stopped) | 960 s | 58,107 |

Matched on the 23 questions the summarising arm completed (`data/2026-10-08-longmemeval-stage2/matched-23.txt`):

| method | correct of 23 | median time | median tokens |
| --- | ---: | ---: | ---: |
| whole history | 21 | | |
| archive-and-recall | 20 | 297 s | 9,004 |
| summarise | 19 | 960 s | 58,107 |

Only-one-right splits: 3 questions only archive got, 2 only summarising got, 1 both missed. That is a tie
on accuracy at this sample size; the pilot's 6/7 vs 4/7 did not hold up, which is what the pilot was for.

Where archive-and-recall loses to whole-history reading (42 vs 46): abstention questions 1/8 vs 4/8 (it
answers when it should say the history does not say) and preferences 4/8 vs 5/8. Everything else is 6-8 of 8
for both. Abstention is the next lever: a note-taking agent that records "not mentioned" evidence.

## How the run went

- Stage 2 started 03:40 one question at a time. At 09:27 the H3 stream tool (830 MB, cached decoded clips)
  was started beside the server with 2.1 GiB available; the host memory guard killed the server
  (`campaign-c2-MEMORY-GUARD.json`). Archive arm 52/56 at that point; nothing lost, finished jobs are skipped.
- Resumed 13:33 (`launch-d.sh`, unit `ctx-lme-stage2b`, `campaign-c3`). The owner then ruled out full-day
  runs ("Do not do full day soaks like this"); a STOP file ended the summarising arm after 23 questions at
  21:01 and the judge ran on everything. Cards left empty, no GPU fault in either campaign.
- Lesson for the harness: run trials concurrently against the server (it serves many users) so a 56-question
  arm takes an hour or two, not 17; host RAM per Harbor trial is the thing to measure first.

Raw: `/mnt/fast-ai/bench-results/context-longmemeval-20261007/stage2-client/runs/jobs/` (copies of the
summary, verdicts, client/launch scripts and campaign logs in `data/2026-10-08-longmemeval-stage2/`).
