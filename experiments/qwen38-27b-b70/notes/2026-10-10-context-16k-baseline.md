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

## Campaign 5, phase 1 (2026-10-11 05:41-06:34): a pinned place for rules

Rules stream, 240K, seed 0, 32K live budget, server window 262,144. Same 39 questions as campaign 4's S2.

| arm | current | old value | who | **rule** | **method** | final (confidential one) | all 39 | minutes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B32ira (campaign 4) | 5/5 | 5/5 | 5/5 | 0/5 | 5/5 | 13/14 (blank) | 33 | 20 |
| **B32iraR** permanent `RULE:` lines | 4/5 | 4/5 | 5/5 | **5/5** | 4/5 | 13/14 (**right**) | **35** | 18 |
| B32ira-free free-text notes | 3/5 | 5/5 | 4/5 | 4/5 | 3/5 | 9/14 (blank) | 28 | 23 |
| B32iraR4 four items per command | stopped after 10 min at item 21 | | | | | | | |

Read against the preregistered rules:

- **B32iraR fixes the rule**: all five rule questions and the confidential counter in the final query. By item 11 its
  state held two `RULE:` lines, the rule and the house method, in its own complete wording. No RULE edit was ever
  rejected.
- **It did not come free**: on the other 33 questions it scored 29 against B32ira's 33 (the bar was "within one").
  The four misses are bookkeeping: one current value, one tally computed from a wrong value, one old value, one
  stale final. Looking at the transcripts, the two runs settled on different ways of writing an update. B32ira's
  script upserts and lets Python do the sums (`setv(s, "hike77", 383+6)`); B32iraR's rewrites matching lines with
  values worked out in the reply (`out.append("roke54 268")`), and has no upsert (12 edits rejected for a vanished
  line against 0). One seed, so this may be chance, but the mechanism is plausible: a state file with mixed
  content invites line-by-line rewriting. The cleaner design keeps rules where the model never rewrites them.
- **Free-text notes carry a rule without being told to, but not reliably, and they keep books badly.** B32ira-free
  wrote both the rule and the method into its notes at items 1-2 unprompted and answered 4/5 rule questions; on the
  first it answered `null` (the counter had been removed) although the rule was in view, and it left the
  confidential final blank. Its notes are a per-item log, not a table: 9/14 finals. A place to keep a rule is
  necessary but not sufficient; B32iraR's line "read the RULE lines before you answer" is what made it 5/5.
- **Four items per command is not a speed lever at 32K.** The room check then wants 12.2K free (4 x 2.0K + 4.1K
  headroom); the context sat near 25K with about 200 small turns, `next` was refused, and the run needed 115 calls
  for 21 items. Stopped by hand (SIGINT to the client; the server was idle before the next arm, kernel log clean).
  Closed at 4 for this budget. The lever needs either a larger live budget or the harness clearing the agent's own
  command turns, which is the keeper arm's design (`clm_keeper.py`, not yet run).

B32iraR (35) went to the 1M stream at 06:34.

## Campaign 5, phase 2 (2026-10-11 06:34-08:12): one million tokens through a 32K live budget

B32iraR on the 1M rules stream (999,460 tokens, 617 items, seed 0; 29 PROBE items of seven questions; 25 final
counters), server window 262,144, live budget 32K. Evidence:
[`../data/2026-10-11-context-campaign5/`](../data/2026-10-11-context-campaign5/).

**This is a stopped run, reported as one.** The agent read all 617 items and answered 28 of the 29 PROBE items as
they arrived. At the final item it rewrote `/app/answers.json` with the 25 final counters only, which wiped its 196
probe answers; the harness told it keys were missing and it began to re-derive them from the archive one question
at a time (a question about "now" would then be answered with the value at the end). I stopped the client at 08:12.
The verifier never ran, so there is no official score and no storage-rule verdict. What is reported:

- probe answers **as the agent wrote them during the run**, rebuilt from the 30 write commands in its saved context
  snapshots by `replay_answers.py` (literal values only, nothing executed; the two "unread" notices are comments);
  the same counts came from a live copy of the file at 08:01, through probe 28: 157/196;
- final answers as they stood in the file when the run was stopped.

| | right / asked |
| --- | ---: |
| all probe questions | **163 / 203 (80 %)** (one PROBE item, the 14th, was never answered: 7 blanks) |
| by distance: 1-4 / 5-24 / 25-99 / 100-399 / 400+ items back | 45/50, 40/50, 23/30, 35/48, **20/25** |
| by type: current / who / house method / standing rule / old value | 54/58, 25/29, 25/29, 22/29, **37/58** |
| by third of the run (probe items 1-10 / 11-20 / 21-29) | 56/70, 52/70, **55/63** |
| final query | 24 / 25 (the confidential counter was answered `null`) |

Cost: 87 minutes for the stream, **8.7 minutes per 100K on average and no slower at the end** (per 100K: 5.2, 11.5,
8.3, 8.0, 12.0, 8.5, 8.6, 5.4, 5.4). 2,170 model calls (3.5 per item), 289K tokens written, 30.6M prompt tokens of
which 82 % came from the prefix cache (5.5M read fresh, 5.5 times the stream), 470 recalls returning 148K tokens,
191 rejected state edits. Live context stayed under 30.7K throughout.

Read against the preregistered rules:

- **Flat with distance: yes, narrowly.** Per ten asked, the near bins are 9.0 and 8.0; 100-399 back is 7.3 and
  400+ back is 8.0, within the two-question margin. Accuracy did not fall as the history grew: the last third of
  the run was the best.
- **Speed flat: yes.** The last 200K took 10.8 minutes, the first 200K 16.7.
- **Rule and method: kept, not perfectly.** 22/29 and 25/29. The rule line was pinned the whole time, yet six rule
  questions were answered with a number or `removed` and the final confidential counter with `null`; five of the
  six lapses are in the last ten PROBE items. A pinned rule decays in use even when it never leaves view.
- **Old values are the weak spot**: 37/58. The model has to replay every archived sentence about a counter up to
  item N. Everything else is at 76-93 %.

Three defects this run exposed, each with a fix to test:

1. **The answers file can be wiped by the final write.** The task text says to keep earlier keys; at 240K the model
   did, at 1M it did not. The runner now needs snapshots that are kept, not overwritten (the copy that would have
   saved this was replaced two minutes later), and the harness should refuse a write that drops answered keys.
2. **With thinking off the model often issues a made-up second update right after a fold** (the harness rejects it:
   that is most of the 191 rejections). About one wasted call per item; saying "now run `next`" in the fold's reply
   is the cheap thing to try.
3. **"What was true at item N" needs a history, not a replay**: arm B32iraRH keeps every accepted version of the
   pinned state and answers `recall --state-at N` (`clm_history.py`, campaign 6).

And one for the rule: a reminder at the moment of use. The keeper arm appends the RULES lines right after any item
that asks questions.

## Campaign 6 (2026-10-11, preregistered before any result)

Runner: `longrun-campaign6.sh` beside campaign 5's. Same server recipe (window 262,144, guard floor 1.6 GiB), started
once. C32 and W200 were taken out of campaign 5 after its 1M arm started, so that the keeper arm could be tested as
soon as the cards were free; both run here.

**The keeper arm (`clm_keeper.py`).** Every method so far that beats the lossy floors asks the model to run a
protocol: fold each item into a state file, then drop it. That is two or more model calls per item, it is specific
to this stream, and it is what a real agent will not do. The keeper asks nothing of the agent. It is the plain
sliding-window agent (W32); when the context goes over the limit the harness, before cutting the oldest turns down
to 75 %, (1) writes every delivered item in those turns verbatim to the archive, (2) asks the model once, with no
tools, to rewrite a NOTES block (RULES / STATE / OPEN) from the old notes and the turns being cut, and puts back any
RULES line the model dropped, (3) replaces the cut turns with one pinned NOTES message after the task statement. The
system prompt gains a Memory section: read RULES before answering, use `recall` for anything out of view. This is the
policy a serving-side proxy could apply to any tool-calling agent.

| stage | arm(s) | stream | question |
| --- | --- | --- | --- |
| 1 | N32 | rules, 240K, seed 0 | does the keeper lift the sliding window (W32 23/39: rule 0/5, method 0/5, who 2/5) toward the protocol arms (B32iraR 35, B32ira 33) with no per-item protocol? |
| 1 | N32j | the same | N32 thinking only when a question, refusal or error is in view (the notes call thinks instead): how much faster, at what cost? |
| 1b | B32iraRH, cut at 60 min | rules, 1M, seed 0 | B32iraR's weak spot at 1M was "what did X hold at the end of item N" (about half right, against nine in ten on everything else). Does a version history of its own pinned state (`recall --state-at N`) fix that? Own rule class: archive plus state history |
| 2 | C32, cut at 80 min | plain, 240K, seed 0 | the production-style summary method in the 32K table |
| 3 | B32iraR, B32ira, the better keeper | rules, 240K, seed 1 (new stream) | second seed for "no rule without a pinned place", for the bookkeeping cost of RULE lines, and for the keeper |
| 4 | the better keeper, only if it scored at least 33/39 in stage 1, cut at 100 min | rules, 1M, seed 0 | the general method at the owner's scale |
| 4 | W200, cut at 90 min | the same 1M stream | the plain alternative at the owner's cap |

