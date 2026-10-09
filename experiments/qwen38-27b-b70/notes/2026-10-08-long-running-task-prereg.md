# Long-running task past the window: pre-registration (2026-10-08)

**Question.** An agent on the 27B runs one task whose history grows far past the live context cap. Which
way of managing the context keeps answers right and keeps the agent fast as the history grows? The
owner's framing: live context under about 200K, history many times that, "fastest and most lossless of
the bunch"; lossy methods are allowed in the comparison. Serving stays exact; only the history management
varies.

**Why the earlier tests do not answer it.** LongMemEval asks one question at the end of a 110K history
that fits the window; the 32K-budget ledger runs ask only at the end. Neither measures accuracy or speed
*during* a task that keeps running past the cap.

## Task

The sparse narrative ledger (`make_sparse_prose_tasks.py`, density 3, `--words`) with the new
`--probes-every N --probes-k 3`: after every N-th batch a PROBE item asks three questions to be answered at
once in `/app/answers.json` (keys `pJ_i`), then the stream continues. Each probe holds one question of each
type: a counter's value now (distance = since its last change), a value a counter held at the end of an
earlier item that was later overwritten, and a one-off detail of the narrative (who did what, a small
number). Questions target distance bins 1-4, 5-24, 25-99, 100-399, 400+ items back (about 2K tokens per
item), cycling through the bins that exist yet. The final item asks the usual 24 current values. The grader
is unchanged (exact match per key; memory-mode storage rule; void on violations). `tests/reference.json`
records each probe's type, item, reference item, distance and tokens back.

Development setting: live cap 48K (`CONTEXT_BUDGET` 49152), history 480K tokens (10x the cap), 240
batches, probes every 25 batches (9 probes, 27 questions), seed 0, server window 65,536. The ratio
history:cap is what the use case is about; the smaller absolute cap lets all arms share one server
(two-card KV cache 311K tokens at this window) so the run ends in hours.

## Arms (all memory mode, same budget)

| arm | method | loss |
| --- | --- | --- |
| W48 | sliding window: drop the oldest turns when over budget | lossy, nothing kept |
| D48 | compaction as coding agents do it: drop old tool output and thinking first, then oldest turns | lossy |
| C48 | summarise at 75 % of the budget (standard compaction) | lossy, summary only |
| B48ir | CLM self-editing, read mode, protected STATE.txt table, no archive | lossy, state only |
| B48ira | the same plus the verbatim archive and `recall` | lossless store |
| B48ira-free | self-editing with free-text notes (6K cap) plus the archive | lossless store |

Quoted events (B32iq) is not run: it is specific to counter arithmetic, and the use case is general.

## Measures

1. Probe accuracy by distance bin and by type; final-query accuracy; blanks reported separately.
2. Speed as the history grows: minutes per 100K tokens of history in each 100K segment (from the `next`
   delivery timestamps), so a method that slows with the history shows it; model calls; tokens written.
3. Peak context; management counts (summaries, truncations, folds, recalls).
`probe_analysis.py OUT_DIR` produces the tables.

## Decision rules (fixed before the run)

- Report every arm as a point on (speed, accuracy); "best" is the most accurate arm within each speed
  band, not a single winner. An arm whose probe accuracy at 100+ items back is below the sliding window's
  is not a memory method.
- Accuracy ties within 2 questions are ties; then the faster arm wins.
- A void trial (storage rule) counts as a failed arm for that seed and is rerun once.
- Confirmation: the two best arms rerun at the owner's numbers, cap 200K (`B200*` arms), history 1M,
  window 262,144, one at a time, only after this result is in and its duration is stated (about one hour
  per arm).

## Expected duration (stated before starting)

The 1M-token read-mode run took 62 minutes alone at a 32K budget. Six arms at 480K sharing the server:
about 1 to 1.5 hours including probes, then a few minutes of analysis. Host RAM per Harbor process is
measured on the CPU stub before the server starts; the arms run concurrently only if the headroom beside
the server allows it, otherwise two or three at a time.

Run files: `/mnt/fast-ai/bench-results/context-longrun-20261008/` (`longrun-client.sh`, `launch.sh`).
