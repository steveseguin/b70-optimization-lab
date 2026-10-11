# Long-horizon context, fast-scale baseline: 16K live cap over a 240K history (2026-10-10)

First run of the program in `docs/long-horizon-context-program.md`, section 5. One seed, so treat every number as a
first reading, not a result.

## Setup

- Server: Qwen3.8-27B FP8 on **one** B70 (card 0), R314 state-stride image, MTP depth 5 with the INT4 draft shortlist,
  cpu-embed, exact prefix cache (`b70-prefix-cache-exact`, `--mamba-cache-mode align`), tool calling on, window 26,624
  (the most the card holds beside the weights: 3.0 GiB of KV; 28,288 was the engine's own ceiling). One request at a
  time. Launch argv: `experiments/qwen38-27b-b70/data/2026-10-10-context-16k-baseline/server-launch.json`.
- Host: the Gemma LAN service had to be stopped for the run; with it resident the launcher's 2 GiB host-RAM guard killed
  the server. 15 GiB host, 6.1 GiB available with the server loaded.
- Task: sparse prose stream, density 3, 240,208 tokens, 147 items, 15 probes (every 25 batches, 3 questions each: a
  current value, an overwritten old value, a "who did X" detail), plus 14 final questions. Seed 0.
- Arms (`second-comparison.sh`, budget 16,384, `MAX_TOKENS=8192`): W16 sliding window (drop oldest turns), D16
  compaction (stub old tool output, strip thinking), B16ir improved self-editing read mode (model keeps `name value`
  lines in STATE, 4K thinking cap), B16ira = B16ir + archive-on-drop + `recall` search.
- Campaign script, logs, checks and probe analysis: `experiments/qwen38-27b-b70/data/2026-10-10-context-16k-baseline/`
  (raw trials under `/mnt/fast-ai/bench-results/context-longrun-20261010/`).

## Results

| arm | probes | 1-4 back | 5-24 back | 25-99 back | current | old value | who | final 14 | all 29 | minutes | LM calls | tokens written | peak ctx |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W16 window-drop (lossy) | 10/15 | 8/8 | 2/5 | 0/2 | 5/5 | 2/5 | 3/5 | 14/14 | 24/29 | 22 | 157 | 58,977 | 12,793 |
| D16 compaction (lossy) | 10/15 | 5/8 | 3/5 | 2/2 | 5/5 | 5/5 | 0/5 | 14/14 | 24/29 | 19 | 155 | 38,947 | 9,891 |
| B16ir self-edit read mode | 4/15 | 3/8 | 1/5 | 0/2 | 3/5 | 1/5 | 0/5 | 14/14 | 18/29 | 20 | 360 | 37,284 | 9,366 |
| B16ira + archive and recall | **12/15** | 7/8 | 4/5 | 1/2 | 3/5 | 4/5 | **5/5** | 8/14 (2 stale) | 20/29 | 36 | 466 | 80,290 | 11,648 |

Speed (minutes per 100K tokens of history): W16 8.2 then 10.0; D16 7.3 then 7.6; B16ir 8.8 then 7.6; B16ira 17.7 then
7.2 (its first 100K includes 24 recalls and 3 rollbacks).

## Reading

- **Archive + recall is the only arm that beats the lossy floor on the probes** (12/15 vs 10/15) and it is the only one
  that answers every "who did X" question, because the verbatim text is still there to search. It is also the slowest
  (36 min vs 19-22) and it got the *final* questions wrong (8/14, two stale answers): after recalling old batches it
  wrote stale values back into its state. Searching the past must not be allowed to overwrite the present.
- **The self-editing read mode collapses at 16K** (4/15; it was 23/24 at 1M tokens with a 32K budget last week). With a
  2K batch, the state lines, the instructions and a 4K thinking cap inside 16K there is no working room. So the cap is not
  a free test knob for in-window editors: 16K changes the answer, 32K did not. Fast-scale tests need a cap that leaves
  the method its working room (32K), or a method whose working set is outside the window.
- **The two lossy baselines tie at 10/15 but fail on different things.** Window-drop keeps recent detail and some "who"
  facts; compaction keeps the running state (5/5 old values) and loses every "who" fact, because that detail lives in
  the tool output it stubs. Which lossy method is "better" depends on which probe family you ask.
- **Final questions do not separate methods** (14/14 for three arms): they ask about state that is still in the window.
  Distance-binned probes are the measurement; the charter's benchmark design holds.
- **Speed does not degrade with history** for any arm at this scale (7-10 min per 100K, flat). Prefix cache hit:
  W16 941K of 1.77M prompt tokens cached.

## Next

1. Seed 1 of the same four arms, and the 32K cap for B32ir / B32ira / W32 / D32 on the same stream, so the "16K is too
   small for in-window editing" claim rests on more than one seed. About 2 h each on one card.
2. Fix the archive arm's stale write-back (recall results must be marked as history, never copied into current state
   without a newer-value check) and rerun; that is the first real contender.
3. Add the two probe families the charter calls for and no arm has yet: a constraint stated at the start that must still
   hold at the end, and a procedure learned early that must be reused late.
4. Engine side (with the other host's runtime): the KV park/restore on NVMe measurement, since the archive arm's cost is
   re-reading recalled text at 2K tok/s; paging saved cache would cut that ~25x.