How the results will be read (fixed now):
- N32 "works" if it is at least 6 questions above W32 (29/39 or more) with rule and method each at 4/5 or better;
  it "matches the protocol arms" at 33/39 or more. Its minutes are compared with W32 (26) and B32iraR (18).
- N32j is the better keeper if it is not below N32 in questions right (a tie goes to the quicker one). If it loses
  more than two questions to N32, thinking-off costs bookkeeping and N32 stays the keeper.
- Stage 1b: compared with B32iraR on the probe items both reached. The history "fixes old values" at 80 % or more of
  those questions with the other types unchanged (within two questions). It is a cut run by design and is reported
  as one; its results are never pooled with the archive-only arms.
- Stage 3: the rule result replicates if B32ira is at most 1/5 and B32iraR at least 4/5 on rule questions; the
  bookkeeping cost of RULE lines replicates if B32iraR is again more than one below B32ira on the other questions.
- Stage 4 as campaign 5: accuracy by distance, minutes per 100K by segment; a cut run is reported as cut.
- Known risk, stated now: the keeper's STATE is rewritten by a model call without tools, so sums are done in the
  model's head; N32 leans on the agent's own running table (W32's final answers were 35/35), N32j cannot.
- Added after the 1M run and before any keeper result: the keeper appends the RULES lines as a reminder after every
  item that asks questions (`recite_rules`, on in N32 and N32j). So stage 1 tests pinned notes and recitation
  together; if it works, a run without recitation is the ablation.

## Campaign 6, stage 1 (2026-10-11 08:39-09:01): the keeper

Campaign 6 ran its first stage and was then stopped, so that the keeper's second seed and its 1M run would not wait
behind three hours of other arms (campaign 7 has the rest, keeper first). No GPU fault line; server stopped idle.

**N32, first attempt: stopped after two minutes, a prompt defect.** The notes request gave the instruction first and
then about 8K tokens of the agent's own turns. The model read its own turns last and wrote one more of them (a
running state, no RULES section), so the rule of item 1 was gone after the first cut. Fixed before the next arm:
the instruction now comes after the turns, the reply must have the RULES / STATE layout or it is asked for once
more, text before the RULES heading is dropped, and RULES is for rules the stream states, not the task statement.
A Codex read-only review before the run had also found six defects in the two new arms and two in the runner
(an item fetched by a chained command could have made an archive file non-verbatim and voided a run; archive writes
were not confirmed; snapshots of different seeds shared a name); all fixed before any keeper result.

**N32j: 39 of 39.** Rules stream, 240K, seed 0, 32K live budget; the same task as campaigns 4 and 5.

| arm | current | old value | who | rule | method | final | all 39 | minutes | model calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **N32j keeper** | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 14/14 | **39** | **15** | **197** |
| B32iraR pinned RULE lines | 4/5 | 4/5 | 5/5 | 5/5 | 4/5 | 13/14 | 35 | 18 | 400 |
| B32ira archive + recall | 5/5 | 5/5 | 5/5 | 0/5 | 5/5 | 13/14 | 33 | 20 | 424 |
| W32 window-drop | 5/5 | 3/5 | 2/5 | 0/5 | 0/5 | 13/14 | 23 | 26 | 162 |

Not void; 138 items archived, all 138 verbatim. Against the preregistered bars: it "works" (needed 29 with rule and
method at 4/5) and "matches the protocol arms" (needed 33). It is the first perfect score on this task.

What it did: 174 main-loop calls, 167 of them without thinking (9.5K tokens written in the main loop), plus 23 notes
calls, one per cut of six items (about 12.3K prompt tokens and 1.9K written each, thinking on). NOTES stayed between
450 and 860 tokens: two RULES lines in the stream's own words from the first cut to the end, never dropped by the
model, and a state table of 48 lines. The rules were recited at each of the six question items. Time splits about
evenly: 7 minutes in the main loop, about 8 in the notes calls. That is the next speed lever (arm N32f: a notes call
that does not think, and a deeper cut).

Why this matters beyond the score: nothing in this arm asks the agent to do anything. The agent runs `next` and
answers questions; the harness archives, takes notes and reminds. That is what a serving-side proxy can do for any
tool-calling agent. One seed, one stream of 240K: campaign 7 runs seed 1 and the 1M stream next.

## Campaign 7 (2026-10-11 09:08, preregistered before any result)

Runner `longrun-campaign7.sh`, same server recipe. Order: N32j on the rules stream seed 1; N32j on the 1M stream
(cut at 130 min); N32f on seed 0; B32iraRH on the 1M stream (cut at 60 min); C32 (cut at 80 min); B32iraR and
B32ira on seed 1; W200 on the 1M stream (cut at 90 min). The reading rules of campaign 6 stand, with these additions:

- Seed 1 replicates the keeper result at 35/39 or more with rule and method each at 4/5 or better.
- At 1M the keeper is compared with B32iraR's stopped run on the same stream: probes by distance and by type,
  minutes per 100K, and whether NOTES stays under its 2,048-token cap. "As good at scale" is within 3 points of
  B32iraR's 80 % overall with the rule at 90 % or better; old values are reported separately (B32iraR 64 %).
- One change to the arm since its 39/39, made before any campaign 7 result: answers already in `/app/answers.json`
  are put back by the harness if a later write drops them (the defect that cost B32iraR its 1M score). It changes
  nothing unless a write drops keys; the count is recorded.
- N32f is the fast setting if it is within one question of N32j at 240K; its gain is the ratio of minutes.

## Campaign 7 results (2026-10-11 09:08-10:55): the keeper on a second seed, at 1M, and a faster setting

Three arms ran; the campaign was then stopped so that the proxy could be tested next (campaign 8 carries C32, W200
and the seed-1 protocol arms; B32iraRH is dropped for now, see below). No GPU fault line.

**Second seed: 46 of 46.** N32j on the rules stream, 240K, seed 1 (a different rule, method and day book): every
probe, every final, the confidential counter, in 16 minutes with 188 model calls; not void, 137 items archived, all
verbatim. With seed 0 that is 85 of 85. The replication bar (35/39-equivalent with rule and method at 4/5) is met.

**One million tokens: 114 of 126 (90 %) through item 378, then a loop; a stopped run.** N32j on the 1M stream:

| through PROBE item 18 (item 378 of 617) | N32j keeper | B32iraR at the same point |
| --- | ---: | ---: |
| all probes | **114 / 126 (90 %)** | 97 / 126 (77 %; its 14th item unanswered) |
| current / old value / who / rule / method | 33/36, 29/36, 17/18, 18/18, 17/18 | 32/36, 18/36, 17/18, 16/18, 14/18 |
| 1-4 / 5-24 / 25-99 / 100-399 items back | 32/36, 34/35, 14/18, 34/37 | |
| minutes per 100K of history | about 7.3 (399 items in about 47 min) | 8.7 |

At item 399 (the 19th PROBE item) the agent issued `recall "p13_3"` and then the same command 790 times, each with
the same one-line result, for 22 minutes, until I stopped the client. Cause, from the transcript: the judgement
policy turned thinking on for the call that received the PROBE item and off again for the calls that followed it,
so the work on a probe (searches, the answer write) ran without thinking, and greedy decoding fell into repeating
one call. The older protocol arms have a repeat guard for exactly this; the keeper did not. Two fixes, both in
`clm_keeper.py` and in the proxy before any further run:

- an identical command is not run twice in a row (except a fetch); the refusal says so and turns thinking on;
- thinking stays on for as long as a question is open: from a question item until the next ordinary item arrives.

NOTES stayed between 388 and 1,381 tokens over 77 cuts, with both rules in place throughout (0 put back, 19
recitals); the rule was answered 18 of 18 times, where the pinned-rule protocol arm had begun to slip. The run is
repeated with the fixes in campaign 8.

**N32f, the faster setting: closed.** A notes call that does not think and a cut down to 50 %: 37/39 in 12 minutes
against N32j's 39/39 in 15. Two questions lost (one current value, one final) for a fifth of the time, and the bar
was "within one". The thinking in the notes call is what keeps the books; N32j stays the setting.

**B32iraRH is not run.** It was the fix for B32iraR's weak old-value answers at 1M. The keeper already answers
those better without it (29/36 against 18/36), and the proxy now keeps every NOTES version for the same
purpose (`recall` with `notes_at`). The arm stays in the tree, unit-tested and wire-tested.

## Campaign 8 (2026-10-11, preregistered before any result): the keeper as a proxy

Runner `longrun-campaign8.sh`. Arm **X32** is the plain agent with no context budget of its own (it sends its whole
history, as arm A does) talking to `tools/ctxkeeper`, which keeps a 32K live window in front of the model server.
Nothing in the harness manages context for this arm; the archive and the notes live in the proxy's state directory
on the host, not in the task sandbox. It is the first run of the proxy against the real server.

