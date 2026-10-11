# Long-horizon context, fast-scale baseline: 16K and 32K live caps over a 240K history (2026-10-10/11)

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
  (36 min vs 19-22) and it got the *final* questions wrong (8/14, two stale answers). Post-mortem (context snapshots):
  this was budget starvation, not recall write-back. At 16K the harness refused `next` 121 times for lack of room
  and refused the fold 35 times because STATE.txt lacked a line for a counter the items mentioned, so the agent spun
  and old state values stuck. Recall itself (24 calls, 41.9K tokens of output) ate the room that was left.
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
2. Give the archive arm room (32K cap; see round 2) and harden it for small windows as described below; it is the
   first real contender.
3. Add the two probe families the charter calls for and no arm has yet: a constraint stated at the start that must still
   hold at the end, and a procedure learned early that must be reused late.
4. Engine side (with the other host's runtime): the KV park/restore on NVMe measurement, since the archive arm's cost is
   re-reading recalled text at 2K tok/s; paging saved cache would cut that ~25x.

---

## Round 2 (night of 2026-10-10): seed 1 at 16K, and the 32K cap

Two-card server (TP2, window 65,536, same image and overlays as the 10-08 campaign, exact prefix cache, MTP 5), one arm
at a time (host RAM 2.2-2.7 GiB available beside the server). Campaign: `longrun-round2-client.sh`; tables:
`probe-analysis-round2.txt` in the data folder. New arms W32 / P32 are the lossy floors at 32K beside B32ir / B32ira.

| arm | cap | seeds | probes | 1-4 | 5-24 | 25-99 | current | old value | who | final | all | min per run |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W16 window-drop | 16K | 2 | 16/30 | 11/11 | 5/14 | 0/5 | 9/10 | 3/10 | 4/10 | 34/35 | 50/65 | 22 |
| D16 compaction | 16K | 2 | 19/30 | 8/11 | 9/14 | 2/5 | 10/10 | 8/10 | 1/10 | 35/35 | 54/65 | 19-20 |
| B16ir self-edit read | 16K | 2 | 9/30 | 5/11 | 4/14 | 0/5 | 8/10 | 1/10 | 0/10 | 35/35 | 44/65 | 14-20 |
| B16ira + archive/recall | 16K | 1 (+1 void) | 12/15 | 7/8 | 4/5 | 1/2 | 3/5 | 4/5 | 5/5 | 8/14 | 20/29 | 25-36 |
| W32 window-drop | 32K | 1 | 11/15 | 8/8 | 3/5 | 0/2 | 5/5 | 2/5 | 4/5 | 14/14 | 25/29 | 20 |
| P32 compaction | 32K | 1 | 13/15 | 7/8 | 4/5 | 2/2 | 5/5 | 5/5 | 3/5 | **4/14** (6 stale) | 17/29 | 13 |
| B32ir self-edit read | 32K | 1 | 8/15 | 4/8 | 3/5 | 1/2 | 5/5 | 3/5 | 0/5 | 14/14 | 22/29 | 16 |
| **B32ira + archive/recall** | 32K | 1 | **13/15** | 7/8 | 4/5 | 2/2 | 5/5 | 4/5 | 4/5 | **14/14** | **27/29** | **15** |

Cost per run (tokens written / LM calls / peak live context): B32ira 37.6K / 360 / 27.2K with 20 recalls and 1
rollback; W32 74.0K / 159 / 27.9K; P32 51.9K / 157 / 21.1K; B32ir 55.2K / 346 / 23.9K. Speed stayed flat for every arm
(4-10 min per 100K of history in both halves).

The seed-1 B16ira run is void: it hit the step cap and wrote 24 keys beyond the queried ones into its answer file.
Post-mortem: the same starvation, worse (292 `next` refusals, 151 recalls, 4,405 refused steps of 628); at the end it
answered every counter it had rather than the ones asked. The harness already notes extra keys on write (clm_improved
answers guard) but does not refuse them; a refusal would only add another refused step under starvation. The cure is
room, i.e. the 32K cap, where neither failure appeared.

### Reading, after two rounds

- **Archive + recall at 32K is the first method clearly above the lossy floor on every axis at once**: best probes
  (13/15), perfect finals, best total (27/29), and the fastest or second-fastest run (15 min), with the fewest tokens
  written of the 32K arms. At 16K the same method had no room: stale write-back on seed 0 and a runaway on seed 1. The
  working room is the difference, not the method. 32K is the fast-scale cap to use from here.
- **Compaction (keep old state visible, stub tool output) is a trap**: good probes, then 4/14 finals with six stale
  values at 32K. It keeps what *was* true in view and the model reports it as current. This is the stale-fact failure
  the charter lists, now measured on our own task.
- **Window-drop is honest but forgets**: 0/5 and 0/2 at 25-99 batches back in every run.
- **Self-editing without an archive (B*ir) is below the lossy floors at both caps** on this task. Its `name value`
  state keeps current values but throws away the "who" detail by design (0/15 across all runs), and at 16K it loses
  even current values.
- Two seeds agree on the 16K ranking (D16 > W16 > B16ir). The 32K ranking is one seed; seed 1 at 32K is the next run.

### Next

1. Seed 1 at 32K for W32 / P32 / B32ir / B32ira (about 1 h on two cards).
2. Harden the archive arm for small windows: cap recall output per call relative to the budget, and when `next` is
   refused for room twice in a row, tell the model the one action that frees room (drop the oldest folded batch)
   instead of refusing again; a step budget that degrades to "answer what you have" instead of a cap void.
3. Add the constraint-adherence and procedure-reuse probe families.
4. Engine lever: measure KV park/restore on NVMe for recalled batches (the archive arm's remaining cost is re-reading
   recalled text through prefill).

---

## Round 3 (2026-10-11 02:06-03:15): seed 1 at 32K, three of four arms

Same two-card server recipe. W32, P32 and B32ir finished on seed 1; the server was then stopped by the host memory
guard before the archive arm (B32ira) started, so round 3 has no B32ira row and round 4 did not run.

| arm (32K, seed 1) | probes | finals | all 36 | minutes |
| --- | ---: | ---: | ---: | ---: |
| W32 window-drop | 10/15 | 21/21 (4 blank probes) | 31 | 30 |
| P32 compaction | 10/15 | 21/21 | 31 | 23 |
| B32ir self-edit read | 8/15 | 21/21 | 29 | 15 |

One correction to the round-2 reading: **P32's stale finals did not repeat.** Seed 0 gave 4/14 finals with six stale
values; seed 1 gave 21/21. "Compaction reports stale values as current" is a one-seed observation until a third seed
or a look at the seed-0 transcript says why. Pooled tables: `probe-analysis-round3.txt` in the data folder.

**Why the server stopped (not a GPU fault).** The launcher's memory guard has a 2.0 GiB default floor and an
owner-approved research floor of 1.6 GiB (2026-10-06, `B70_GUARD_MIN_AVAILABLE_GIB`). Rounds 2 and 3 were launched
without that setting. With the server (about 9 GiB) and one client (harness process 0.3 GiB, compose and docker about
0.15 GiB) the host had 2.06-2.25 GiB available all hour; the per-arm summary step (0.11 GiB for one second) took it to
1.95 GiB at 03:15:24 and the guard killed the container. No fault line in the kernel log; Gemma reloaded on both cards
at 03:18 and served. Measured on 2026-10-11 with a stub run: the client costs about 0.45 GiB of host memory in total.
Rule for this lane: every research launch passes `B70_GUARD_MIN_AVAILABLE_GIB=1.6`, tasks are generated before the
server starts, and nothing else runs on the host while a two-card server is up.

## Campaign 4 (2026-10-11 03:27, preregistered before any result)

One unattended runner, `longrun-campaign4.sh` in the data folder: stops the Gemma LAN service, starts the round-2/3
server once with the 1.6 GiB floor, runs the stages one arm at a time, stops the server, analyses, puts Gemma back
(not if a GPU fault line appears). No restart if the server dies.

| stage | what | why |
| --- | --- | --- |
| S1 | B32ira, seed 1, plain 240K stream | the row round 3 lost; the 32K recommendation rests on one seed |
| S2 | B32ira, W32, P32, B32ir, seed 0, `--rules` stream | charter axes 4 and 5: a standing rule in item 1 (three confidential counters, answer `protected`) and a house method in item 2 (tally = value x 5 + 13), each asked at 25, 51, 77, 103 and 129 items back, plus one confidential counter in the final query |
| S3 | C32 (summarise at 75 %), seed 0, plain stream, cut at 100 min | the production-style method is missing from the 32K table |

How the results will be read (fixed now):
- S1 confirms the round-2 claim if B32ira's seed-1 probes are above both lossy floors on that seed (10/15 each) and
  its finals are 21/21. Equal probes or any lost final makes the claim "ahead on one seed, level on the other".
- S2: an arm "keeps the rule" if every rule probe and the confidential final are answered `protected`; "keeps the
  method" if every tally is exact. A wrong tally with the right current value is a method loss; with a wrong current
  value it is a state loss and is counted separately. Rule and method are 25+ items back at every probe, so
  window-drop is expected to lose both once item 1 leaves the window; the question is whether the editing and archive
  arms carry them, since nothing tells them a rule is more important than a counter.
- S3: C32 is compared with B32ira on the same seed for accuracy and minutes; a run cut at 100 min is "did not finish".

## Campaign 4 results (2026-10-11 03:27-05:28)

Ran S1 and S2; S3 (C32) was moved to campaign 5 so the rule fix and the 1M run come first. Host memory beside the
server never went below 2.10 GiB with the 1.6 GiB floor (round 3 died at 1.95 under the 2.0 default). No GPU fault
line; server stopped idle; Gemma put back. Evidence: [`../data/2026-10-11-context-campaign4/`](../data/2026-10-11-context-campaign4/).

### S1: the archive arm's second seed at 32K

B32ira, seed 1: **36/36** (15/15 probes, 21/21 finals) in 16 minutes, against 31/36 for both lossy floors on the same
seed (30 and 23 minutes). The preregistered bar (above both floors on probes, 21/21 finals) is met.

Plain 240K stream, 32K cap, two seeds pooled:

| arm | probes | 1-4 | 5-24 | 25-99 | current | old value | who | final | all 65 | min per run |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **B32ira archive + recall** | **28/30** | 10/11 | 13/14 | 5/5 | 10/10 | 9/10 | 9/10 | 35/35 | **63** | 15-16 |
| W32 window-drop | 21/30 | 11/11 | 10/14 | 0/5 | 10/10 | 4/10 | 7/10 | 35/35 | 56 | 20-30 |
| P32 compaction | 23/30 | 10/11 | 10/14 | 3/5 | 10/10 | 9/10 | 4/10 | 25/35 | 48 | 13-23 |
| B32ir self-edit read | 16/30 | 6/11 | 8/14 | 2/5 | 10/10 | 6/10 | 0/10 | 35/35 | 51 | 15-16 |

Cost per run: B32ira reads 5.3M prompt tokens of which 81-82 % come from the prefix cache (about 1.0M read fresh, four
times the stream) and writes 38-49K; W32 reads 4.0M (70 % cached) and writes about 100K; P32 2.8M (75 %), 52-69K.

### S2: a standing rule and a house method (charter axes 4 and 5), seed 0

Item 1 states a rule (three counters are confidential: answer `protected`), item 2 a method (tally = value x 5 + 13).
Each of five PROBE items asks one question of each kind, 24 to 129 items after they were stated; the final query
includes one confidential counter. 39 questions per run.

| arm | current | old value | who | **rule** | **method** | final (confidential one) | all 39 | minutes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B32ira archive + recall | 5/5 | 5/5 | 5/5 | **0/5** | 5/5 | 13/14 (blank) | 33 | 20 |
| W32 window-drop | 5/5 | 3/5 | 2/5 | **0/5** | 0/5 | 13/14 (blank) | 23 | 26 |
| P32 compaction | 3/5 | 3/5 | 0/5 | **0/5** | 3/5 | 11/14 (blank) | 20 | 14 |
| B32ir self-edit read | 3/5 | 3/5 | 0/5 | **0/5** | 0/5 | 12/14 (wrong) | 18 | 33 |

**No method kept the rule. Not one rule question was answered `protected` in any run, at any distance, and the
confidential counter in the final query was left blank by all of them.** By the preregistered reading every arm "lost
the rule"; only the archive arm "kept the method". B32ir also had a bad run on this stream (694 model calls against its usual
336; its context sat at the 75 % nudge with edits that matched nothing), which is why it took 33 minutes.

