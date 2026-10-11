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