Proxy settings, chosen to mirror N32j: window 32,768 with 2,048 kept for the reply, cut down to 60 %, a notes call
that thinks, thinking on only when the newest message is a question, a refusal or an error (`--think-when`, with
`--effort medium`), the RULES repeated when a tool result asks questions (`--recite-when`), fresh state per run.
What differs from N32j by construction: `recall` is a tool the proxy answers (not a shell command), the archive
holds whole messages (not items), the proxy adds a Memory paragraph to the system message, and there is no answers
guard (that lives in the harness).

| stage | arm | stream | question |
| --- | --- | --- | --- |
| 1, 2 | X32 | rules 240K, seeds 0 and 1 | does the policy survive being moved out of the harness into a proxy any client can use? (N32j 39/39 and 46/46) |
| 3 | C32, cut at 80 min | plain 240K, seed 0 | the production-style summary baseline |
| 4 | X32, cut at 130 min, only if seed 0 scored 33 or more | rules 1M | the proxy at the owner's scale |
| 5 | W200, cut at 90 min | rules 1M | the plain alternative at the owner's cap |
| 6 | B32iraR, B32ira | rules 240K, seed 1 | second seed for the rule result and the cost of RULE lines |

How the results will be read (fixed now):
- X32 "carries the policy" at 35/39 or more on seed 0 and 41/46 or more on seed 1, with rule and method each at
  4/5 or better, and not void. Between 29 and 34 it works but loses something in the move; the transcript says what.
- The system prompt of the plain agent forbids tools other than `bash`; if the model therefore never calls `recall`
  (proxy counter 0), far "who" and old-value questions will fail for that reason, and the fix is in the proxy's
  wording, not in the policy.
- Minutes are compared with N32j (15-16); the agent's own full-history bookkeeping in the harness is extra cost that
  a real client would not have.
- Added before launch: between X32's two seeds and C32 the runner repeats **N32j on the 1M stream** (cut at 130 min)
  with the repeat guard and thinking kept on while a question is open. It is read like the first attempt: probes by
  distance and type against B32iraR, minutes per 100K, NOTES size, and whether it reaches the final item this time.
  The proxy has the same two protections (`--think-until`, `--repeat-limit`).

## Campaign 8 results (2026-10-11 10:56-): the keeper as a proxy

**X32, seed 0: 37 of 39, first run of `tools/ctxkeeper` against the real server.** The plain agent sent its whole
history on every call (154 calls); the proxy kept the live window at 32K.

| arm | current | old value | who | rule | method | final | all 39 | minutes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **X32 proxy** | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 | 13/14 | **37** | 21 |
| N32j harness keeper | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 14/14 | 39 | 15 |
| B32iraR | 4/5 | 4/5 | 5/5 | 5/5 | 4/5 | 13/14 | 35 | 18 |
| W32 | 5/5 | 3/5 | 2/5 | 0/5 | 0/5 | 13/14 | 23 | 26 |