Why, for the archive arm (transcript checked): the model noticed the rule (its thinking at item 1 reads "Standing rule
... confidential -> answer protected") and then had nowhere to put it. STATE.txt accepts only `name value` lines,
earlier thinking is dropped by design, and item 1 goes to the archive. It never tried to write the rule into the state
(the 44 rejected state edits are all other things). A question about a confidential counter looks like any value
question, so nothing prompts a search; it answered `null`. The method survived because its questions name it ("using
the house method"), which sends the model to `recall`. Window-drop simply no longer had items 1-2 by the first probe
(a 32K window holds about 15 items).

This is the charter's "cheapest and most damning test" doing its job: the method that is best on recall (63/65) fails
adherence completely, for a reason that is about where instructions live, not about memory capacity. The fix to test
is a pinned place for rules: campaign 5, arms B32iraR (permanent `RULE:` lines) and B32ira-free (free-text notes).

Speed on the rules stream (minutes per 100K of history, first and second 100K): B32ira 8.5 / 7.9, W32 7.9 / 12.6,
P32 6.7 / 4.5. B32ira made 20 recalls (12.7K tokens of output) and 424 calls; W32 34 truncations; P32 54 compactions.

## Campaign 5 (2026-10-11, preregistered before any result)

Runner: `longrun-campaign5.sh` in `/mnt/fast-ai/bench-results/context-longrun-20261011/`. One two-card server
(the same recipe at `--max-model-len 262144`, guard floor 1.6 GiB), started once; stopped only when no request is
running; Gemma stopped first and put back at the end.

**Why.** Campaign 4 showed the archive arm loses a standing rule (see above), and the 32K result has not been
tried at the owner's numbers. Campaign 4's S3 (C32) was moved here so the rule fix and the 1M run come first.

| phase | arm(s) | stream | question |
| --- | --- | --- | --- |
| 1 | B32iraR, B32ira-free | rules, 240K, seed 0 (campaign 4's task) | does a pinned place for rules bring the rule back without costing anything else? |
| 1 | B32iraR4 | the same | speed lever: four items fetched and folded per command instead of one; does accuracy hold with a quarter of the calls? |
| 2 | the better of phase 1 (B32ira if neither beats its 33/39) | rules, 1M, seed 0, probes every 20 batches x (5 + rule + method), 32K live budget | does the method stay accurate and as fast per 100K at 31x its live budget, with questions up to 400+ items back? |
| 2 | B32iraR4, only if it lost at most one question to B32iraR in phase 1 | the same 1M stream | the fast variant at the owner's scale |
| 3 | C32, cut at 80 min | plain, 240K, seed 0 | the production-style summary method in the 32K table |
| 4 | W200, cut at 90 min | the 1M stream | the plain alternative at the owner's cap: fill a 200K window, drop the oldest |

New arms (both leave B32ira's counter lines, guards, archive and `recall` unchanged):
- **B32iraR** (`clm_rules.py`): STATE.txt may also hold up to 12 permanent `RULE: ...` lines of at most 400
  characters; an edit that removes or rewords one is rejected; the protocol says to add a rule or method when an item
  states one and to read the RULE lines before answering.
- **B32ira-free** (`clm_freenotes.py`, built 10-07 for LongMemEval, never run on this stream): free-text notes up to
  6,144 tokens instead of counter lines. Its protocol is unchanged, so it says nothing about rules; this is the test
  of whether free notes carry a rule without being told to.

How the results will be read (fixed now):
- B32iraR4 is a speed lever only if it is within one question of B32iraR at 240K; its gain is the ratio of minutes
  per 100K. One call then carries four reports, so a mistake costs more; more than one question lost closes it at 4
  (2 would be the next size to try).
- Phase 1: an arm "fixes the rule" at 5/5 rule probes plus the confidential final; it "costs nothing" if the other
  34 questions stay within one of B32ira's 33/34. The arm with more questions right goes to 1M; B32iraR on a tie.
- Phase 2: "flat" means the far bins (100-399 and 400+ items back) are within two questions of the near bins per
  ten asked, and minutes per 100K in the last 200K are within 25 % of the first 200K. Rule and method are judged as
  in phase 1. One seed: a result, not yet a replication.
- Phase 4: W200 is expected to be right inside its window and wrong beyond it, and to decode two to three times
  slower once the window is full (41 tok/s at 137K, 26 at 246K, measured 10-05). If it is cut, the probes it reached
  are graded from the last copy of its answers file (`partial_grade.py`) and reported as a cut run.
- Phase 3: C32 against B32ira on the same seed, accuracy and minutes; a cut run is "did not finish in 80 min".