Not void; nothing was written in the sandbox (the archive is in the proxy's state directory). Proxy counters: 22
cuts, 276 messages archived, 12 `recall` calls answered without the client seeing them, 0 failed notes calls, 0
rules put back, 4.2 characters per token learned from the server's usage numbers; 25 MiB of host memory. The
preregistered bar for "carries the policy" (35 with rule and method at 4/5, not void) is met. The model did call
`recall` although the agent's system prompt names `bash` as the only tool. The two misses are one counter: a
current value three items back at the last probe, and that counter in the final query. Slower than the harness
keeper (21 against 15 minutes): thinking now stays on while a question is open, and each `recall` is one more
round trip inside a client call.

**X32, seed 1: 42 of 46, not void, but 47 minutes and a defect.** Rule 5/5, method 5/5, old value 5/5, current 4/5,
who 3/5, finals 20/21. The bar for "carries the policy" on this seed (41 with rule and method at 4/5) is met, the
speed is not acceptable, and the cause is the proxy's, not the policy's: 10 of its 24 notes calls were rejected, all
of them after the 14th cut. The proxy's notes call did not send the reasoning effort the other calls use, so it
thought at the template's full effort inside a 4,096-token cap; once one reply came back empty or cut, the notes
were a cut behind, the next call had more to reconcile, and every later one failed too. With stale notes the model
stopped trusting its state and checked the final answers one counter at a time through `recall` (68 searches); the
proxy allowed six per turn and then handed the seventh `recall` call to the client, which does not know that tool.
Fixed in `tools/ctxkeeper` after this run, each with a test: the notes call sends the same effort and has 8,192
tokens; a rejected notes reply is logged with its reason and asked for again without thinking; when a turn's
searches are used up the model is asked once more without the tool and the client never receives a `recall` call.
Seed 0 had none of this (22 cuts, 22 notes, 12 searches, 21 minutes). The proxy's numbers so far are therefore
37/39 and 42/46 with a known defect in the second; it is rerun after the fixes.

**N32j on the 1M stream, second attempt: 226 of 228, a finished and verified run.** With the repeat guard and
thinking kept on while a question is open; 12:08-13:32. Evidence:
[`../data/2026-10-11-context-keeper/`](../data/2026-10-11-context-keeper/).

| 999,460 tokens, 617 items, 32K live budget | N32j keeper (official grade) | B32iraR (stopped run, rebuilt answers) |
| --- | ---: | ---: |
| all 228 questions | **226 (99.1 %)**, not void | 187 (probes 163/203, finals 24/25) |
| probes | **201 / 203** | 163 / 203 |
| current / old value / who / rule / method | 58/58, 58/58, 27/29, 29/29, 29/29 | 54/58, 37/58, 25/29, 22/29, 25/29 |
| 1-4 / 5-24 / 25-99 / 100-399 / 400+ items back | 49/50, 49/50, 30/30, 48/48, **25/25** | 45/50, 40/50, 23/30, 35/48, 20/25 |
| first / middle / last third of the run | 68/70, 70/70, 63/63 | 56/70, 52/70, 55/63 |
| final query | 25 / 25, confidential one right | 24 / 25 |
| minutes | 83 (8.3 per 100K) | 87 (8.7 per 100K) |
| model calls | 865 (755 by the agent, 110 notes calls) | 2,170 |

The storage rule passed: 609 items in the archive, all 609 verbatim copies; nothing else written. The two misses are
"who did it" questions 3 and 5 items back, both in the first third. By segment of 100K the run took 7.7, 7.8,
10.1, 9.4, 6.4, 7.9, 7.9, 8.9 and 8.9 minutes (interpolated from the two-minute answer snapshots): the last 200K
took 15 % longer than the first, inside the preregistered 25 %. NOTES stayed between 388 and 1,031 tokens over 110
cuts; both rules were in it from the first cut to the end and the model never dropped one (0 put back); the rules
were recited 30 times. The agent thought on 168 of its 755 calls and wrote 66K tokens; the notes calls read 1.36M
tokens and wrote 231K. No command was refused as a repeat and no answer had to be put back: the loop of the first
attempt did not recur once thinking stayed on through a probe, and old values went from 29/36 to 36/36 over the same
items.

Against the preregistered reading: flat with distance (every far bin at or above the near bins), flat with history
length (the last third is perfect), speed flat, rule 100 %, "as good at scale" met by 19 points over B32iraR.
One stream, one seed: a result, not yet a replication.

**What the day adds up to.** On this task family the keeper is the best method at every size tested (39/39 and
46/46 at 240K, 226/228 at 1M), the cheapest in model calls, and the only one that asks nothing of the agent. As a
proxy it scored 37/39 and 42/46 before the fixes its second run prompted. Still owed: C32 (running), W200 and the
proxy on the 1M stream, a second seed for the protocol arms and for the keeper at 1M, and the proxy under a real
agent on a real task.

**C32, the production-style summary method: 23 of 29 in 29 minutes.** Summarise at 75 % of a 32K budget, plain 240K
stream, seed 0; it finished well inside its 80-minute cap. Same seed, same stream:

| arm (32K, plain stream, seed 0) | probes | current | old value | who | final | all 29 | minutes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B32ira archive + recall | 13/15 | 5/5 | 4/5 | 4/5 | 14/14 | 27 | 15 |
| W32 window-drop | 11/15 | 5/5 | 2/5 | 4/5 | 14/14 | 25 | 20 |
| **C32 summarise at 75 %** | 10/15 | 4/5 | 4/5 | 2/5 | 13/14 | **23** | **29** |
| P32 compaction | 13/15 | 5/5 | 5/5 | 3/5 | 4/14 | 17 | 13 |

Thirteen summaries, none failed (361K tokens read and 87K written for them, on top of 2.2M read and 40K written by
the agent). It is the slowest arm at this size and below the plain sliding window in questions right: a summary
keeps old values (4/5) and loses the incidental detail nobody knew to keep (who 2/5). Not void. One seed.

Campaign 8 ended here (14:06): server stopped idle, no GPU fault line, host memory never under 1.96 GiB with the
1.6 GiB floor, Gemma put back. Not run: X32 on the 1M stream, W200, the seed-1 protocol arms, and X32 seed 1 again
with the fixed proxy.

## Campaign 9 (2026-10-11 afternoon, preregistered before any result): the proxy after its fixes

Runner `longrun-campaign9.sh`. Arm **X32b** is X32 with `tools/ctxkeeper` as of commit `c16585171`; a new name so that
X32's two runs stay on record beside it. Between the two lie the fixes of campaign 8's second seed (the notes call's
effort, room and retry; the search limit) and nine defects found by a Codex read-only review of the proxy, among them
a history fingerprint that no longer mistakes dropped thinking for a new conversation and a notes reply cut off by
the token cap no longer being accepted.

| stage | arm | stream | question |
| --- | --- | --- | --- |
| 1 | X32b | rules 240K, seed 1 | X32 scored 42/46 in 47 minutes with 10 of 24 notes calls rejected. Are the notes calls accepted now, and does the time come back toward the harness keeper's 16 minutes? |
| 2 | X32b | rules 240K, seed 0 | X32 scored 37/39 in 21 minutes with no rejected notes call. Did the fixes cost anything where nothing was wrong? |
| 3 | X32b, cut at 110 min | rules 1M, seed 0 | the proxy at the owner's scale (harness keeper: 226/228 in 83 minutes) |

How the results will be read (fixed now):
- Stage 1: fixed if no more than one notes call is rejected for good (`notes_failed` in the proxy's counters) and
  the run takes under 30 minutes; the score bar is unchanged (41/46 with rule and method at 4/5, not void).
- Stage 2: no cost if the score is 36/39 or more and the time within five minutes of 21.
- Stage 3: read like the harness keeper's 1M run. "The proxy carries the policy at scale" at 90 % or more of the
  228 questions with the rule at 90 % or better, not void if it finishes; a cut run is graded on the probes it
  reached and reported as cut. The client holds the whole 1M-token history in this arm (a real client would too);
  its memory is watched, since the host has little to spare beside the server.

## Campaign 9 results (2026-10-11 14:22-): the proxy after its fixes

**X32b, seed 1: 44 of 46 in 18 minutes** (X32 before the fixes: 42/46 in 47 minutes; N32j: 46/46 in 16). Current
5/5, old value 5/5, rule 5/5, method 5/5, who 3/5, finals 21/21; not void. Proxy counters: 22 cuts, 22 notes calls
accepted and none rejected (10 rejected before), 18 searches (68 before), 0 rules put back. Both preregistered
conditions for "fixed" are met (no notes call rejected for good, under 30 minutes), and the score bar with them.
The two misses are "who did it" questions, one of them 2 items back.

**X32b, seed 0: 39 of 39 in 17 minutes** (X32 before the fixes: 37/39 in 21). Every probe, every final, the
confidential counter; not void. 22 cuts, 22 notes calls accepted, 7 searches. The fixes cost nothing where nothing
had been wrong, and the run is four minutes quicker.

| the keeper policy, 240K rules streams, 32K live window | seed 0 (39) | seed 1 (46) | both |
| --- | ---: | ---: | ---: |
| in the harness (N32j) | 39 in 15 min | 46 in 16 min | 85 / 85 |
| as the proxy after its fixes (X32b) | 39 in 17 min | 44 in 18 min | 83 / 85 |
| as the proxy before them (X32) | 37 in 21 min | 42 in 47 min | 79 / 85 |

The proxy now carries the policy at about the harness's score and time, with an agent that manages nothing and
sends its whole history on every call.

**X32b on the 1M stream: 222 of 228, a finished and verified run through the proxy.** 15:00-16:36, 95 minutes.

| 999,460 tokens, 617 items, 32K live window | X32b proxy (official grade) | N32j harness keeper (official grade) |
| --- | ---: | ---: |
| all 228 questions | **222 (97.4 %)**, not void | 226 (99.1 %), not void |
| probes | 197 / 203 | 201 / 203 |
| current / old value / who / rule / method | 58/58, 56/58, 28/29, 28/29, 27/29 | 58/58, 58/58, 27/29, 29/29, 29/29 |
| 1-4 / 5-24 / 25-99 / 100-399 / 400+ items back | 49/50, 50/50, 30/30, 44/48, 24/25 | 49/50, 49/50, 30/30, 48/48, 25/25 |
| first / middle / last third of the run | 70/70, 66/70, 61/63 | 68/70, 70/70, 63/63 |
| final query | 25 / 25, confidential one right | 25 / 25 |
| minutes (per 100K) | 95 (9.5) | 83 (8.3) |
| calls by the agent | 657 | 755 (plus 110 notes calls) |

The agent sent its whole history on every call (1,266 messages by the end) and managed nothing; nothing was
written in the sandbox. Proxy counters: 102 cuts, 102 notes versions saved and none rejected, 161 searches (one turn
hit the limit of eight and was answered without the tool), NOTES between 2.4K and 4.9K characters, 4.0 to 4.2
characters per token learned from the server. Per 100K the run took 7.9, 9.6, 12.1, 9.4, 8.4, 9.1, 8.6, 8.9 and
11.7 minutes: no trend. Against the preregistered bar ("carries the policy at scale" at 90 % of the 228 with the
rule at 90 %, not void): met, at 97.4 % with the rule at 28/29. One stream, one seed.

One thing to fix that this run showed: the proxy put a RULES line back 95 times. The model kept copying the task
statement's own rules into RULES and rewording them at each cut; the proxy restored the earlier wording and kept
the rewording too, so the section carried near-copies (the notes stayed small because the model also tidied them).
The proxy now replaces a rewording with the original line (commit `41795b839`, after this run started).

**The memory guard fired once, at the very end, with no harm.** At 16:35:24, after the agent's last model call and
the grader's verdict, the client's end-of-run bookkeeping on a 1,266-message history (final trajectory, 1.7 GB of
per-call snapshots, the summary step) took about 0.8 GiB within seconds; available host memory went from 2.28 to
1.49 GiB and the guard stopped the server container, which was idle. The run's result was already written. No GPU
fault line in the kernel log; Gemma was restored on both cards at 16:40 and both answer. Handled as the standing
rule says for a hard stop: evidence kept (`campaign9-MEMORY-GUARD.json`), cards checked, noted in CURRENT.md.
For the next full-history client at this size: stop the server (idle) before the client's post-processing, or keep
per-call snapshots off for that arm.

| the keeper policy, 32K live window | 240K seed 0 (39) | 240K seed 1 (46) | 1M (228) |
| --- | ---: | ---: | ---: |
| in the harness (N32j) | 39, 15 min | 46, 16 min | 226, 83 min |
| as the proxy (X32b) | 39, 17 min | 44, 18 min | 222, 95 min |
| best protocol arm (B32iraR) | 35, 18 min | not run | 187, stopped run |
| sliding window (W32) | 23, 26 min | not run | not run (W200) |

## Campaign 10 (2026-10-11 evening, preregistered before any result): cheaper notes, and retrieval alone

Two questions. (1) Where did the keeper's 83 minutes at 1M go, and can the cost be cut without losing answers?
(2) The owner asked how the keeper differs from "a RAG that we just add all context to"; I answered from the
archive-and-search arm and said that a retrieval-only arm had not been run. This campaign runs it.

**Measured first, from the 1M run of N32j (no new run).** 4,974 s of agent time: main loop 2,262 s over 755 calls
(617 fetches at a median 1.6 s; 138 other calls, 710 s, of which 101 archive searches 470 s), shell 79 s, and the rest,
2,633 s or 53 %, in the 110 notes calls. The notes calls read 1.36M tokens (12.4K each, about 2 s) and wrote 231K
(2,100 each, about 24 s): about 1,400 tokens of thinking and a rewrite of about 700 to keep a NOTES block of 390 to
1,030 tokens. Re-reading after a cut is small (3 s a cut). So the cost is written tokens in the notes call, not reading.

**Arms** (`clm_keeper.py`, all with the judgement thinking policy of N32j; `second-comparison.sh`):

| arm | what changes against N32j |
| --- | --- |
| N32d | changes-only notes: the notes call writes only the lines that changed (`NEW RULES` / `CHANGES` / `OPEN`), with the working on the line (`name: 120 + 49 = 169`) and no thinking. The harness applies them, checks the working (a wrong sum is corrected; working that starts from a value the NOTES do not hold sends that cut to the full rewrite with thinking) and keeps every line not mentioned |
| N32j35, N32d35 | the cut goes down to 35 % of the window instead of 60 %: about half as many notes calls |
| R32 | retrieval only: no notes, no pinned rules, no search tool. Cut items go to the same verbatim archive; when an item asks questions the harness shows the 20 best-matching archived sentences per question, each with the sentence after it (BM25 over sentences, each indexed with its item number; `rag_retrieve.py`), trimmed weakest-first to the room left in the window |
| N32r | rules-only notes (a no-thinking call that copies new rules, nothing else) + the retrieved sentences + `recall` |
| N32jr, N32dr | N32j / N32d plus the retrieved sentences |

Keyword retrieval is the favourable retriever here: what is asked about is an exact string (a counter name), which
an exact-term index matches better than an embedding model does. An embedding retriever is not tested (no room for
one beside the server on this host).

**What retrieval can reach, measured before any run** (`rag_coverage.py`, no GPU; an upper bound): for each
question, are all the sentences a correct answer needs either still in view or among the 20 retrieved (each shown with
the sentence after it)? Rules stream 240K: 39/39 (seed 0) and 46/46 (seed 1). Hard stream: 50/50, not counting the
second counter that a "went up by as much as Y held" change depends on. 1M stream: 187/228 at 20 per question, 220 at
40, 227 at 80; a probe item there asks 7 questions, so 40 per question is about 12K tokens of retrieved text in a
32K window. So at 240K retrieval is not short of evidence on this stream: counters are reset often (a third of all
changes are sets), so a value needs one or two archived sentences on average, and the rule names its three counters,
so a question about one of them retrieves it. **This contradicts what I told the owner** ("rules never get
retrieved"): that came from the arm where the model decides when to search. Automatic retrieval does fetch a rule
that names what the question names. What the runs add is whether the model then answers correctly, and at what cost.

Two choices were made in the baseline's favour after the review: a match is shown with the sentence that follows it
(the rule says "X, Y and Z are confidential" in one sentence and what to answer in the next; without that the final
query of a confidential counter could not be covered), and items that only ask questions are not stored (with the
earlier questions in the store, coverage at 1M falls from 187 to 111 of 228: old questions share their words with
the new one and crowd the evidence out).

**Streams.** rules: the 240K rule + method stream of campaigns 4 to 9, seeds 0 and 1 (N32j 39/39 in 15 min and 46/46
in 16). hard (new, exploratory): the same with `--pronouns --relative`: every change names its counter in one
sentence and changes it in the next ("Next on the list was X. It went up by as much as Y held at that moment."),
with doublings and thirds; 240K, seed 0. 1m: the 1M stream (N32j 226/228 in 83 min; proxy 222/228 in 95).

**Reading rules, fixed now.**

- N32d (and each other speed lever) is "the faster setting" if on both seeds of the rules stream it is within one
  question of N32j (38/39 and 45/46 or better), with rule and method each at 4/5 or better, and takes at least 25 %
  less time. Fallbacks to the full rewrite, sums corrected and notes-call tokens are reported.
- R32 is reported by question type against N32j on the same seed. "Retrieval alone is enough on this stream" if it is
  within one question of N32j on both seeds; then N32r is the speed candidate and the keeper's notes are judged on
  the hard stream and at 1M, where 20 sentences per question no longer cover (187/228). If R32 is 3 or more short,
  the types it loses say what notes are for.
- The hard stream is exploratory (no bar): N32j is the reference, the fastest passing keeper setting and R32 run
  beside it. Its single-step difficulty is not calibrated, so only differences between arms on the same stream count.
- 1M: the fastest setting that passed on both seeds runs once. "As good at scale" is 222/228 or better (the
  proxy's score) in under 60 minutes.
- One seed per cell beyond the two rules seeds. A difference of one or two questions between arms is not a ranking.

Runner `longrun-campaign10.sh` (queue file, one run per line, lines appended as results come in; server started
once; Gemma stopped first and restored at the end). Before launch: 50 unit tests pass (changes-only parsing and
merging, the working check, BM25, the retrieval message), and a fake-server run of N32d, R32, N32r, N32jr and N32j
with a window small enough to cut at every item (all archives verbatim, no run void, a wrong stub sum corrected, the
fallback path taken).

A Codex read-only review of the diff found 11 defects, all fixed before launch. The three that mattered most: the
retrieved text could push the context over the limit (it is now trimmed to the tokens really left after the cut);
the retrieval-only arm was handicapped by showing sentences alone (the two choices above); and `same_rule`, which
decides whether a rule is a rewording of one already held, treated "abcd12 is secret" and "efgh34 is secret" as one
rule, so a second rule about another counter would have been dropped. That last one was also in the keeper arm and
the proxy as run in campaigns 8 and 9 (their streams have one rule of each kind, so no result changed); both now
require the same names and numbers. Also fixed: arithmetic with no whole-number value is rejected instead of
trusted, working that starts from a number for a counter the NOTES call removed is rejected, a reply without an
OPEN heading keeps the old OPEN section, the space budget is applied to the rendered message, and the coverage tool
counted the method sentence under the wrong question type (my first coverage figures, never published, were wrong
for that reason and are replaced above).

## Campaign 10 results (2026-10-11 17:47-): cheaper notes, and retrieval alone

One server start, arms from a queue; no GPU fault line. Rules stream, 240K, 32K live window. Minutes are agent time.
"Notes wrong" is from `notes_audit.py`: every version of the pinned NOTES is compared with the grader's true ledger at
the point it covers, and the counters whose value was ever wrong are counted (a wrong value can sit in the NOTES
without costing an answer if nothing asks for that counter before it is set again).

| arm | seed | score | final list | min | model calls | notes calls | notes tokens written | notes wrong |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N32j keeper (campaigns 6, 7) | 0 | 39/39 | 14/14 | 15.7 | 197 | 23 | 42,887 | 0 |
| N32j | 1 | 46/46 | 21/21 | 16.5 | 188 | 23 | 48,220 | 0 |
| N32j35: cut to 35 % | 0 | 39/39 | 14/14 | 12.7 | 176 | 14 | 31,995 | 1 |
| N32d: changes only, no thinking (first version) | 0 | 39/39 | 14/14 | 14.4 | 192 | 31 | 28,351 | 2 |
| N32e: the same after two fixes | 0 | 39/39 | 14/14 | 12.2 | 200 | 25 | 13,158 | 8 |
| N32e35: N32e, cut to 35 % | 0 | 36/39 | 12/14 | 10.3 | 177 | 17 | 16,129 | 6 |
| N32e25: N32e, cut to 25 % | 0 | 39/39 | 14/14 | 9.8 | 174 | 13 | 14,511 | 2 |
| N32c35: N32e35, notes in pieces of six items | 0 | 38/39 | 14/14 | 10.8 | 196 | 33 | 16,022 | 2 |
| N32x: in-place notes, no thinking | 0 | 39/39 | 14/14 | 11.3 | 194 | 28 | 20,267 | 2 |
| **N32xth: in-place notes that think, every ten items** | 0 | **39/39** | 14/14 | **9.5** | 182 | 18 | 22,770 | **0** |
| **N32y: the same after two robustness fixes** | 1 | **46/46** | 21/21 | **8.5** | 190 | 14 | 17,510 | 2 |
| R32: retrieval only, store = what left the window | 0 | 32/39 | 7/14 | 13.0 | 170 | 0 | 0 | |
| R32a: retrieval only, store = every item | 0 | 38/39 | 13/14 | 10.8 | 169 | 0 | 0 | |
| R32a | 1 | 30/46 | 5/21 | 11.7 | 173 | 0 | 0 | |
| **R32b: R32a, store out of the model's reach** | 0 | **39/39** | 14/14 | **9.2** | 160 | 0 | 0 | |
| **R32b** | 1 | **45/46** | 20/21 | **9.7** | 161 | 0 | 0 | |

Every arm answered all 25 mid-stream questions on its stream (current value, old value, who, rule, method: 5/5 each)
except N32e35 and N32c35 (one current value each). The differences are in the final list and in the NOTES.

### What the time is made of

Server counters after 1,170 requests of this campaign: 54 % of the server's time is reading (6.3M new prompt tokens at
2,640 tokens/s) and 46 % writing (194K tokens at 96 tokens/s). My statement before the campaign, "the cost is written
tokens, not reading", was right for the notes call of N32j and wrong for the run as a whole. In N32j and N32e every
stream token is read about four times: when it arrives; when the turns kept by a cut are read back at their new
place (23 cuts x 17K = 391K tokens at 240K: the fetch after a cut takes 6.7 s against 1.6 s otherwise); and when the
cut turns are shown to the notes call as text (312K). Agent time of N32j seed 0: 941 s = main loop 432 + notes
calls 492 + shell 17.

### Changes-only notes without thinking: fast, but the NOTES go wrong (not adopted)

The notes call writes only the changed lines, with the working on the line, and the harness applies them: 570 tokens
a call instead of 1,865, notes time halved (N32e: 241 s against 492 s). The first four scores looked fine (39, 39, 36,
39 of 39), and the 36 looked like the price of a deeper cut until the 25 % setting scored 39. The audit settles it:
**every one of the six no-thinking runs (N32d, N32e, N32e35, N32e25, N32c35 and the first in-place run N32x) had
wrong values in its NOTES, 2 to 8 counters at some point; the thinking runs of that evening had 0 to 3.**
Example, the same in N32d and N32e: "The clerk recorded domo86 at three hundred and forty-two. ... Ten were taken
from domo86." was noted as `-390 - 342 - 10 = -742` (a set read as a subtraction; true value 332). The working check
passes such a line: it starts from the right value and the sum is right. The value stayed wrong for 35 items, until
the next set; no question asked for it in between. So a perfect score on 39 questions does not show that the NOTES
are right, and at 1M, with six times the questions, these errors would be answers. Thinking in the notes call stays.

Two defects of mine found on the way, both fixed: the working check sent 8 of 23 cuts to the slow path because the
model writes a set and a following change on one line (`294 + 12 = 306`), which is right (working may now start from
a number the cut turns state); and the harness read `-107 -> -31` and `-58 - 35 = -93, then set to 82` as their
first number (it now reads the last one).

### In-place notes: the same notes, nothing read twice (the result of this campaign)

Arm N32xth / N32y. Every ten items (17K tokens of turns), when the newest turn is an ordinary delivery, the notes
call is the live conversation itself with one more message at its end (same tool list, `tool_choice` none), so the
server has already read all of it: 20K prompt tokens of which 16.6K come from the cache. The reply is the changes
only, written with thinking; the harness applies them; then every turn in view is moved to the archive and the
context is the task statement and the NOTES again (1.5K to 2K tokens). Nothing is read back after the cut, and the
agent's own calls run at 2K to 20K of context instead of 18K to 28K.

- seed 0 (N32xth): 39/39 in 9 min 49 s against 15 min 41 s (-37 %); seed 1 (N32y): 46/46 in 8 min 47 s against
  16 min 30 s (-47 %). The bar was within one question on both seeds and 25 % less time.
- where the time went, seed 1: 511 s = main loop 268 (147 fetches at a median 1.3 s) + notes 224 (14 calls of about
  1,250 written tokens) + shell 18. Prompt tokens of the whole run: 1.79M against 3.7M.
- NOTES audit: 0 counters ever wrong on seed 0, 2 on seed 1 (a removal, the only mention of that counter in a batch
  of ten items; and a set that was read past, see the correction below; N32j had 0 and 0). Arm N32z adds a check for exactly that: a name of a STATE line that the items
  being moved out mention, outside a question, without a line in CHANGES is asked about once.
- N32y differs from N32xth in two things that only act on a doubtful reply: it is asked for again in place (with
  thinking and the lines named) instead of handing the turns to the ordinary cut, and a STATE value is read as its
  last number.

### Retrieval alone ("RAG"): it matches the keeper at 240K once it is built right

Three versions, each fixing something the one before showed:

- **R32, 32/39.** The store held only what had left the window. All 25 mid-stream questions right, including the
  rule 5/5 and the method 5/5; the final list 7/14, four of them stale values. Every sentence a right answer needed
  was in its context (`final_evidence` check): the older changes in the retrieved list, the newer ones in the
  window, and it did not put the two together.
- **R32a, 38/39 and 30/46.** The store holds every item from the moment it arrives, so the retrieved list is
  complete on its own. But in all three runs so far the model had gone looking under `/tmp/.live_ctx` (the task
  statement names that directory), found the archive files the harness writes there, and answered the final list
  with its own scripts over them: right on seed 0, and on seed 1 with a number-word parser that added about 100 to
  most values (5/21). Those runs were not retrieval-only.
- **R32b, 39/39 and 45/46, in 9.2 and 9.7 minutes.** The same with the store kept by the harness only (no files).
  The model answers from the retrieved sentences and gets the final list 14/14 and 20/21.

So, on this stream at 240K, **retrieval alone is within one question of the keeper on both seeds** (the preregistered
test), with no notes call at all, and as fast as the fastest keeper setting. What I told the owner before the run
("rules never get retrieved"; "what is true now becomes a replay that fails") is not what happened: the rule names
its counters, so a question about one of them retrieves it, and a 27B that thinks replays a short list of changes
correctly. Why it works here, and what remains to be shown: the things asked about are exact strings; a counter is
reset every third change, so a value needs one or two old sentences; and the questions are explicit. The 1M stream
(20 sentences per question cover 187 of 228 questions; a probe item asks seven) and the stream with "it" and
cross-references are the tests that follow.

### Making the in-place notes complete: three checks, each from an audited error

The in-place arm was run five times at 240K while its checks were tightened. Every change came from an error the
audit found in the NOTES, and each arm name is one state of the code, so the table keeps them apart.

| arm | seed | score | min | notes calls | asked again | notes wrong | what was new in this arm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| N32xth | 0 | 39/39 | 9.5 | 18 | | 0 | in-place notes that think, every ten items |
| N32y | 1 | 46/46 | 8.5 | 14 | 0 | 2 | a doubtful reply is asked for again in place; a STATE value is read as its last number |
| N32z | 0 | 38/39 | 9.3 | 16 | 1 | 3 | a name the items mention must have a line in CHANGES |
| N32w | 0 | 39/39 | 9.6 | 19 | 4 | 2 | the lines of a name must account for as many changes as the items mention it |
| N32v | 1 | 45/46 | 9.7 | 18 | 4 | 2 | a value written without working must be one the items state |

What the audit found, in order: a removal that was the only mention of its counter in ten items, left out (N32y);
the second of two changes in one item left out, twice, with one wrong answer (N32z: `fasu60`, asked while wrong);
`rumi16: -132` written without working for 29 - 73 (N32w); and `zija81: -62` for 134 - 16 (N32v, one wrong answer),
which the last check should have caught and did not, because my number scanner counted the 62 inside the counter
name `xasa62` as a number the items state. That is fixed (digits inside a name and item headings are not numbers),
and arm N32u also narrows "the items state it" to a sentence that names the thing, or the one after it. So the
honest reading of the 240K table is: **same scores as the full keeper within one question (39, 46, 38, 39, 45
against 39 and 46), in 8.5 to 9.7 minutes against 15.7 and 16.5, with 0 to 3 wrong values in the NOTES per run
where the full keeper had 0.** The remaining errors are of the kinds the checks now reject; N32u is the first arm
with all of them and has only run at 1M (below). Ten items per notes call is also more than the full keeper's six;
six per call (arm N32w6) is wired and not run.

### The stream that says "it" and refers to other counters (exploratory, one seed)

`client-hard`: every change names its counter in one sentence and changes it in the next, with doublings, thirds and
"it went up by as much as Y held at that moment". 50 questions.

| arm | score | probes | final list | min | notes wrong |
| --- | ---: | ---: | ---: | ---: | ---: |
| N32z keeper, in-place notes | 42/50 | 23/25 | 19/25 | 14.9 | 14 |
| R32b retrieval only | stopped by me at 20.5 min, item 104 of 147 | 10/15 answered (3 blank); the keeper had 15/15 at that point | | | |

Neither method is good here. The keeper's NOTES went wrong mostly at the cross-references (nearly every first wrong
value follows a "went up by as much as Y held" change), and one wrong counter then spoils the ones that copy from it.
Retrieval was both slower and worse: a question about X retrieves "X ... it went up by as much as Y held", but
nothing about Y, and the model spent long thinking turns on what it could not see. This stream is the place to
measure the next version of either method; it is not calibrated, and one seed says only which way the difference
points.

### One million tokens with in-place notes: 228 of 228 in 50 minutes

Arm N32u (N32v with the scanner fix, and "the items state it" narrowed to a sentence that names the thing). The
first start of the 1M run (N32v, 21:34) was stopped by me after 3 minutes when the audit of its 240K run showed the
scanner defect; N32u started at 21:37 on the same server. Same stream as campaigns 5 to 9 (999,460 tokens, 617
items, 228 questions), 32K live window, official grade, not void, 610 archive files, all verbatim.

| | N32u in-place notes | N32j keeper (campaign 8) | proxy X32b (campaign 9) |
| --- | ---: | ---: | ---: |
| all 228 questions | **228 (100 %)** | 226 (99.1 %) | 222 (97.4 %) |
| current / old value / who / rule / method | 58/58, 58/58, 29/29, 29/29, 29/29 | 58/58, 58/58, 27/29, 29/29, 29/29 | 58/58, 56/58, 28/29, 28/29, 27/29 |
| by distance back: 1-4 / 5-24 / 25-99 / 100-399 / 400+ items | 50/50, 50/50, 30/30, 48/48, 25/25 | 49/50, 49/50, 30/30, 48/48, 25/25 | 49/50, 50/50, 30/30, 44/48, 24/25 |
| final list | 25/25 | 25/25 | 25/25 |
| **agent minutes** | **50.2** | 82.9 | 95 |
| model calls (of which notes calls) | 870 (84) | 865 (110) | 657 by the agent |
| prompt tokens sent / of which from the cache | 10.0M / 7.9M | 16.7M / 12.9M | |
| tokens written: main loop / notes calls | 68K / 111K | 66K / 231K | |
| time: main loop / notes calls / shell | 1,586 s / 1,345 s / 82 s | 2,262 s / 2,633 s / 79 s | |
| counters ever wrong in the NOTES (audit) | **0** in 63 versions | 5, all in one version | |

Per 100K tokens: 4.2, 4.3, 6.4, 4.5, 5.2, 5.1, 3.7, 4.9 and 6.1 minutes (no trend; the keeper took about 8.3).
The preregistered bar was 222 or better in under 60 minutes.

What the notes calls did: 63 cuts, 59 of them in place (four by the ordinary cut, when a question was open as the
window filled; three of those were noted in two pieces). 1.75M prompt tokens in the in-place calls, 1.51M of them
from the cache. An in-place reply was asked for again 18 times in 17 of the 59 cuts: 13 times because a name's
lines accounted for fewer changes than the items mention it, 5 times because working did not start from the value
held (`suru92: working starts from -14, NOTES say removed`); one doubtful line was accepted after the second reply. NOTES stayed between 391 and 1,147 tokens with both rules in
place. The audit finds no counter ever wrong.

What the audit shows about the full keeper on the same stream, which its score had hidden: at one cut (model call
178) its rewritten NOTES ended mid-list, 39 lines instead of 62, without an OPEN section, and five live counters
were gone from STATE until later cuts brought them back. A full rewrite can lose lines that way and still pass the
layout check; changes-only notes cannot, because the harness keeps every line the model does not mention.

One seed, one stream. The 240K runs of the earlier in-place arms had one wrong answer in two of five runs; N32u is
the first arm with every check and has this one run. Its two 240K runs are queued behind the retrieval-only run.

### Retrieval alone at one million tokens: perfect for two thirds, then it falls behind

Arm R32c40: the retrieval-only build that scored 39/39 and 45/46 at 240K, with 40 sentences per question and room
for 70,000 characters of retrieved text (a question item asks seven questions here). Same 1M stream, same window.
A stopped run: I ended it after 59 minutes, when it had answered every question item and then issued 223 empty
commands at the final list.

| mid-stream questions (203) | R32c40 retrieval only | N32u in-place notes |
| --- | ---: | ---: |
| all | 189 (93 %) | 203 (100 %) |
| first / middle / last third of the run | 63/63, 70/70, **56/70** | 63/63, 70/70, 70/70 |
| current / old value / who / rule / method | 55/58, 53/58, 28/29, **25/29**, 28/29 | 58/58, 58/58, 29/29, 29/29, 29/29 |
| by distance back: 1-4 / 5-24 / 25-99 / 100-399 / 400+ items | 50/50, 46/50, 27/30, 47/48, **19/25** | 50/50, 50/50, 30/30, 48/48, 25/25 |
| final list of 25 | not answered | 25/25 |
| minutes | 46.9 to reach the final item | 50.2 for the whole run |

Through item 420 it was perfect (140 of 140) and slightly faster than the keeper. All 14 errors are after item 500.
Four are the standing rule: by then a confidential counter has been mentioned dozens of times, the 40 best matches
for its name are recent changes (ties go to the later sentence), and the rule from item 1 is no longer among them;
the model answered a number or null. The rest are values worked out from an incomplete list. This is what the
coverage figures predicted before the run (187 of 228 questions coverable at 20 sentences, 220 at 40): the evidence
a question needs grows with the history, and the rule is one sentence among thousands. The keeper's NOTES stayed
at about 1,000 tokens with both rules in them.

The final list is a limit of this build rather than of retrieval: the retrieved text for 25 questions filled the
window, the next cut removed the question item and that text, and the model had nothing left to work from. A build
that answers a long list a few questions at a time would not fail this way. The mid-stream comparison is the clean
one.

**The memory guard fired at 23:27:09** (1.28 GiB available; the floor is 1.6) two seconds after I stopped that
client: its shutdown wrote out a 900-call history. Same cause as on campaign 9. The server was idle, nothing was
lost but the three runs still queued (N32u on the two 240K seeds and on the hard stream); no GPU fault line in the
kernel log; Gemma was restored at 23:32 and answers. For 1M runs the client's bookkeeping has to happen after the
server is stopped, or without per-call snapshots; the campaign runner should do that itself.

### Reading (campaign 10)

1. **The fast form of the keeper is in-place notes.** Same or better answers at every size tested: 240K in 8.5 to 9.7
   minutes against 15.7 and 16.5; 1M in 50 minutes against 83, at 228 of 228 with NOTES that the audit finds right
   in all 63 versions. Two things made it: the notes call reuses what the server has already read, and after it the
   window is emptied instead of trimmed, so nothing is read back. And three checks keep a changes-only reply
   complete: every mention accounted for, every worked-out value with its working, every sum redone by the harness.
2. **Notes written without thinking are not safe, whatever they score.** 2 to 8 wrong values in the NOTES of each
   of the six such runs, with scores of 39, 39, 36, 39, 38 and 39 of 39. Only the audit showed it.
3. **Retrieval alone is much better than I said, and not enough at scale.** Built right it equals the keeper at
   240K (39/39, 45/46) with no notes call at all, and for the first 420 items of the 1M stream. It falls behind
   where the history is long (56/70 in the last third, the rule lost 4 times in 29) and where the text refers to
   things indirectly (10/15 against 15/15 on the hard stream). Building it right took three tries: the store has
   to hold everything from the moment it arrives, and the model must not be able to reach it with its own scripts.
4. **So the two are not rivals.** Retrieval finds; notes hold what must always be in view (rules, current state)
   at a fixed size. The keeper already has both halves (`recall` is retrieval on demand); automatic retrieval at
   question time is wired as arms N32jr and N32er and not yet run.
5. **A full rewrite of the notes can lose lines silently** (the keeper's own 1M run, once, five counters). Changes
   applied by the harness cannot.

Owed: N32u on both 240K seeds and on the hard stream (queued, lost to the guard); a second seed at 1M; the proxy
with in-place notes (designed in the charter, not built); the hybrid arms; six items per notes call; a rule that
does not name what it covers, which neither retrieval nor this benchmark has been tested on.

## Campaign 10b (2026-10-12 00:01-02:08): the runs the guard cost, and the hard stream again

Same server recipe, started once more after Gemma had been back for half an hour; runner `longrun-campaign10b.sh`,
queue `QUEUE10b.txt`. Nine runs, no GPU fault line, no guard event (no 1M client).

**The fully-checked in-place arm on both 240K seeds: 39/39 and 46/46; one counter wrong in the NOTES on seed 1.**

| arm N32u | questions right | minutes | notes calls | counters ever wrong in the NOTES |
| --- | ---: | ---: | ---: | ---: |
| 240K rules stream, seed 0 | 39/39 | 9.9 | 20 | 0 |
| 240K rules stream, seed 1 | 46/46 | 10.0 | 19 | 1 |
| 1M rules stream (campaign 10) | 228/228 | 50.2 | 84 | 0 |

313 of 313 answers over the three runs, against the full keeper's 311 of 313 in 15.7, 16.5 and 82.9 minutes. The
checks cost up to a minute and a half at 240K (9.9 and 10.0 against 9.5 and 8.5 for the unchecked versions). The one
wrong counter (seed 1, `dope10`, wrong from item 121 until it was next set; no question asked for it meanwhile) is
a misreading no check here can see: "The clerk recorded dope10 at six." was not taken as a new value, and
"Thirty were taken from dope10." was then worked from the old one (`92 - 30 = 62`; true value -24). The same
sentence was misread the same way in the two earlier in-place runs on that seed, and the same phrase ("the clerk
recorded X at N") is the one the no-thinking notes turned into a subtraction. It is the model's reading, not its
bookkeeping. Six items per notes call instead of ten (N32u6, seed 0): 39/39 in 10.0 minutes with 28 notes
calls and two counters wrong in the NOTES for a while; no gain, ten stays. One of the two was a defect, fixed: a line
`tamija29: (no change - mention is the confidentiality rule itself)` was stored as that counter's value (a no-change
line with a remark after it is now still a no-change line).

**The hard stream ("it" in the next sentence, values that depend on other counters; 50 questions, one seed).**

| arm | score | probes | final list | min | notes wrong | what happened |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| N32z (campaign 10) | 42/50 | 23/25 | 19/25 | 14.9 | 14 | |
| N32u | 3/50 | | | 17.4 | | stuck at the first question item: one archive search refused 362 times in a row |
| N32t: N32u + the refusal says stop after three, and that call is sampled | stopped by me at 11 min | 5/5 on the first item | | | | circled between three different searches instead |
| N32s: + `recall` shows the sentence after each match; a search sent a third time since the last item is refused | 43/50 raw, **void** | 20/25 | 23/25 | 19.6 | 10 | void for one key in the answers file that was not asked for; the standing rule lost at the first cut |
| N32ur: N32u + retrieved sentences at each question | 47/50 | 23/25 | 24/25 | 19.4 | 10 | |
| **N32sr: everything together** | **46/50** | 22/25 | 24/25 | **14.4** | 6 | |
| R32b retrieval only (campaign 10) | stopped at 20.5 min | 10/15 on the first three items | | | | |

What this stream taught, each now in the code:

- **A refused repeat does not end a loop under greedy decoding.** The same context plus the same refusal gives the
  same command again. From the third refusal in a row the note says to stop and answer, and that one call is
  sampled (temperature 0.5 rising to 1.0).
- **A search tool that prints matching sentences alone is blind on text that says "it".** `recall "nipewe33"` returned
  "Next on the list was nipewe33." and never the sentence that changed it; the agent then searched for "It was
  opened", "It was lowered", ... `recall` now prints each match with the sentence after it.
- **A loop can go round three commands.** A search sent a third time since the last item arrived is refused like a
  repeat (the archive has not changed in between).
- **An asked-for second reply must not lose what the first one had.** N32s lost the standing rule at its first cut:
  the first reply named it, the count check asked again, the second reply left NEW RULES empty, and the second
  reply stood. A rule named in any reply of one notes call is now kept. (Rule 3/5 in N32s, 5/5 again in N32sr.)
- **Retrieval at question time helps the keeper here**: 47 and 46 of 50 with it, 42 and 43 without. The same three
  misses remain in both runs with it (and a fourth in N32sr): values that passed through a chain of "as much as Y
  held" changes.

N32sr on the 240K rules stream, seed 1: 46/46 in 11.2 minutes, no counter wrong in the 14 of 15 NOTES versions the
audit can place. Retrieval added to the keeper
costs about a minute there and loses nothing.

So after both campaigns the recommended form is the keeper with in-place notes and its checks (N32u: 313/313 on
the rules streams up to 1M), with retrieval at question time switched on where the text refers to things indirectly
(N32sr).

**Correction to the audit figures (02:40, after a second Codex read-only review of the night's code).** The review
found that `notes_audit.py` could skip a NOTES version: right after an in-place cut the context is the task and the
NOTES alone, the tool marked that version as seen there, and never audited it once items were in view again. Fixed
(a version counts as audited only when it is seen together with an item; the tool now prints how many versions it
audited), and every audit was run again. Changed: N32y 1 to 2, N32v 1 to 2, N32u seed 1 0 to 1 (all three the
`dope10` misreading above), N32ur on the hard stream 9 to 10. Unchanged: every other run, including **N32u at 1M: 0
counters wrong, 63 of 63 versions audited**, and N32j (0, 0, and 5 at 1M). The tables above carry the corrected
figures. The review's other 14 findings change no result on record and are fixed in the code (review text:
`data/2026-10-11-context-campaign10/codex-review-2-findings.md`): a value written with words round it or as
`old -> new` escaped the "stated in the items" check; a value the items set could excuse two workings; the sign of
a set value was not checked (`opened at 402` allowed `-402`); the ordinary cut's pieces skipped the checks; the count
of steps in working missed single-digit operands (a needless re-ask); a counter opened and left out altogether was
not noticed; number words ran on across a full stop; a search refused as a repeat stayed refused after the archive
had grown; sampling stayed on after the loop was left; rules in a reply without the full layout were dropped; the
search tool printed a sentence twice when two neighbours matched; failed in-place attempts were missing from the
cost records. One finding is left as designed and is a known limit: after one re-ask the second reply is accepted
even if a check still objects (once in 63 cuts at 1M, and that reply was right). The arm names N32xth to N32sr are
states of the code on the night, not switches; the header of `second-comparison.sh` says which commit ran what. Not yet run: N32sr at 1M; any of this in the proxy; a second seed of the hard stream, which stays
exploratory until it has one.

## Campaign 11 (2026-10-12, preregistered before any result): in-place notes in the proxy; a rule that names nothing

The owner asked what I suggest next. Suggested and started: (1) put in-place notes into the proxy, the form a real
agent uses; (2) stop tuning on the rules stream, which the fully-checked keeper now answers 313 of 313, and test what
it cannot show; (3) a real task. This campaign is (1) and the first of (2).

**Built before the run (no GPU):**

- `tools/ctxkeeper`: `--notes-mode inplace` (commit 4c5fb18fd and the fixes after it). The notes call is the view the
  server has just read, without the newest exchange, plus one message, with the same tool list and `tool_choice`
  none; the reply is the changes only; the proxy applies and checks it (`notesdelta.py`, its core copied unchanged
  from the harness keeper and held in step by `sync_notesdelta.py`); the noted messages are archived and the view
  becomes the opening messages, NOTES and the newest exchange. Differences from the harness arm, forced by a client
  that resends its history: the newest exchange stays in view (the model has to act on it), so about nine items are
  noted per call instead of ten; the latest user message stays in view while it is being worked on; a question that
  arrived in a tool result blocks the cut until it is closed. 44 unit tests, a scripted end-to-end run of the plain
  agent through the proxy, and a Codex read-only review: 10 findings, all fixed before the run (the two that
  mattered: with a user message after tool results the assistant's call could be archived and its results kept;
  a save that failed half-way could archive the same messages twice).
- `make_sparse_prose_tasks.py --class-rule`: a second standing rule in item 1 that names no counter and shares no
  word with the questions it governs: "any figure below zero is reported as the single word overdrawn, never as a
  number", for every answer about a counter, now or earlier, and the final list (a tally stays a number). 7 of 39
  expected answers on seed 0 and 9 of 46 on seed 1 are that word. A question about X cannot find this rule by X's
  name or by its own wording (`rag_retrieve` shares no term with it); it has to be kept in view. This is the claim
  about notes against retrieval that no run has tested: in campaign 10 retrieval found the rule because the rule
  named its counters.
- The runner passes `emit_ctx_trajectory=false` on 1M runs: the end-of-run export of a 1M-token history is what took
  0.8 GiB of host memory and stopped the server three times. Untested, so a 1M run still goes last.

**Arms.** X32i: the plain agent (it sends its whole history) through the proxy with `--notes-mode inplace
--inplace-tokens 15000 --notes-checks near`, otherwise the proxy flags of campaign 9. N32k / N32kr: the harness
keeper with in-place notes, without and with retrieval at each question, on today's code (after both reviews).
R32b: retrieval only.

**Reading rules, fixed now.**

- **Proxy.** "The proxy carries the gain" if on both 240K seeds X32i is within one question of X32b (39 and 44) and
  takes at least 25 % less time (X32b: 17 and 18 minutes, so 12.75 and 13.5 or less), and on the 1M stream scores
  220 or more of 228 (X32b 222) in under 70 minutes (X32b 95; harness N32u 50). Reported with it: in-place cuts,
  failed attempts, replies asked for again, cached share of the notes calls, and an audit of the proxy's saved NOTES
  versions against the true ledger.
- **Rule by condition.** On each seed: of the questions whose answer is the word, how many are right, keeper against
  retrieval. "The rule is kept" at 80 % or more; "lost" at 20 % or less. My expectation, written down so it can be
  wrong: the keeper keeps it (the rule sits in NOTES and is repeated at each question), retrieval loses it. The
  other questions are reported too (a method that answers "overdrawn" for a positive value has not kept the rule).
- **Hard stream, second seed** (if time allows before the 1M run): N32kr against N32k. Seed 0 had 47 and 46 with
  retrieval, 42 and 43 without. Exploratory still; the direction of the difference is what a second seed can add.
- One seed per cell beyond these. One or two questions between arms is not a ranking.

Runner `longrun-campaign11.sh` (queue file; one server start; Gemma stopped first and restored at the end).

## Campaign 11 results (2026-10-12 03:12-): in-place notes in the proxy; a rule that names nothing

One server start, arms from a queue. Minutes are agent time.

### The proxy with in-place notes (plain agent that sends its whole history, 32K window)

| proxy, 240K rules stream | seed 0 (39) | seed 1 (46) |
| --- | ---: | ---: |
| X32b: full NOTES rewrite at each cut (campaign 9) | 39 in 17 min | 44 in 18 min |
| X32i: in-place notes, first build | 39 in 10.2 min | **40 in 12.3 min** |
| **X32m: in-place notes after the merge fix** | **39 in 10.2 min** | **46 in 13.1 min** |
| N32u: the same policy inside the harness (campaign 10b) | 39 in 9.9 min | 46 in 10.0 min |

X32m meets the bar on both seeds (within one question of X32b, at least 25 % less time: 40 % and 27 % less). Seed 0
of X32m is the same run as X32i, call for call (the fix did not come into play). Per run: 17 in-place cuts, no failed
attempt, no ordinary cut; a reply asked for again 8 and 14 times; notes calls read 431K and 544K prompt tokens of
which 387K and 487K came from the server's cache (90 %), and wrote 22K and 31K. An audit of the proxy's saved NOTES
versions against the true ledger (`proxy_notes_audit.py`): no counter ever wrong, 17 of 17 versions, on both seeds.

**The defect X32i seed 1 exposed (in the harness arm too, never hit there).** 40/46, with 15 counters wrong in the
NOTES from the version that covers items 100 to 108 on. When a reply fails a check the model is asked for "the
three complete sections again", and the second reply was applied on its own. At that cut the second reply held four
lines where the first held 27 (the model answered with the lines that had been in question), and the changes of
nine items were gone. Fixed in both (`merge_replies`): an asked-for reply replaces the lines of the names it
mentions, `name: (no change)` withdraws a name, and every other line of the reply before it stays; the proxy now
logs every notes reply, which is how the four-line reply was seen in the re-run. The same run showed the checks
earning their keep: "The clerk recorded domo86 at three hundred and forty-two" came back as `-342`, the sign check
refused it (the text states 342), and the corrected line was applied.

My audit tool misread a typographic minus sign as no sign and reported five wrong counters on the first proxy run;
fixed before any figure was written down (harness figures did not change).
