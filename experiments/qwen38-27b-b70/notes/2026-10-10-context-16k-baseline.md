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

### A rule that names nothing: notes keep it, retrieval never finds it

Stream `client-crule`: the 240K rules stream with one more rule in item 1, "any figure below zero is reported as the
single word overdrawn, never as a number" (for every answer about a counter, now or earlier, and the final list).
It names no counter and shares no word with the questions it governs.

| questions whose right answer is the word | seed 0 | seed 1 | both |
| --- | ---: | ---: | ---: |
| **Keeper with in-place notes** (N32k, N32m) | 7/7 | 9/9 | **16/16** |
| **Retrieval only** (R32b) | 0/7 | 0/9 | **0/16** |
| the other questions: keeper / retrieval | 31/32, 31/32 | 34/37, 36/37 | |
| whole stream: keeper / retrieval | 38/39, 31/39 | 43/46, 36/46 | |
| minutes: keeper / retrieval | 9.7, 10.4 | 11.4, 9.8 | |

"Kept" was 80 % or more and "lost" 20 % or less; it is all against none on both seeds, as expected and now measured.
Retrieval answered every one of the 16 with the true negative number: the rule had left the window by the first
question item (item 26) and nothing in "What value does X hold now?" leads back to it. The keeper had the rule as a
RULES line from the first cut, whole, and it was repeated at every question item. This is the difference between the
two methods that campaign 10 could not show, because there the rule named its counters.

One thing the stream got wrong, not the methods: the rule's last clause, "a tally is still worked out from the true
figure", does not say how a tally that comes out below zero is to be reported, and the keeper, which had the rule in
view, answered "overdrawn" for those (4 of the keeper's 4 misses outside the governed questions; retrieval, which
had lost the rule, gave the number and was marked right). The grader expects the number. Read the "other questions"
row with that in mind; the clause should say "and is reported as a number" before this stream is used again.

### The proxy at one million tokens: 216 of 228 in 76 minutes, below the bar

Stream `client-1m` seed 0 (617 items, 228 questions), arm X32m: the plain agent sends its whole history, the proxy
keeps a 32K window with in-place notes.

| 1M tokens, 32K window | right | minutes | notes |
| --- | ---: | ---: | --- |
| harness keeper, in-place notes (N32u, campaign 10) | 228/228 | 50.2 | NOTES audit 0 wrong of 63 versions |
| harness keeper, full rewrite (N32j, campaign 10) | 226/228 | 82.9 | |
| proxy, full rewrite (X32b, campaign 9) | 222/228 | 95.1 | |
| **proxy, in-place notes (X32m)** | **216/228** | **75.8** | 6 blank, 6 wrong; not void |

The bar written down before the run was 220 or more in under 70 minutes. **Missed on both counts.** It is 20 % faster
than the proxy's full rewrite and six questions worse. By type: final list 25/25, current 56/58, earlier value
53/58, who 26/29, rule 28/29, method 28/29. Counters: 662 client calls, 79.8K tokens written in the main loop;
77 in-place cuts, none failed, 111 notes replies (33 asked for again: 29 by the count check, 4 by the working
check) that wrote 133.8K tokens and read 1.98M of which 1.77M (89 %) came from the cache; 255 archive searches,
and the limit of eight searches in one turn was reached six times. Of 75.8 minutes, 70.6 are model time, and the 60
calls that took over 20 seconds each (the turns with a notes call or with a question item) are 41.6 of them: three
question turns took 160 to 172 seconds each.

**Where the twelve went.**

- *Six blank, all at one question item (item 441).* The model made its eight searches, then spent the one further
  call it was allowed thinking about which item "message 424" belonged to and returned nothing: no words, no
  command. The client nudged ("no tool call in your last turn"). The proxy answers `recall` itself, so the client's
  history never holds the searches, and in the next request everything found was gone. The model then believed only
  the seventh question was pending, answered that one (right) and never wrote the other six.
- *Six wrong: four earlier values (items 50, 56, 71 and 10) and two "who" questions (items 58 and 443).* All six
  ask about a numbered item. A search hit was labelled with its message number, not its item, and the thinking that
  was logged shows the model building a table from message numbers to items by hand. The harness keeper prints the
  item with each hit and got all six right on the same stream. (Attribution by that comparison and that thinking;
  the proxy did not log the searches themselves.)

**The NOTES were not as clean as the harness's.** `proxy_notes_audit.py`, 77 of 77 versions: two counters were
wrong for a while (`katu85` from item 246, `peroco54` from item 377; neither was asked about while wrong, and both
were reset before the final list). Both are one mistake: "The clerk recorded katu85 at five hundred and
twenty-three" (a set) came back as `650 - 27 = 623`, and "recorded peroco54 at sixty-four" as `208 - 64 = 144`.
Each starts from the value held and adds up, so the checks passed it. Also, twice the model stored its answers as
STATE lines (`p21_7: answered 571`); the working check asked, the model insisted, and the second reply stood.

**What the count check was really asking about.** Replaying the first reply of every cut through the checks: 14 of
the 25 count questions that remain once question items are no longer read as facts were lines that pack several
changes (`578 + 62 = 640, then set to 174`, `opened at 117, set to -190, +46 = -144`), which the counter took as
one change each. The harness keeper has the same counter: N32u asked again on 20 of its 63 cuts.

### What killed the server at the end of the long proxy runs

The guard fired at 05:58:05, two seconds after the trial's `result.json` was written: available memory went from
2.07 to 1.58 GiB. It was not the client. `summarize_results.py`, which the job script runs twice right after a
trial, loaded every context snapshot of the trial into a list, and a client that resends its whole history leaves
664 snapshots of up to 5 MB each: 1.7 GB on disk, **2.1 GB resident** (measured afterwards on that job folder).
Beside a server with about 2 GB to spare that is certain to fire the guard. One snapshot is held at a time now:
50 MB, the same output byte for byte. This explains the events after the two 1M proxy runs (X32b in campaign 9,
X32m here). It does not explain the event in campaign 10, which followed an interrupted retrieval run whose job
folder is 104 MB. `emit_ctx_trajectory=false`, which I had passed as the cure, was beside the point. The three
runs queued behind X32m were lost (hard stream seed 1 twice, the second 1M stream).

### Fixes made from this run (unit-tested and replayed on the saved replies; not yet run on the cards)

Proxy (`tools/ctxkeeper`):
- A search hit shows the first line of its message (`message 105 (tool, "ITEM 50/617 (UPDATE)"): ...`).
- The searches of a turn that ended with nothing for the client are shown again in the next request (bound to the
  history they were made in, cut to the room left in the window), and an empty reply is asked for once more with
  thinking off.
- `--max-recalls` (default 8), and a search result is cut to the room left beside the reply; once there is no room
  no further search is made in that turn.
- `--notes-scan`: only tool results that match are read as facts by the checks (question items are not).

Notes checks (shared by the harness keeper and the proxy):
- A line is counted by its parts (`steps_in`) and a line that packs several changes is followed part by part
  (`chain_of`): each set must be stated in the turns, each sum must be right, each step must start from the value
  before it.
- A line that ends at the value already held, from another start, is a change noted at the last call and read
  again (the newest exchange stays in view): no change, no question.
- With the near check, every amount added or taken in a line's working must be stated for that thing in the turns.
  This catches `650 - 27 = 623`. It cannot catch `208 - 64 = 144`, where the 64 is in the sentence.
- Replayed on the saved first replies: 33 replies asked for again at 1M become 9, of which 4 are lines the model
  really left out and one is the `katu85` error; at 240K, 8 and 14 become 4 and 4.

An independent review of the new code (Codex, read-only, before any run) reproduced six defects: a negative start
counted as a change, any part with one number read as a set (`increased by 5, then +2 = 7` stored 7 for 17),
brackets inside working dropped (`10 + (5) + 2 = 12` passed), the carried searches able to overflow the window, a
batch of searches sharing no budget, and carried searches reaching another conversation under the same session
header. All six are fixed, each with a test.

## Campaign 12 (2026-10-12 morning, preregistered before any result): the proxy after its fixes; the second seeds

Arms are today's code under new names (`second-comparison.sh`): X32n is the proxy as above with `--max-recalls 16
--notes-scan '^ITEM n/m (UPDATE)'`; N32n is the harness keeper with in-place notes and the same checks; N32nr adds
retrieved sentences at each question. Queue, in this order, one server, Gemma off for about three hours:

1. X32n, rules stream, seeds 1 and 0. Gate: 39/39 and 45/46 or better, in no more time than X32m (10.2 and 13.1
   min). If either seed is two or more questions below X32m the 1M run is not made and the cause is found first.
2. X32n, 1M stream seed 0. **Bar, unchanged: 220 or more of 228 in under 70 minutes.** Expected from the replay
   and the per-call times: 222 or more, 58 to 66 minutes. Also reported: blank answers, searches, how often the
   search limit and the carry were used, replies asked for again, and the NOTES audit (expected: no counter wrong
   that the amount check can see; a set read as a change with the same number can still slip through).
3. N32nr and N32n, hard stream seed 1 (the pair owed since 10b). On seed 0 retrieval took the keeper from 42 or 43
   to 46 or 47 of 50. Expected: retrieval adds two or more questions; "no difference" is a result.
4. N32n, 1M stream seed 1 (the second stream for the headline 1M claim). Expected: 97 % or more of its questions
   in 45 to 60 minutes, NOTES audit clean.

One stream each for the 1M runs: a 1M figure stays "one stream" until item 4 is done. If the guard fires again at
the end of a 1M run, the cause above was not the whole story and that is reported as such.

## Campaign 12 results (2026-10-12 06:26-)

### The gate: X32n on the 240K rules stream is faster and failed the gate (one cause, found, fixed as X32n2)

| 240K rules stream, proxy, 32K window | seed 0 | seed 1 |
| --- | ---: | ---: |
| X32m (last night): right, minutes | 39/39, 10.2 | 46/46, 13.1 |
| **X32n: right, minutes** | **14/39**, 9.6 | **45/46**, 11.0 |
| X32n: notes replies asked for again (X32m: 8, 14) | 4 | 6 |
| X32n: in-place attempts that failed (X32m: 0, 0) | 1 | 1 |
| X32n: tokens written by notes calls (X32m: 22K, 31K) | 17.9K | 23.9K |

The speed is what the replay predicted (fewer replies asked for again). The scores are not, and by the rule written
down before the run the 1M run was not made on this build.

**Seed 0, 14/39: one command.** All 25 mid-stream answers were right (20 graded from the answers file as it stood
at item 104, the last five compared by hand with the expected values) and the NOTES audit is clean, 17 of 17. At
the final item the model wrote the 14 final values with `cat > /app/answers.json`, and the 25 answers were gone.
**Seed 1, 45/46:** one counter stale in the final list (`sahidi23`: 339 for 423).

**Both come from the same weak point: a notes reply is questioned, the model gives no usable second reply, and the
whole cut falls back to the full rewrite.** Last night's X32m was asked the same kinds of question and always
answered; today it did not, twice.

- *Seed 0, at the first cut.* The count check asked about the three confidential counters (the rule sentence of
  item 1 names them without changing them: a known false alarm). The model answered "Let me verify each mention in
  the archive before replying", twice (it may not call a tool in a notes call). The attempt failed and the turns
  went to the ordinary cut. That full rewrite wrote six RULES lines instead of two: four restate the task's
  opening message, among them "Final item lists 14 counters to report; write /app/answers.json mapping each to
  its current integer value". Rules are repeated at every question item; at the final item the model did exactly
  that.
- *Seed 1, at the second cut.* Here the trigger is something the proxy does and the harness does not. After an
  in-place cut the newest exchange stays in view (a real agent needs the result it has just fetched). Its
  assistant message was written about the result *before* it, which the NOTES of that cut already cover; at the
  next notes call that message is the first of the turns to be noted, and the model wrote that result's changes
  again: `pediba69: opened at 214` (item 8, already noted). The value check looks in the turns being noted, does
  not find 214, and asks. The model answered with nothing, twice. The full rewrite that followed lost a change
  (`yomoke87`, the -17 of item 13).
- *Seed 1, the stale answer.* The same overlap, not caught: `sahidi23: 423 - 84 = 339`, a +84 already in the
  NOTES, written again and the wrong way round. The new amount check questioned it (84 is nowhere in those
  turns); the model insisted, and "the second reply stands" took it.

Replayed on saved sessions, a line for a name that none of the turns being noted mentions occurs in 5 of 77 cuts
at 1M (X32m) and 2 of 17 at 240K: the overlap is not rare, the checks had been absorbing it.

**Fix (arm X32n2, proxy only, unit-tested; the queue was reordered so that the two harness runs go first):**
the notes request says what that first message is; with the checks on, a line for a name that none of the turns
being noted mentions is left out without a question; when the model gives no usable second reply the first one
stands without the questioned lines (no failed attempt, no full rewrite); after the second reply a line whose
number the turns do not state is left out and the old value stays. Not reviewed by Codex before the run (the
research server is up); to be reviewed before anything is published from it.

Gate for X32n2, as before: 39/39 and 45/46 or better, no failed in-place attempt, then the 1M run.

### The hard stream, seed 1: accurate with retrieval, and the new checks are too strict for it

| hard stream (pronouns, values that depend on another counter), 240K, harness keeper | right | minutes |
| --- | ---: | ---: |
| seed 0, last night: in-place notes plus retrieved sentences (N32ur, N32sr) | 47, 46 of 50 | 19, 14 |
| seed 0, last night: in-place notes only (N32z; N32s voided) | 42, 43 of 50 | 15, 20 |
| **seed 1, today: in-place notes plus retrieved sentences (N32nr)** | **46 of 49** | **23.4** |
| seed 1, today: in-place notes only (N32n) | stopped by me at item 78 of 147 after 22.7 min; 10 of 10 answered until then | does not count |

N32nr missed two values in the final list and one tally; its NOTES had five counters wrong at some point (16 of
16 versions audited), every one a change of the kind this stream is made of ("went up by as much as X held", a
doubling, a set followed by a change in the next sentence). So the accuracy claim of last night holds on a second
seed: 46 of 49 with retrieval. The comparison "retrieval adds questions" could not be made on this seed, because the
partner run did not finish.

**Why it was slow and why N32n hung.** 51 notes calls for 17 cuts and 85K tokens written by notes calls (a plain
240K stream needs about 25K). Today's amount check ("every amount in the working must be stated for that thing")
questions every line of the form `228 + 577 = 805 (went up by as much as bamo35 held)`: 577 is bamo35's value, not
a number in the sentence. Each question costs a rewritten reply, and in the harness a reply questioned twice falls
back to the full rewrite, which here writes up to 9K tokens with thinking at about 45 tokens a second. N32n then
sat at one question item for eight minutes of long thinking calls and I stopped it (SIGINT to its `timeout`, the
same signal its time cap sends; host memory stayed at 2.1 to 2.4 GiB and the server was untouched).

Prepared, not applied while this queue runs (the queued harness run must use the same code as the finished one):
an amount may also be any value a thing of STATE holds, and times or divided by a small whole number passes; a
reply that is asked for again holds only the lines in question (`merge_replies` already keeps the rest), which cuts
the cost of every question, on every stream, from about 1,500 tokens to a few hundred; and the harness takes the
proxy's rule that a questioned reply never falls back to the full rewrite.

### X32n2 passes the gate: 39/39 in 8.8 minutes and 46/46 in 9.7, NOTES clean

| 240K rules stream, 32K window | seed 0 | seed 1 |
| --- | ---: | ---: |
| proxy, full rewrite (X32b, campaign 9) | 39/39, 17.0 min | 44/46, 18.0 min |
| proxy, in-place notes, last night (X32m) | 39/39, 10.2 min | 46/46, 13.1 min |
| **proxy, in-place notes, today's fixes (X32n2)** | **39/39, 8.8 min** | **46/46, 9.7 min** |
| harness keeper, in-place notes (N32u, campaign 10b) | 39/39, 9.9 min | 46/46, 10.0 min |
| X32n2: in-place cuts, failed, replies asked for again | 17, 0, 1 | 17, 0, 2 |
| X32n2: tokens written by notes calls (X32m: 22K, 31K) | 16.0K | 20.0K |
| X32n2: counters ever wrong in the NOTES (17 of 17 versions audited) | 0 | 0 |

The proxy is now as fast as the harness arm it was built from, on both streams, with the same score and clean
notes. What the fixes did in these two runs:

- No line for a name the turns never mention was written at all: saying what the first message after the NOTES
  is was enough (the filter that would have left such lines out never had to act).
- On seed 0 the model again answered the count question at the first cut with "Let me verify each mention in the
  archive before replying." The first reply stood, the cut was made in place, and the RULES section holds the two
  rules of the stream and nothing else. That is the whole difference between 14/39 and 39/39 on this seed.
- Three replies were asked for again over the two runs (X32m: 22).

Where the 9.7 minutes of seed 1 go (the server's own counters, sampled every 30 seconds): 523 of 584 seconds are
the model server: 190 s reading (517K tokens that were not in its cache, 2,720 a second: the 240K stream once, and
as much again in notes, the turns re-read after each cut and the uneven ends of cached blocks) and 333 s writing
(35.3K tokens at 106 a second, 20K of them notes). The proxy itself adds 2 seconds over the run; the client, its
155 shell commands and the trial start and end add about a minute.

### X32n2 at one million tokens: 220 of 228 in 53 minutes. The bar is met

| 1M tokens, 32K window | right | minutes | notes calls | counters ever wrong in the NOTES |
| --- | ---: | ---: | --- | ---: |
| harness keeper, in-place notes (N32u) | 228/228 | 50.2 | 63 cuts, 20 asked again | 0 of 63 versions |
| proxy, full rewrite (X32b) | 222/228 | 95.1 | 102 cuts | not audited |
| proxy, in-place notes, first build (X32m) | 216/228 | 75.8 | 77 cuts, 33 asked again | 2 of 77 |
| **proxy, in-place notes, today's fixes (X32n2)** | **220/228** | **53.3** | 76 cuts, 5 asked again, none failed | 2 of 76 |

The bar was 220 or more in under 70 minutes: met, by the smallest margin on the score and a wide one on time
(expected: 222 or more in 58 to 66 minutes; it came in at 220 in 53). Not void, no blank answer. By type: final list
24/25, current 56/58, earlier value 54/58, who 29/29, rule 29/29, method 28/29. No guard event at the end: host
memory was 2.4 GiB available when the summary script had run.

What each fix did here:
- *Search hits labelled with their item:* the six questions about a numbered item that X32m got wrong in the first
  150 items are all right, and "who" is 29 of 29 (X32m 26).
- *Item 441*, where X32m left six answers blank: 7 of 7. The carry of lost searches was never needed, nor the
  retry of an empty reply, nor the search limit (161 searches, X32m 255).
- *Counting and following packed lines:* 5 replies asked for again instead of 33; notes calls wrote 119K tokens
  instead of 134K, and the main loop 43K instead of 80K (fewer long search turns).
- *The first reply stands:* used twice; no in-place attempt failed.

Where the 53 minutes go (server counters): 2,789 of 3,196 seconds are the model server, 914 s reading (2.48M
tokens not in its cache: the 1.06M stream once and 1.4M more in turns re-read after cuts, search results, notes
calls and the uneven ends of cached blocks) and 1,875 s writing (192K tokens at 102 a second: 119K notes, 43K main
loop, 29K in search rounds). The proxy adds 24 seconds over the run; the client, 659 shell commands and the trial's
start and end about six minutes. 24 calls took over 20 seconds, 12 minutes in all (X32m: 60 calls, 42 minutes).

**The eight misses.**
- *Six, probably seven, are one confusion that my own fix made possible.* The search tool takes `before` and
  `after` as message numbers; since this morning each hit also shows its item ("ITEM 150/617"). At item 336 the
  model searched "before 332", meaning item 332; that is message 332, which is item 150. It read the result as
  complete ("no other mention between item 72 and 332"), concluded that `moja47` had been removed since item 72,
  and answered three questions about it with null although its NOTES said `moja47: set to 330 (ITEM 332)`; two
  more answers of that item and one each at items 378 and 588 are the same. The thinking is on record.
- *One lost to a misspelled name.* The model wrote `vozi36` for `vozimi36`; the new filter left the line out as
  unsupported; the question about the missing mention got an 8,192-token reply that could not be used; the first
  reply stood without the change. (Not asked about while wrong.)
- *One sign slip in the notes:* "+35" written as `-46 - 35`, which every check passes; `nidi38` was wrong in the
  final list (24/25).

**Fixed as code state p (arms X32p, N32p, N32pr), unit-tested, under review, not yet run:** `recall` can run in
the content's own numbering (`--recall-label '(?m)^ITEM (\d+)/' --recall-unit item`): every number it shows or
takes is then an item number; when there are more matches than fit, the ones nearest to the anchor are shown and
the count line comes first, not last. A line for a name the turns never mention, one or two letters from a
mentioned name that has no line, is given to that name. The OPEN section is told not to repeat STATE (the model
listed every live value there in every reply, about a fifth of what the notes calls wrote). For the hard stream: an
amount may be a value some thing of STATE holds or held, and times or divided by 2 to 10 passes. The harness takes
the proxy's rule that a questioned reply never falls back to the full rewrite.

**Reviewed before it ran** (a read-only review by a second model instance: the Codex CLI cannot run beside the
research server, a reviewer that only reads can). Ten findings, eight of them defects, all fixed with tests before
any run: leaving out one made-up line could leave the next one standing on it (`70 - 27 = 43` out, `43 - 31 = 12`
stored); a line for a real name could be given to a similar name (`bako35` to `bamo35`); a correction written
under the same misspelling was lost; any value held anywhere excused an invented amount (now: only values of
things the noted turns mention, and the amounts of a packed line no longer count as held values); a name written
into the working (`+ 402 (bamo35)`) was read as the amount 35; the label pattern was not checked and the model's
own text could set a label; a test of `notes_at` passed in either numbering; a second reply without the layout
was thrown away without the one layout question, and its rules with it; a search result too long for the room
lost its nearest matches. Two are stated tradeoffs, not fixed: times or divided by 2 to 10 is never checked against
the text, and a value a mentioned thing held earlier in the same reply still counts.
Not covered by a test: the harness path "the first reply stands" (the proxy's is).

Next in this queue: X32p on both 240K seeds (gate as before) and on the 1M stream. The proxy for these runs is
started by hand (`start-proxy-p.sh` in the campaign folder: campaign 12's options plus `--recall-label
'(?m)^ITEM (\d+)/' --recall-unit item`), because the running campaign script starts one only for the arms it knew.
Expected at 1M: 225 or more of 228 in 46 to 54 minutes. A sign slip of the kind above can still cost one.

### The harness keeper on a second 1M stream: 210 of 222 in 50 minutes (below what I expected)

Stream `client-1m` seed 1 (618 items, 222 questions), arm N32n (in-place notes with this morning's checks; the
harness's own `recall`, which was not changed today).

| 1M tokens, 32K window, harness keeper with in-place notes | right | minutes | notes |
| --- | ---: | ---: | --- |
| seed 0 (N32u, campaign 10) | 228/228 (100 %) | 50.2 | NOTES audit 0 wrong of 63 |
| **seed 1 (N32n)** | **210/222 (94.6 %)** | **50.0** | 7 blank, 5 wrong; NOTES audit 1 counter wrong for a stretch, 65 of 65 versions |

Expected: 97 % or more in 45 to 60 minutes. The time is as expected; the score is not. Not void. By type: final
list 19/19, current 55/58, earlier value 55/58, who 26/28, rule 28/29, method 26/29. 65 in-place cuts, none failed,
no fall back; 78 notes calls wrote 95K tokens (seed 0: 111K).

**Seven of the twelve are one event, and it is a hole in the keeper, not in the notes.** At the last question item
(609) the model searched for a counter's history up to item 480. The harness `recall` prints the first matches in
item order and stops at its line limit ("the list shows up to item 468"), so the model fetched whole items 468 to
480, three at a time, about 5K tokens a fetch. The window filled, the ordinary cut ran, and it moved the question
item itself out of view together with the first search results. The model finished reading item 480, no longer saw
any question, and ran `next`. Nothing was written for that item. The in-place cut waits while a question is open;
the ordinary cut does not, in the harness or in the proxy (the proxy is less exposed: its searches never enter the
history, and it made no ordinary cut in any run today).

The other five: two tallies and one current value computed from a value that the NOTES had right (the audit finds
them right at those items; the model answered from a search instead), one "who", one earlier value.

So the one-stream claim "228 of 228" does not carry over as it stood: **over the two 1M streams the harness keeper
is 438 of 450 (97.3 %)**, and both streams took 50 minutes. To fix, in this order: `recall` in the harness shows
the matches nearest to where it is asked (as the proxy's now does) and takes `--before` / `--after`; an open
question is never cut out of view by any cut (kept word for word until it is answered), in the harness and in the
proxy.

### X32p (code state p) at 240K: 39/39 in 8.5 minutes, 46/46 in 9.4, NOTES clean

The proxy at commit `9711d42d4` (the hash after this morning's rebase onto the other host's work), started by hand
with campaign 12's options plus `--recall-label '(?m)^ITEM (\d+)/' --recall-unit item`.

| 240K rules stream, proxy with in-place notes | seed 0 | seed 1 |
| --- | ---: | ---: |
| X32m (last night) | 39/39, 10.2 min | 46/46, 13.1 min |
| X32n2 (this morning) | 39/39, 8.8 min | 46/46, 9.7 min |
| **X32p** | **39/39, 8.5 min** | **46/46, 9.4 min** |
| X32p: in-place cuts, failed, replies asked for again | 17, 0, 2 | 17, 0, 2 |
| X32p: tokens written by notes calls | 15.7K | 20.1K |
| X32p: counters ever wrong in the NOTES (17 of 17 versions) | 0 | 0 |

Gate passed; the 1M run follows in the same queue. The OPEN section no longer lists live values (three short lines
now), but the notes calls wrote as much as before: most of what they write is thinking. None of the new paths
(misspelled name, lines left out, the first reply standing) was needed in these two runs.

### X32p at one million tokens: 226 of 228 in 50 minutes

| 1M tokens (stream seed 0), 32K window | right | minutes | notes calls | searches | counters ever wrong in the NOTES |
| --- | ---: | ---: | --- | ---: | ---: |
| harness keeper, in-place notes (N32u) | 228/228 | 50.2 | 63 cuts, 20 asked again | 124 | 0 of 63 versions |
| proxy, full rewrite (X32b) | 222/228 | 95.1 | 102 cuts | | not audited |
| proxy, in-place, first build (X32m) | 216/228 | 75.8 | 77 cuts, 33 asked again | 255 | 2 of 77 |
| proxy, in-place, this morning (X32n2) | 220/228 | 53.3 | 76 cuts, 5 asked again | 161 | 2 of 76 |
| **proxy, in-place, code state p (X32p)** | **226/228** | **49.6** | 75 cuts, 15 asked again, none failed | 112 | 5 of 75 |

Expected 225 or more in 46 to 54 minutes: met. Not void, no blank. By type: final list 25/25, current 58/58,
earlier value 58/58, who 29/29, rule 29/29, method 27/29 (both misses are tallies). **The proxy is now within two
answers of the harness arm it was built from, and as fast.** No guard event; host memory never below 1.83 GiB.

- `recall` in item numbers did what it was for: every earlier-value question right (58 of 58; X32n2 54, X32m 53),
  with fewer searches (112 against 161 and 255).
- Server time: 869 s reading (2.36M tokens not in the cache) and 1,676 s writing (172K tokens at 103 a second:
  93K notes, 55K main loop, 24K search rounds), 86 % of the 2,975 seconds. Twelve calls over 20 seconds, 6.5
  minutes in all (X32n2: 24 calls, 12 minutes; X32m: 60 calls, 42 minutes).
- New paths used: lines for names the noted turns never mention left out 7 times (the model still writes down
  what its kept message says, now without effect); one misspelled name put right (`roke83` for `voke83`); the first
  reply stood once.

**The audit is worse, and two of the five wrong counters are my own new rule's doing.** Neither cost an answer here.
- "A line whose number the turns do not state is left out" took out three lines that were right or nearly right
  but written in a form the checker cannot follow: `faxamo72: 279 → 415 (set, item 582), then 415 - 18 = 397, then
  removed (item 587)` and the same shape for `jaru53` (an arrow inside a packed line: not followed, so the checker
  saw only "397 is not in the turns"); and `vozimi36: 522 - 20 = 502, 502 - 17 = 485, 485 + 58 = 498`, where the
  last sum is wrong (543) and a plain line would simply have been recomputed. Left out, all three kept stale values
  (two counters that should have read "removed").
- `lodo77` and `tudi76`: read wrongly by the model (as in earlier runs: one line in about 75 notes calls); `tudi76`
  is behind one of the two wrong tallies.
- Eight of the fifteen questions were about amounts; six of those were a set written as made-up working whose
  result is right (`436 + 78 = 514` for "recorded at 514"): a question each, about 13 seconds.

Fixed after the run, before the next (not yet run): a packed line is followed through arrows and its sums are
recomputed like a plain line's; a line is left out only when it is a bare value that the turns do not state, or
working with an amount they do not state, never because the checker could not follow it; working whose result is a
value the turns state for the thing is taken as that set without a question.

## Campaign 13 (2026-10-12 midday, preregistered before any result): a real-code task; the open-question fix

### Part A: the repair marathon (first run of this task; a pilot, one seed, one run per arm)

Every result so far is on one synthetic family. This task is real code with a real test suite
(`scripts/context/make_repair_tasks.py`, its module text has the details): more-itertools 10.7.0 (MIT) with 40
injected one-token defects (a comparison turned round, plus for minus, `and` for `or`, True for False, a dropped
`not`), one per function, each breaking that function's own test class and, for 39 of the 40, nothing else. The
agent gets 43 tickets one at a time from `next`: 40 BUG tickets ("`chunked` in more.py gives wrong results; its
tests: `t ChunkedTests`") and three NOTICE tickets, each a standing instruction "from now on":

- ticket 3: every line added or changed in the library ends with the comment `# fixed`;
- ticket 9: after each fix, one line in `/app/FIXES.md`: ticket, function, a few words;
- ticket 16: only for fixes in `recipes.py`, the function's name also goes into `/app/RECIPES.txt` (a rule by
  condition: 10 of the 40 defects are in `recipes.py`, all placed after this notice; listing a `more.py` fix there
  breaks the rule too).

The grader restores the original tests, runs each ticket's test class against the agent's library, and checks each
instruction for every ticket after its notice: a ticket is *fixed* when its tests pass and *clean* when it is
fixed and no instruction in force was broken for it. Built and checked before any model saw it: a self-test builds
the image, runs `next` through the queue and `t` once, and grades six scripted solutions whose scores are known
(untouched 0 fixed; correct 40 clean; no notice followed 2; no FIXES.md 7; no RECIPES.txt 30; everything in
RECIPES.txt 23), and a stub model has driven it through the harness. The builder was reviewed read-only before its
first run (11 findings, among them a host-memory risk: every test process is now capped).

Arms, the same plain agent in each (it sends one shell command per turn; thinking on in every call, at most 8,192
tokens a reply, temperature 0), the same server:

| arm | what manages the context |
| --- | --- |
| XR | nothing in the agent: it sends its whole history through `tools/ctxkeeper` (32K window, in-place notes, checks off because this is not a ledger, RULES recited when a ticket arrives, `recall` in message numbers) |
| W32 | a 32K sliding window: the oldest turns are dropped |
| C32 | summary compaction at 32K: what agent programs usually do |

What I expect, written down before any result (a pilot can only show large differences):
- *Fixing* is local work and all three arms can do it: 30 or more of 40 fixed in each.
- *Instructions:* XR keeps the marker and the log line on 90 % or more of the fixes they apply to, and the rule by
  condition on 80 % or more. W32 keeps the marker and the log line while its own last fix is still in view (habit:
  70 % or more would not surprise me) and loses the rule by condition, whose last use is usually out of the window
  when the next `recipes.py` ticket comes (50 % or less). C32 lands between the two.
- *Clean tickets:* XR 28 or more of 40; W32 20 or fewer.
- *Time:* XR within 1.3 times W32.
If W32 keeps every instruction, the task does not separate the methods and that is the finding; the next version
then spaces the tickets further apart. If XR fixes fewer than 10 by its time cap (60 minutes), the set-up is at
fault and the other arms are not run until it is understood.

### Part B: the open-question fix and the later check fixes, on the ledger streams

Code at the commit this campaign starts from: proxy arm X32q, harness arms N32p and N32pr (the harness has not run
since this morning's N32n: it now has `recall --before N` with the nearest matches, the open question kept across
the ordinary cut, no fall back for a questioned reply, misspelled names, amounts that are another thing's value).

1. X32q, rules stream, seeds 1 and 0. Gate as before: 39/39 and 45/46 or better, no failed in-place attempt.
2. N32pr and N32p, hard stream seed 1 (the pair that could not be compared this morning). Expected: both finish;
   N32pr 45 or more of 49 in 16 minutes or less (this morning 46 in 23); retrieval adds two or more answers.
3. N32p, 1M stream seed 1 (this morning 210 of 222: seven lost to the question that was cut out of view). Expected:
   217 or more of 222 in 45 to 55 minutes.
4. X32q, 1M stream seed 1 (the proxy's second 1M stream). Expected: 213 or more of 222 (96 %) in 45 to 55 minutes.

Order in the queue: part A, then B1, B2, B3, B4. Gemma is off for the length of the queue (about four and a half
hours if everything runs); the 1M runs go last and are dropped if the cards are wanted sooner.

### Campaign 13, before the first result: what changed after the preregistration

**The note checks were taken apart and made stricter (code state of part B: commits `c86efddda`, `f7c8c6961`,
`f9be77a94`).** Four more read-only reviews of the check code (Codex twice, then an opus reviewer twice, with
in-memory probes) found about twenty more inputs for which a wrong value was stored without a question, or a
correct line was thrown away. Nearly all of them came from one idea: when a packed line (`578 + 62 = 640, then set
to 174`) held a wrong sum, the checker redid the sum and read on, and every way of reading on was a guess (the next
part starts from the miscounted result; the next part repeats it; a remark in brackets held the amount). The idea
was removed rather than patched again:

- A packed line is followed only if every part gives exactly what the line says, read in a fixed order (from
  the value so far; going on from it; from a value the turns state). Otherwise it is asked about once and then
  stored as the reply wrote it. A plain line with two sums (`539 - 31 = 508 - 48 = 460`) is followed the same way
  (only its last sum used to be checked).
- One sum is still redone, as on a plain line: the last sum of a line, when it starts from the value so far,
  its amounts are stated, no remark that says more than `(item N)` stands in it or after its result, its value
  does not depend on the order of the operations, and the result it writes is not itself a number the turns
  state.
- Every question carries the index of its line, and a line that is left out after the second reply is that line
  (the filter used to take the first line of that name).
- Working with an amount the turns do not state is left out only when its result is not a number the turns state
  either (`436 + 78 = 514` for "recorded at 514" had been thrown away; `650 - 27 = 623` for "recorded at 523"
  still is).
- A sum that gives its written result only when taken from left to right (`10 + 5 x 2 = 30`) may be meant that
  way ("gained 5, then was doubled") or miscounted (`100 - 40 / 2 = 30`): asked about, then stored as written.

Known costs, accepted: a thing set to one value twice within one line costs a question; so does a line the
checker cannot follow. What the strictness costs and buys on text the model really wrote was measured, not
assumed: `tools/ctxkeeper/replay_diff.py` runs every saved first notes reply of a proxy session through the checks
of an old commit and of the working tree. Against the code that ran this morning's proxy (`9711d42d4`), over the
2,502 CHANGES lines of the 1M run and the two 240K runs, five names differ, each for the better: one silent wrong
value of the 1M run is now asked about (`563 - 376 + 53 = 429 (recorded at 376 in item 333, then +53 in item
334)` had been "corrected" to 240 without a question), one wrong last sum of a packed line is put right (543 for
a written 498), and three packed lines that were asked about are followed, two of them to a removal the old code
did not apply. (The commit message of `f9be77a94` says "two silent wrong values"; one is the right count.)
Questions asked: 14 of
75 cuts on the 1M stream (13 before), 2 of 17 on each 240K stream (as before). Tests: 51 harness, 66 proxy, the
flow check's 8 cases.

**The first start of part A (11:32) was stopped by the memory guard after 40 seconds; nothing was measured.**
The second ticket's defect makes `ichunked` never stop. At its 13th command the agent ran `t IchunkedTests`; the
test process grew by 70 MiB a second towards its cap of 800 MiB, host memory fell from 2.19 GiB available to the
guard's floor of 1.6 GiB in nine seconds, and the guard stopped the server (`MEMORY-GUARD.json`: "available host
memory fell to 1.58 GiB"). The runner saw the server gone, ended the queue and put the Gemma service back by
11:41. The builder's review had asked for a cap and got one; nobody asked whether the cap was smaller than the
room beside the server (about 0.55 GiB). The reference suite (671 tests in 156 classes) passes class by class
under 96 MiB of address space, so the caps are now 128 MiB for a test process, 160 MiB for any shell the agent
starts and 384 MiB for the container (were 800 MiB, 1.5 GiB, 2 GiB), and the builder's self-test runs under the
same 384 MiB without swap. Measured in the rebuilt image: the same test ends in 2 seconds with the container's peak
at 130 MiB; a runaway the agent could write itself peaks at 154 MiB. The task was rebuilt from the same screened
mutations (tickets, spec and library byte-identical; the six self-test scores unchanged), commit `9f687860f`.
The stopped attempt is kept beside the results (`client-repair/runs/jobs/XR__repair-n40-s0.guard-stop-1135`,
`server/tp2-w262144-c13.attempt1`). Restarted at 11:42 with the same queue.

### Campaign 13, part A results: the repair marathon (one seed, one run per arm, 2026-10-12 11:44 to 13:20)

Task `repair-n40-s0` (rebuilt with the small caps, otherwise as registered). Same server session for all three
arms, no restart; lowest host memory available in the three runs 1.95 GiB (floor 1.6), container peak 139 MiB.

| arm | fixed | clean | marker (R1) | log line (R2) | rule by condition (R3) | minutes | model calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| XR: plain agent through the proxy, in-place notes | 40 | **40** | 38/38 | 33/33 | 27/27 | 37.8 | 268 (+17 by the proxy) |
| W32: 32K sliding window | 40 | **30** | 36/38 | 33/33 | 17/27 | 29.3 | 245 |
| C32: summary compaction at 32K | 40 | **40** | 38/38 | 33/33 | 27/27 | 28.5 | 256 (+6 summaries) |

Against what was written down beforehand:

- *Fixing is local work and all three can do it (30 or more each):* yes, 40 of 40 in every arm.
- *XR keeps the instructions (28 or more clean):* yes, all 40, every instruction on every ticket it applied to.
- *W32 keeps the often-used instructions by habit and loses the rule by condition:* yes in kind, not in size. The
  marker and the log line survived the loss of their notices (which left its view during tickets 11 and 17) on 36
  of 38 and 33 of 33: each fix it could still see showed it what to do. The rule by condition was lost on every
  ticket where it asked for something: its notice left the view four model calls before the first `recipes.py`
  ticket arrived, and from then on W32 wrote its FIXES.md line into RECIPES.txt as well (`23 | subslices | slice
  endpoints ...`) instead of the function's name: 0 of 10. It remembered that there was such a file and when it
  applied (its own recent turns said so) but not the form, and nothing in view could correct it. I had expected 20
  or fewer clean; it was 30, because the other two rules held better than I thought.
- *C32 lands between the two:* no. It kept everything, and it was the fastest. Six summaries, the view never over
  19.7K tokens.
- *XR within 1.3 times W32's time:* 1.29, so barely, and it is a third slower than C32.

So on this task, at this length, **the proxy is as correct as summary compaction and slower; both beat the plain
window, and what the plain window loses is exactly the instruction that is used rarely and has a form to get
wrong.** Two things qualify the comparison and set the next runs:

1. *The task is short.* The whole XR conversation is 538 messages, about 100,000 tokens: three windows. At that
   length six summaries are enough for a model that is told to keep instructions. The ledger streams, where
   summary compaction fell far behind, are 8 to 30 windows long and ask about old values; this task never asks
   about old work. The next build adds a last ticket that does (`--audit`: ticket number and function of every
   fix made before FIXES.md existed, which nothing on disk holds).
2. *Where XR's extra nine minutes went* (server totals per arm from the sampler):

   | | requests | read, not cached | seconds reading | written | seconds writing |
   | --- | ---: | ---: | ---: | ---: | ---: |
   | XR | 285 | 587K | 217 | 178K | 1,965 |
   | W32 | 245 | 774K | 314 | 117K | 1,376 |
   | C32 | 262 | 629K | 240 | 128K | 1,409 |

   Reading is no dearer through the proxy (it is the cheapest of the three: after a cut the view is small). The
   difference is 50,000 more tokens written, and most of them were thrown away. The agent's own replies are 97,850
   tokens; nine good notes replies about 22,000 (four fifths of that is thinking); of the remaining 58,000 or so,
   about 45,000 are six replies in which the model thought up to the cap of 8,192 tokens and wrote nothing: three
   ordinary turns (the proxy asks again without thinking, as designed) and one notes call three times over
   (in-place try, its retry with thinking still on, and the first try of the full rewrite; fixed since, commit
   `199ed4657`: an empty notes reply is tried again without thinking). The last 13,000 I have not attributed.
   Notes for a coding task do not need the arithmetic care the ledger needed, so the next run also tries the
   notes call without thinking at all.

The proxy's notes on real code read well without any change to the request text: the three notices word for word
under RULES, one STATE line per ticket (`ticket 24 (polynomial_eval, recipes.py line 1118): fixed & verified ...`),
the early tickets folded into one line by the model itself, 6.7K characters at the end. No `recall` was made.
Proxy code of this run: commit `9f687860f` (notes checks off). Evidence: `client-repair/runs/jobs/{XR,W32,C32}__repair-n40-s0`,
`proxy-state/c13-XR-repair-n40-s0`, `metrics-c13.tsv`, `campaign13.log`.

### Campaign 13b (preregistered 2026-10-12 13:30, before any result): the repair task on a second seed, with an audit

Task `client-repair2/tasks/repair-n40-s1`, built with `--audit` from the same screened mutations: other defects in
another order (first `recipes.py` ticket is 17, right after its notice at 16; then 25, 28, 29, 31, 33, 34, 35, 41,
43), and a 44th ticket that asks for `/app/AUDIT.md`: `<ticket number> | <function name>` for the seven BUG
tickets before the FIXES.md notice (1, 2, 4, 5, 6, 7, 8). The audit is graded apart from the score.

Arms, same agent and server as part A:

| arm | what manages the context |
| --- | --- |
| XR3 | the proxy at today's code (`47fa9ae60` or later), as XR but with the notes call made without thinking |
| W32 | 32K sliding window |
| C32 | summary compaction at 32K |
| XR2 | as XR (notes with thinking) at today's code; run only if XR3 loses an instruction or audit lines |

What I expect:
- *Fixing:* 36 or more of 40 in every arm.
- *XR3:* 36 or more clean; time within 1.1 times C32's (the notes call without thinking writes a fifth as much);
  audit 6 or 7 of 7.
- *W32:* this seed is kinder to it on the rule by condition: its first use comes while the notice is in view, and
  the later uses are close enough together that each can see the one before. I expect it to keep the form on 7
  or more of the 10 `recipes.py` tickets; if so, part A's 0 of 10 was where the first such ticket happened to
  fall, and that is worth knowing. Audit: 2 or fewer of 7 (the turns are gone and nothing on disk maps ticket
  numbers to functions).
- *C32:* clean 36 or more. Audit is the open question: whether six rounds of summaries keep which ticket fixed
  which function at the very start. My guess is 4 or more of 7.
- If XR3 and C32 tie on everything again, the conclusion for code tasks of this length is that summary compaction
  is enough and the proxy's case rests on longer histories and on questions about old detail; the next task then
  has to be several times longer, not another seed.

After the repair arms the queue runs the two 1M ledger lines that campaign 13 gave up for this (N32p and X32q on
the second 1M stream, as registered under part B, items 3 and 4); they are dropped if the cards are wanted sooner.

### Campaign 13, part B results so far (2026-10-12 13:20 to 14:15), and one more pair registered before it runs

Code state for these runs: `47fa9ae60` (the note checks after six reviews).

| run | result | time | notes calls | |
| --- | ---: | ---: | --- | --- |
| X32q, rules stream, seed 1 | 46/46 | 9.5 min | 17 cuts in place, 0 failed, 2 asked again | gate met |
| X32q, rules stream, seed 0 | 39/39 | 8.8 min | 17 cuts in place, 0 failed, 3 asked again | gate met |
| N32pr, hard stream, seed 1 (keeper + retrieval at questions) | 45/49 | 22.5 min | 42 calls for 16 in-place cuts; 11 lines left out | expected 45 or more in 16 min: score yes, time no |
| N32p, hard stream, seed 1 (keeper alone) | 48/49 | 14.0 min | 34 calls for 14 cuts; 1 line left out | finished (this morning's N32n did not) |

*The gate holds with the rewritten checks*, at this morning's speed (X32p: 8.5 and 9.4 minutes).

*The hard-stream pair does not show what it was run to show.* "Retrieval adds two or more answers" came out the
other way round: the keeper alone scored three more and was eight minutes faster. But the two runs differ mostly in
something else. On this stream the text says changes without numbers ("was doubled", "a third written off",
"received exactly what sajaro19 stood at then"), the model writes them as `520 -> 1040` or `849 - 283 = 566`, and
the checks, which want every new number either stated in the turns or shown with working whose amounts are stated,
asked about them at nearly every cut (40 questioned lines in N32pr, 21 in N32p, of 46 and 28 in all). After the
second reply the "leave out what the turns do not state" rule then threw away 11 lines in N32pr, right ones among
them (`yoyo70: 493 -> 549 (received exactly what sajaro19 stood at then)`, three lines of `kedo72` in a row), and
1 in N32p. Which run lost lines was a matter of how the second replies happened to be written. So the count of
answers says more about that rule than about retrieval, and the pair has to be run again on checks that can follow
such lines.

**Code state h** (commits `8ab078fc2`, `03ff28ce2` and the one that carries this paragraph; arms N32h, N32hr,
X32h): a line without working is followed when some sentence of the turns names the thing without stating any
number and the new value is the old one times 2..10, the old one with a whole fraction of itself added or taken,
what another thing of these turns holds, or the old one with such a value added or taken; a fraction of the
starting value also passes as an amount in working, under the same condition. A read-only review of the first
version found eight ways in which it let a wrong value through (the part written for the remainder, a set read as
a gain, a value the thing held earlier in the reply written again); the rule was narrowed until each of those is
asked about again (tests). It is a loosening all the same: on this stream nearly every counter is named in a
sentence without a number, and for small values many numbers are "a fraction of itself". What it costs is measured
by the notes audit, not assumed. `replay_diff.py` against `47fa9ae60` over 3,299 real lines of the rules streams:
no name differs, so the gate runs are not affected.

Registered before the run, hard stream, seed 1:
- N32h (keeper alone): 46 or more of 49 in 14 minutes or less; 25 notes calls or fewer (34 before); 2 lines or
  fewer left out; the audit of its saved NOTES shows no more wrong values than N32p's.
- N32hr (with retrieval at questions): 46 or more of 49 in 20 minutes or less; 3 lines or fewer left out.
- If N32hr again scores no more than N32h, "retrieval at question time adds answers on indirect text" is withdrawn:
  three of four comparisons would then be within one answer or against it.

**Correction at 14:45, while N32h was running.** I had read "received exactly what sajaro19 stood at then" as "is
set to that value", because that is how the model's own lines read it (`mizike76: -135 -> 458 (per NOTES, dico82 =
458)`), and the first committed version of code state h (`42df34618`) accepts another thing's value as the new
value. The generator means an increase by that value (`make_sparse_prose_tasks.py`: "went up by as much as {s} held
at that moment" and this sentence are two wordings of one operation), and the task statement says so ("increased
by as much as another counter holds"). So (1) several of the eleven lines that N32pr "wrongly" left out were the
model's misreading, which the old checks had rightly questioned: the leave-out rule did less harm there than the
paragraph above says, and how much is for the audit to show; (2) N32h runs with a rule that lets that misreading
pass without a question, and its result is reported as such, not as the test of the idea; (3) the rule is
corrected (the other thing's value counts only as the amount added or taken), registered as arms N32g, N32gr and
X32g, and N32hr was taken off the queue before it started. What was written down for N32h and N32hr above now
stands for N32g and N32gr.

### The checks scored against the true ledger (2026-10-12 15:00; no cards needed)

Six reviews had been finding inputs for which the checks would store a wrong value. None of them could say how
often the model writes such a line, or what the wrong values that do get through look like. The proxy saves every
notes reply, and the streams come with the true value of every counter after every item, so the question can be
put directly: `tools/ctxkeeper/check_score.py` applies the first reply of every cut to the NOTES the run held
before it, with the checks of any commit, and sorts each counter the reply writes into accepted and right,
accepted and wrong, asked about and wrong, asked about and right (counters whose value was already wrong before
the cut are set aside). Five saved runs on the rules streams (X32p: two 240K streams and the 1M stream; X32q: the
two 240K streams), 2,006 counter lines, fifteen seconds:

| checks of | accepted, right | accepted, **wrong** | asked about, wrong | asked about, right |
| --- | ---: | ---: | ---: | ---: |
| `33d6588d4` (yesterday) | 1,958 | 5 | 9 | 34 |
| `9711d42d4` (this morning's proxy) | 1,961 | 5 | 9 | 31 |
| `47fa9ae60` (after the rewrite and six reviews) | 1,966 | 4 | 7 | 29 |
| `a7f76c8c1` (two rules from this table) | 1,967 | 0 | 10 | 29 |

What it shows:

- The model's first reply is wrong on about 11 to 14 of 2,006 counters (0.6 %); the checks ask about two thirds of
  those and about 1.5 % of the right ones. All of the wrong ones are in the 1M run; the four 240K runs have none.
- A day of rewriting and reviewing moved the silent wrong values from 5 to 4. It did real work on lines that were
  being asked about needlessly or stored wrongly after a question (three wrong became right), but the reviews'
  probes were not where the remaining wrong values were.
- The four that every version let through are two habits. Three are a set written as a sum, with a remark that
  says so: `lodo77: 173 + 549 = 722 (set, item 373)` (true value after that item 549; all three in one reply).
  The sum is right and its amount is in the text, so nothing fired. The fourth was made wrong by the checker:
  `tudi76: -87 - 71 = -16` has the right result and one wrong sign in the working, and the sum was "corrected" to
  -158.
- Two rules follow (`set_written_as_a_sum`, `one_sign`): a sum whose remark says set / recorded / opened and
  whose result the turns do not state is asked about; a sum that gives its written result with the sign of one
  amount turned round is read that way. On these replies: no silent wrong value left, no question more.

That last row is fitted to the lines it is scored on and proves nothing by itself. The replies of campaign 13b
(X32g on the rules stream, on the hard stream and on the second 1M stream) are the first that these rules have
not seen, and the same tool scores them. The hard stream had no proxy run before; X32g replaces N32gr in the
queue for that reason (retrieval at question time is set aside: in N32pr the retrieved sentences sit among the
turns being noted, and whether they are counted as mentions there has not been looked at).

The lesson for this lane: when there is ground truth and the replies are saved, measure the checker against it
first; ask reviewers for probes second. The tool also works for any future stream that has a reference.

**The promised fresh-text check (2026-10-13 evening, while campaign 16 runs):** X32g's three saved sessions (the
rules 240K, the hard 240K and the second 1M stream's seed 1; 1,435 counter lines scored, 12 set aside) under the
checks of the two commits of the table above:

| checks of | accepted, right | accepted, **wrong** | asked about, wrong | asked about, right |
| --- | ---: | ---: | ---: | ---: |
| `47fa9ae60` (before the two rules) | 1,345 | 2 | 10 | 78 |
| `a7f76c8c1` (the two rules) | 1,387 | **1** | 11 | 36 |

The rules generalize: on text they were not fitted to, silent wrong values halve (2 to 1) and needless questions
drop from 78 to 36, with one more catch. The line that still gets through (`sajagu11`, items 266-272 of the second
1M stream) is the hard remainder: the reply kept the old 510 with a round trip of working (`510 - 52 = 458`, then
`458 + 52 = 510`) while the true value after those items was 145 — the items that set it are not in the reply's
working at all, so no arithmetic check can see it; only a check that every item in the span was accounted for
could. A rule for it would now be fitted to 3,441 lines and would await its own fresh text; that is the standing
loop from here — every proxy run's streams are scored before the rules move again.

### Campaign 13b, a change to the task before any arm has finished on it (2026-10-12 15:20)

The first arm on `repair-n40-s1` (XR3, started 14:50) was stopped by hand after 27 minutes: it had fixed four
tickets in four minutes and then spent 23 minutes on the fifth, `combination_with_replacement_index`, by then
rewriting the function from nothing instead of looking for the one wrong token (eleven replies thought to the cap
and came back empty). That is the function that took every arm of part A between 3 and 11 minutes as ticket 22
(644 s, 188 s, 540 s; no other ticket took all three arms more than a minute or two). As ticket 5 of 44 it decides
the whole run inside a 60-minute cap, for whichever arm happens to dig in, and none of that has to do with how the
context is managed. The builder can now leave functions out of the pool (`--exclude`), and the three arms run on
`repair-n40-s1x` instead: seed 1 again, built with `--audit --exclude combination_with_replacement_index` (other
defects in another order: the exclusion changes the draw; first `recipes.py` ticket 17, then 22, 23, 24, 29, 33,
34, 38, 41, 42; the audit asks for tickets 1, 2, 4, 5, 6, 7, 8). It was written beside the running server without
its self-test, which starts containers (`--no-selftest`; the builder, grader and scripts are the ones whose
self-test passed on `repair-n40-s1` an hour earlier); the self-test is run on the same folder once the cards are
free and reported with the results. Arms, caps and what I expect are as registered above. The stopped attempt is
kept (`client-repair2/runs/jobs/XR3__repair-n40-s1`).

### Campaign 13c, registered 2026-10-12 16:15 (after XR3 on `repair-n40-s1x`, before W32 and C32 have finished)

XR3 on `repair-n40-s1x`: 40 fixed, 40 clean, audit 7 of 7, 47.1 minutes (the other two arms are running; the
table comes with them). Two things in that run set up one more arm:

- The notes call without thinking costs almost nothing: 13 cuts wrote 4,892 tokens in all (46,816 in part A's XR
  for 10 cuts) and no cut failed. It keeps the notices word for word; its STATE is thinner (it keeps one line
  called `ticket` and overwrites it, where the thinking model kept a line per ticket), and the audit was answered
  with one search of the archive, all seven lines right.
- Half the run was the model thinking to its limit: 15 of 319 calls took more than a minute each and 1,318 of the
  2,746 model seconds between them; eleven replies came back empty after 8,192 tokens of thinking and were asked
  for again. The server wrote 234,000 tokens in this arm and the agent received 139,000. One ticket (`peekable`,
  the 37th) took twelve minutes that way. This has nothing to do with the context method, every arm has it, and
  the ledger arms do not, because they run at `reasoning_effort=medium`. The proxy can set that for a client that
  does not (`--effort medium`: it adds the field to every call it forwards).

**XR4** = XR3 with `--effort medium` on the proxy, on `repair-n40-s1x`. Expected: 36 or more clean, audit 6 or 7 of
7, and 35 minutes or less (three quarters of XR3's time); fewer than 30,000 tokens written and thrown away. If it
is not faster, effort is not what bounds the thinking on this model and the cap on a reply's tokens is the next
thing to try. It is a setting of the model, not a way of managing context: W32 and C32 would gain the same from it
if their client set it, and a comparison at medium effort for all three is the run after this one if XR4 holds.

Then the queue runs the two 1M ledger lines on the day's final check code (N32g and X32g on the second 1M stream;
expectations as registered under campaign 13, part B, items 3 and 4). The self-test of `repair-n40-s1x` runs
between 13b and 13c, while no server is up.

### Campaign 13b results: the repair task on the second seed (`repair-n40-s1x`, 2026-10-12 15:19 to 18:07)

One run per arm, same server session. Every arm met the same two hard tickets (26 `combination_index`, 37
`peekable`), on which this model thinks to its reply limit again and again; what each arm did with that is most of
the story.

| arm | fixed | clean | marker (R1) | log line (R2) | rule by condition (R3) | audit | minutes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| XR3: through the proxy, notes call without thinking | 40 | **40** | 38/38 | 33/33 | 27/27 | **7/7** | 47.1 |
| C32: summary compaction at 32K | 40 | **33** | 31/38 | 26/33 | 24/27 | 0/7 | 60 (cut) |
| W32: 32K sliding window | not graded | | | 15 lines for 26 tickets | 4 names for 7 tickets | | 60 (cut) |

- **XR3** did everything: every fix, every instruction on every ticket, and the audit, which it answered after one
  search of the archive (its notes, taken without thinking, had kept only the newest ticket under STATE). It spent
  twelve minutes on ticket 37. Eleven replies came back empty after 8,192 tokens of thinking; the proxy asked
  each again without thinking, and the run went on.
- **C32** fixed all 40 and lost all three instructions for the last seven tickets. The cause is one summary: the
  seventh of eleven, made in the middle of ticket 37, is 164 characters long and is not a summary but one more
  step of the work ("I need to fix my experiment script (missing `__getitem__`), but more importantly let me
  re-verify the exact current state of the `_get_slice` lines before editing."). The harness took it for the
  summary, and the six good ones before it, which held the three notices word for word and the functions of
  tickets 1 to 8, were gone. The summaries after it picked the marker up again from the source and the two files
  from a listing, too late for tickets 37 to 43. At the audit ticket it had nothing to go on, read
  `/opt/repair/tickets.jsonl` (which the task forbids) and was cut at the 60-minute cap before it wrote the file.
  Graded in its live container at minute 56 (`runs/live-grade-C32__repair-n40-s1x`), because a run that the outer
  cap cuts is not graded by the harness.
- **W32** was cut at the cap without a grade: it reached ticket 37 after 21 minutes and stayed there for 39, most
  of them a loop of empty replies (nothing asks again without thinking in that arm). What its files showed when
  last looked at: FIXES.md had stopped at 15 lines when 26 tickets called for one, and RECIPES.txt held the first
  4 of 7 names (in the right form this time: the notice was in view at the first use, as expected for this seed).
  It is run again in 13c with a time limit inside the task, so that it is graded where it stops.

Against what was written down: XR3 clean 36 or more and audit 6 or 7: yes (40, 7/7). XR3 within 1.1 times C32's
time: not comparable, C32 did not finish. W32 keeps the form on 7 or more of the 10 `recipes.py` tickets: no
(it stopped keeping it, and the log line, around ticket 26). C32 clean 36 or more: no (33). C32's audit 4 or more:
no (0, and by forbidden means had it finished).

**What this adds to part A.** There the summariser matched the proxy and was faster; here it lost the
instructions and the oldest work in one step, and nothing in it could notice or undo that. That is the difference
between the two designs, shown once: a summary replaces the history, so one bad summary is the end of everything
before it; the proxy's notes are changed line by line (a reply that says nothing useful changes nothing), the
RULES section cannot lose a line, and the turns themselves stay in the archive, which answered the audit. Over
the two seeds: proxy 80 of 80 clean, summariser 73 of 80, window 30 of 40 on the one seed where it was graded.
The limits are the same as before (one model, one library, one run per cell), plus one: the bad summary came out
of a stall that this task and this model produce, and a harness that checked its summaries (length, layout) and
asked again would have caught this one. The proxy does that checking; "summary compaction as agent programs
usually do it" does not, and that is the comparison that was run.

**The task's own problems, found on the way.** (1) Three functions of the `*_index` kind and `peekable` cost every
arm between three minutes and the rest of its cap; one is excluded now and the other two decide runs. They belong
out of the pool, or the instruction should allow a ticket to be given up after so many commands. (2) The outer
time cap leaves no grade behind; the task now carries the agent's time limit itself (`--agent-timeout`, 55
minutes), and the harness grades what is there when it expires. (3) Half of the model's time in every arm is
thinking that runs to the limit; XR4 in 13c tries the obvious setting.

### Campaign 13b, the ledger runs (2026-10-12 18:07 to 18:44): the hard stream again, and the gate on the final code

| run | checks | result | time | notes calls | counters ever wrong in the saved NOTES |
| --- | --- | ---: | ---: | --- | ---: |
| N32p, hard stream, seed 1 (campaign 13) | strict (`47fa9ae60`) | 48/49 | 14.0 min | 34 for 14 cuts | 1 |
| N32h, same | first relative rule (`42df34618`) | 47/49 | 23.0 min | 28 for 14 cuts | 8 |
| N32g, same | corrected rule (`a7f76c8c1`) | 46/49 | 15.3 min | 31 for 14 cuts | 5 |
| X32g, same, through the proxy | corrected rule | 47/49 | 11.8 min | 17 cuts in place, 0 failed, 19 asked again | 5 |
| X32g, rules stream, seed 1 (gate) | corrected rule | 46/46 | 9.6 min | 17 cuts, 0 failed, 2 asked again | 0 |

What was written down for N32g: 46 or more (yes, just), 14 minutes or less (no: 15.3), 25 notes calls or fewer
(no: 31), 2 lines or fewer left out (yes: 2), no more wrong values in the NOTES than N32p (no: 5 against 1). Taken
one run against one run, the new rule bought nothing. Two things say that this is not the measure to judge it by:

- The three harness runs differ by more than the rule can explain. The count of mentions asks again at 12 of 14
  cuts in every one of them (this stream names its counters by pronoun and in passing, and the count check asks
  whenever a counter is named more often than it has lines), so the notes calls cannot fall by much whatever the
  working check does; and which of the model's misreadings ends up in the NOTES depends on what its second reply
  happens to say.
- The proxy run saved every reply, so the same replies can be put through each version of the checks and compared
  with the true ledger (`check_score.py`, 234 counter lines of the first replies):

  | checks of | accepted, right | accepted, **wrong** | asked about, wrong | asked about, right |
  | --- | ---: | ---: | ---: | ---: |
  | `47fa9ae60` (strict) | 155 | 0 | 5 | 64 |
  | `42df34618` (first relative rule: another counter's value as the new value) | 197 | 4 | 1 | 22 |
  | `a7f76c8c1` (corrected rule) | 197 | 0 | 5 | 22 |

  On identical replies the corrected rule asks about 22 right lines where the strict checks asked about 64, lets
  no wrong value through, and still asks about all five wrong ones; the first version of it let four of the five
  through, which is what the audit of N32h shows from the other side (8 counters wrong).

So the rule stays, on the strength of the controlled comparison, and the run-against-run table is kept as what it
is: three draws from a noisy process. The five wrong lines are one sentence. "X received exactly what Y stood at
then" is an increase by Y's value (the task statement says "increased by as much as another counter holds"); the
model writes it as a set to Y's value about every other time, the checks ask, and its second reply usually says
the same again; the line is then left out and the old value stays, wrong either way. All five counters ever wrong
in X32g's NOTES are this. A question that told the model what the sentence can mean would be the next thing to
try there; no check can supply the right number.

The proxy's first run on the hard stream is also its fastest on any arm: 11.8 minutes against 14 to 23 for the
harness keeper, with the same score within one answer. Retrieval at question time was not run again (see above).
The gate on the final code is unchanged to the token from this afternoon's (the replay said the rules streams
would not notice the new rules: no reply there contains what they act on).

### Campaign 13c so far, and its control (13d), registered 2026-10-12 19:27 before the control runs

**XR4** (the proxy as XR3, plus `--effort medium`: `reasoning_effort=medium` added to every call it forwards) on
`repair-n40-s1x`: 40 fixed, **40 clean**, audit **7 of 7**, **29.5 minutes** (XR3: 47.1). Expected 36 or more
clean, audit 6 or 7, 35 minutes or less: all three. Expected fewer than 30,000 tokens thrown away: no, about
57,000 (the server wrote 138,000 tokens, the agent received 78,000 and the notes calls 2,400): seven replies still
thought to the limit and were asked for again, and eight calls of 290 took 797 of the 1,703 model seconds. So the
effort setting takes more than a third off the run, and the runaway replies are still nearly half of what is
left; a smaller cap on a thinking reply, with the full cap for the retry, is the next lever (not built).

XR4 has two things XR3 did not have against C32 in 13b: the effort setting, and (as XR3) the proxy's habit of
asking again without thinking when a reply comes back empty. Neither is a way of managing context. The control:

**C32m** = the harness's summariser exactly as C32 (compaction at 32K, its own summary calls), with the proxy in
front as a pass-through that only adds the effort: a window of 262,144 tokens that the client never fills (no cut,
no notes, no `recall`), no memory note in the prompt, and `--no-empty-retry` (a new switch; a unit test checks
that the forwarded request is the client's own with the one field added). Summary calls go through it too.

Expected: it finishes inside the 55 minutes the task now allows and fixes 38 or more. On the instructions I expect
it to do well this time (36 or more clean): the summary that lost them in 13b came out of a stall that the effort
setting shortens. The audit is the open question again; its good summaries in 13b did hold the functions of
tickets 1 to 8 until the bad one, so 4 or more of 7 would not surprise me. If C32m matches XR4 on clean tickets,
audit and time, then on this task the two methods tie whenever the model's thinking is kept in bounds, and what
13b showed is the proxy's robustness to one bad compaction step, not a difference in the ordinary case. If it
loses instructions or the audit again, the difference is in the method.

W32 is being run again in 13c with the task's own time limit (graded where it stops), at the default effort, as
the row that 13b could not grade. After C32m the queue runs the proxy on the second 1M ledger stream (X32g).

**XR5**, registered with the control (19:29): XR4 plus `--think-cap 3072` (new: a call that may think is first sent
with its reply cut to 3,072 tokens; one that spent them all on thinking is asked again without thinking at the
client's own size, one that was cut inside its answer is asked again in full). Expected on `repair-n40-s1x`: 38 or
more clean, audit 6 or 7, 23 minutes or less (XR4: 29.5), fewer than 25,000 tokens thrown away, and fewer than ten
replies redone in full. The risk is on the hard tickets: a think of 3,000 to 8,000 tokens that would have ended in
the right fix is now replaced by an answer without thinking. If it costs fixes or clean tickets, the cap stays off.
Queue of 13d: C32m, XR5, then the proxy on the second 1M stream.

### Campaign 13c ended early (2026-10-12 19:57); state at the end of the day

W32's second run on `repair-n40-s1x` was not graded either. It reached ticket 26 (`combination_index`) after 13
minutes and stayed there; at minute 31 host memory available fell from 1.99 to 1.56 GiB within three seconds and
the memory guard stopped the research server (`MEMORY-GUARD.json` in `server/tp2-w262144-c13c`). What its files
showed when last looked at is what the first run showed at that point: 15 FIXES.md lines, 4 names in RECIPES.txt.
The room beside the server was 0.36 GiB at that moment and the task container may use 0.38 GiB: the container's
cap is still larger than the room, which is the morning's lesson a second time at a tighter margin (the per-process
caps held; what the agent ran in those seconds is not known, the trial was not saved). Before the next run beside
the server the container goes to 256 MiB, and the runner should refuse to start an arm when the room is under
twice the container's cap.

The kill left a fault line and an engine reset on card `e3:00.0` in the kernel log (page faults at the teardown
of a compute job that was running when the container was killed; no "wedged" or failed-reset line after it). The
runner does not put the Gemma service back after a fault line, by design, so **the Gemma LAN service is down** and
the cards are idle; nothing was restarted by hand. Campaign 13d (C32m, XR5, the proxy on the second 1M stream) is
registered and generated (`longrun-campaign13d.sh`, `QUEUE13D.txt`) and has not been started.

Campaign 13d started 2026-10-12 21:16 EDT. The owner supplied the sudo password file and left the restart to the recorded recommendation: Gemma was restarted first as the post-fault health check, answered a real request correctly with a clean kernel log, and the campaign then stopped it gracefully itself. The 19:56 fault latch is preserved as `server/FAULT-20261012-c13c.json` (the launcher only checks for `FAULT.json`). The first launch attempt at 21:10 refused on that latch and restored Gemma; the relaunch is the run of record.

Before the next run beside the server (2026-10-12 20:15, no GPU work): the repair task container is now capped at
**256 MiB** (`memory_mb` in the three generated `task.toml` files and in `make_repair_tasks.py`; the suite passes
class by class under 96 MiB) [correction, found 2026-10-13: only the generator was changed that evening; the three
task directories kept 384 MiB until campaign 14, so 13c and 13d ran at 384], and the 13d runner refuses to start an arm while the room beside the server
(MemAvailable minus the 1.6 GiB guard floor) is under twice the cap. 13d then waits only on the owner: the Gemma
restart after the fault line is the owner's call, and the runner needs `SUDO_ASKPASS`.

Where the lane stands:

| | proxy | summary compaction | sliding window |
| --- | --- | --- | --- |
| repair task, seed 0 (default effort) | 40 of 40 clean, 37.8 min | 40 of 40 clean, 28.5 min | 30 of 40 clean, 29.3 min |
| repair task, seed 1x (default effort) | 40 of 40 clean, audit 7/7, 47.1 min | 33 of 40 clean, audit 0/7, cut at 60 min | 22 of 40 clean, audit 0/7, 55 min (W32f, campaign 14; two earlier runs stuck and ungraded) |
| repair task, seed 1x, effort medium set by the proxy | 40 of 40 clean, audit 7/7, 29.5 min | **40 of 40 clean, audit 7/7, 20.9 min (C32m)** | |

### Campaign 13d results (2026-10-12 21:16 to 23:22; one server, no restart, kernel log clean; container cap in fact 384 MiB — see the correction in campaign 14)

**C32m, the control: the summariser at medium effort matches the proxy on this task.** 40 fixed, **40 clean** (every
instruction on every ticket), audit **7 of 7**, **20 min 55 s** — against XR4's 29.5 minutes and the same scores.
The proxy in front of it was a pass-through to the token: 0 cuts, 0 notes calls, 0 retries of its own. Five
summaries, all of them real summaries (one was retried without thinking after a thinking attempt wrote nothing);
the 164-character pathology of 13b did not occur. As registered: with the model's thinking kept in bounds the two
methods tie on this task, and what 13b showed is the proxy's robustness to one bad compaction step, not a
difference in the ordinary case. The case for the proxy rests on longer histories, questions about old detail,
and clients that cannot set the effort.

**XR5, the short first limit on thinking replies: the cap stays off.** 40 fixed, **34 clean** (the recipe-name
rule broke on 6 of its 27 tickets; the other two rules held everywhere), audit **7 of 7**, **38 min 24 s** — slower
than XR4's 29.5, not faster. About **102,000 tokens thrown away** (the server wrote 192,505, the agent received
86,435, the notes calls 4,068), against the registered 25,000; 33 replies came back empty off the 3,072-token
leash and were asked again without thinking, and **0** replies were cut inside their answer and redone in full
(fewer than ten was the bar). The registered risk happened: a think of a few thousand tokens that would have ended
in the right fix was replaced by an answer without thinking, and on the tickets where the rule by condition was in
force that answer missed the RECIPES.txt line. It cost clean tickets, so the cap stays off (registered).

**X32g on the second 1M stream: 214 of 222 (96 %), 48 minutes, no void.** By type: final lists 19/19, current
58/58, old values 57/58, who 27/28, rule 27/29, procedure 25/29. Expectations (213 or more, 45 to 55 minutes):
both met. This stream is the first text the two fitted check rules had not seen: 75 cuts in place, 0 failed, 14
asked again, 118 archive recalls, and the checks did not loosen on fresh text. The harness keeper's run on the
same stream this morning was 210 of 222 in 50 minutes; over the two million-token streams the proxy is 226 + 214
against the keeper's 228 + 210.

Server: ready in 165 seconds (warm page cache); the lowest host memory available during the runs was 2,507 MiB, so
the new room check (refuse an arm under 512 MiB of room) never came close to firing. The 1M arm's container has no
explicit cap (the repair task then carried 384 MiB; 256 MiB applies from campaign 14); its peak use beside the server stayed inside the room.
Gemma was restored at 23:22, no fault lines logged since 21:16.

Owed, in this order: the campaign-16 results (XR7's gate, C32's seed-2x row, the W200 plain-window control —
running) and staged campaign 17 (XR8's cut-depth gate, then the X24/X16 window curve); the skindeep rows for the
controls above (the repair marathon itself is published: skindeep.ai commit e5ae534, section "Real code: the
repair marathon"). Delivered since this list was written: the graded sliding-window row on the second seed (W32g,
campaign 14), the task without the trap tickets (`repair-n40-s2x`, campaign 14), and the proxy under a real agent
program (FreeAgent, campaign 15: FAp met every registered bound; a second agent is the owner's pick).

### Campaign 14, registered 2026-10-13 before any run: the window's missing grade, and the task without its trap tickets

A record correction first. The 20:15 entry above says the repair container was capped at 256 MiB for 13d; in fact
only the generator was changed that evening, and the three existing task directories still carried 384 MiB, so
13c's and 13d's repair runs ran at 384 MiB (the room check, 512 MiB, stayed conservative against that; the lowest
room seen in 13d was 2,507 MiB). All three task.toml files now carry 256 MiB, and new tasks are built with it.

The task variant the owed list asked for is built as **`repair-n40-s2x`**: seed 2 (a ticket order no arm has seen),
the audit ticket kept, and the whole trap family left out of the pool — `combination_index`,
`combination_with_replacement_index`, `permutation_index`, `product_index`, `iter_index` and `peekable`. The
self-test passes (the six scripted solutions grade to their known scores). Same 40 defects, three notices, 55-minute
agent limit, 256 MiB.

Queue (one server, repair arms only): **W32f** on `repair-n40-s1x`, then **XR6** and **W32g** on `repair-n40-s2x`.

Registered expectations:

- **W32f** (32K window, seed 1x, graded where the task's own 55-minute limit stops it — the row 13b and 13c could
  not produce): sticks again on ticket 26 (`combination_index`) or 37 (`peekable`); graded there. Fixed 25 to 37;
  clean below fixed (the recipe-name rule's notice leaves the window early); audit 0 of 7, the ticket never
  reached. The bar for the row is that a grade exists at all.
- **XR6** (the proxy at default effort on the trap-free task): 40 of 40 fixed and clean, audit 7 of 7, 40 minutes
  or less (XR3 with the trap tickets: 47.1).
- **W32g** (the window on the trap-free task): finishes the queue inside the limit — the answer to whether the
  window's seed-1x failures were the task or the method. Fixed 36 or more; clean 25 to 35 (the recipe-name rule
  still drops once its notice leaves the window; the window on seed 0: 30 of 40 clean); audit 0 to 2 of 7; 50
  minutes or less.

### Campaign 14 results (2026-10-13 09:25 to 11:44; one server, no restart, kernel log clean; containers at 256 MiB)

**W32f: the window's first grade on the second seed — and the stall was luck, not certainty.** Given the task's own
55-minute limit, the window did not stick on ticket 26 or 37 this time: it fetched all 44 tickets and fixed all 40,
and was graded where it stopped. Clean **22 of 40**: the marker rule broke on 18 of its 38 tickets and the log rule
on 18 of 33 (15 FIXES.md lines written) — both notices had long left the window. The recipe-name rule held on 21 of
27. Audit 0 of 7 (the ticket was reached; nothing about the oldest fixes was left in view). Two earlier runs on the
same seed stuck on one trap ticket and were never graded; the third attempt shows that outcome is probabilistic.

**XR6 on the trap-free task: the proxy is unchanged.** 40 of 40 fixed, **40 of 40 clean**, audit **7 of 7**,
**20 minutes 7 seconds** — against the registered 40-minute bar, and 27 minutes faster than XR3 on the seed with the
trap tickets (47.1), the difference being the thinking stalls that never happened. 8 cuts, all in place, none failed,
0 recalls; the notes calls wrote 4,370 tokens.

**W32g: the window finishes when no ticket can trap it.** 40 of 40 fixed, **35 of 40 clean** — the recipe-name rule
held everywhere this time (its notice was still in view when the recipe tickets came; R1 34/38, R2 28/33, 60 FIXES
lines for 33 fixes), audit 0 of 7, **45 minutes 25 seconds**. On seed 0 the same window was 30 of 40 clean.

What the three rows settle: the window's missing grades on the second seed were the trap tickets' doing, not a
property of the method — without them it completes the queue on both seeds, and even with them it completed once in
three tries. What does not change with the task: the window answers nothing about the oldest work (no archive), and
the proxy's clean record does not depend on the trap tickets (40 of 40 clean with them and without).

| | proxy | summary compaction | sliding window |
| --- | --- | --- | --- |
| repair task, seed 0 (default effort) | 40 of 40 clean, 37.8 min | 40 of 40 clean, 28.5 min | 30 of 40 clean, 29.3 min |
| repair task, seed 1x (default effort) | 40 of 40 clean, audit 7/7, 47.1 min | 33 of 40 clean, audit 0/7, cut at 60 min | **22 of 40 clean, audit 0/7, 55 min (W32f)** |
| repair task, seed 1x, effort medium set by the proxy | 40 of 40 clean, audit 7/7, 29.5 min | 40 of 40 clean, audit 7/7, 20.9 min (C32m) | |
| repair task, seed 2x, no trap tickets (default effort) | 40 of 40 clean, audit 7/7, 20.1 min (XR6) | | 35 of 40 clean, audit 0/7, 45.4 min (W32g) |

Owed: the proxy under a real agent program (the owner's pick); everything else registered for the repair task has
run.

### Campaign 15, registered 2026-10-13 before any run: the proxy under an agent program of our own, against the full window

The owner's answer to the open question is to build the agent program ourselves: **freeagent**
(`tools/freeagent/freeagent.py`, ~120 lines, shares no code with the test harness). One loop, one tool — a
structured `shell(command)` tool call, with a fenced bash block accepted as a fallback — a generic
autonomous-engineer system prompt, thinking on, 8,192-token replies, temperature 0. It sends its whole history on
every call and manages nothing: no truncation, no summary, no notes, and it is never told a window size. That is
the property under test.

The task is `repair-n40-s2x` unchanged (the trap-free seed 2 with the audit ticket), so the grader, the 40 defects
and the three notices are the ones already measured. Two arms, one server:

- **FAp**: freeagent through the proxy, in XR6's exact configuration (32K window, in-place notes, checks off, the
  rules recited when a ticket arrives, default effort). Expected: 40 of 40 fixed, 38 or more clean, audit 6 or 7,
  45 minutes or less (the harness client through the same proxy: 40/40 clean, 7/7, 20.1 min).
- **FAd**: freeagent direct against the server (262K window). The repair history is a few hundred thousand tokens
  at most, so it should fit whole: expected fixed 38 or more, clean 38 or more (every notice stays in view), audit
  6 or 7, 30 minutes or less (no proxy overhead). If the history does not fit, the run errors out mid-way — that
  would be the finding, and it is registered as a possible outcome here.

What the pair shows: with the proxy the same agent works at a 32K live window; without it the same agent needs the
full 262K. Equal scores put the proxy's cost beside the window's on an agent the harness never shaped.

### Campaign 15 results (2026-10-13 18:00 to 19:49; one server per launch, two launches; kernel log clean)

Both arms scored the maximum: **fixed 40/40, clean 40/40, audit 7/7** on repair-n40-s2x.

| arm | window | time | calls | prompt tokens | completion tokens | proxy session |
|---|---|---|---|---|---|---|
| **FAp** (proxy, XR6 config) | 32K | **33 min 16 s** | 287 | 2,902,995 | 137,488 | 12 in-place cuts, 562 messages archived, 1 recall, 6,264 notes tokens, 0 failed |
| **FAd** (direct) | 262K | 54 min 58 s | 276 | 29,934,764 | 125,264 | — |

Against the registrations: FAp met every bound (clean 40 ≥ 38, audit 7 ≥ 6, 33.3 ≤ 45 min); FAd met the score
bounds and missed the time bound (55 > 30 min). The miss has a named cause: freeagent returns each reply's
reasoning with the history, so the direct run's live history grew to ~215K tokens of which only ~20K was visible
work; every call re-read it (29.9M prompt tokens, 98% from cache). The proxy strips reasoning from what it keeps,
which is most of the 10.3× prompt gap; its cut/archive machinery did the rest and was exercised in full by a
client that shares no code with the harness (287 requests, 302 upstream calls, one recall against the 562-message
archive, 2 empty replies retried; the audit questions about the earliest tickets were answered 7/7). The harness client in the same proxy configuration (XR6: 221 calls,
8 cuts, 20.1 min) remains faster; freeagent makes more, smaller calls and pays the per-call proxy overhead.

What the pair shows, as registered: the same agent, the same task, the same perfect score — through the proxy at
a 32K live window in 33 minutes, or direct at the full 262K window in 55. The proxy's cost beside the window's,
on an agent the harness never shaped: −40% time, −90% prompt traffic, ±0 score.

Process notes: the first launch aborted on a corrupted sed rename in the runner (the image tag `r314` became
`r315`, the window `262144` became `262154`; fixed by hand and re-checked against the campaign 14 script). On the
second launch FAp was skipped without running — the runner smoked the proxy's port before starting the proxy;
the order is fixed in the runner and FAp ran on the third launch. Both faults are recorded in QUEUE15.txt.

### Campaign 16, registered 2026-10-13 evening before any run: cache-aligned notes, and the missing controls

**The finding that motivates it** (measured 2026-10-13 from the saved proxy states, no GPU): across the repair runs
the notes calls' share of prompt tokens served from the prefix cache swung from 84-90% (XR4, XR5) to 2-4% (XR6,
FAp) — 154K-234K prompt tokens read per run to write 2-6K of notes (XR3-s1x 227K, XR6 154K, FAp 234K).

**Narrowed cause (same evening, offline; replay harness over FAp's recorded trajectory, 297 captured calls):** the
in-place notes call is already a continuation of the conversation just served — 97% of its messages are the main
call's exact prefix, and rendered with the model's real chat template the two prompts are byte-identical for
99.95% of their length (they part only at the final generation marker). The proxy's construction is not the
problem. The miss is server-side, in how the request is handled rather than what it contains. Two suspects stand:
(S1) vLLM's reasoning path changes the tokenized prompt when `enable_thinking` is false — the notes calls run with
thinking off, the main calls with it on; (S2) the exact-prefix-cache overlay keys on something request-scoped
beyond the tokens. The flags-identical template render clears the template itself; XR4's 84% with thinking off but
`reasoning_effort=medium` on both call kinds points at the same place.

**Prepended diagnostic (before any arm; minutes, no registration needed as it claims nothing):** against the live
server, one ~19K-token prompt replayed four ways — thinking on, thinking off, a repeat of the first, and the first
with a different `max_tokens` — reading `cached_tokens` on each repeat. S1 predicts the thinking-off repeat
misses; S2 predicts the changed-`max_tokens` repeat misses; neither predicts trouble for the first repeat.

**Diagnostic result (20:44, `diag-c16.sh`/`diag-c16.json`): S1 confirmed, S2 refuted.** One real 17,231-token
FAp prompt: its repeat hit 15,808 from the cache; the same prompt with `enable_thinking` false came back 36 tokens
shorter (17,195) and hit **zero** — thinking-off renders a different token stream from the first message on; a
changed `max_tokens` hit in full (15,808), so request fields are not keyed; the real notes call (thinking off)
then hit 15,808 of 17,658 (89.5%) — once its own rendering was warm, the continuation design works exactly as
drawn. The historical spread is consistent: XR3-s1 (notes thinking on) 81%, XR4/XR5 (effort medium on every call,
which overrides the thinking flag) 84-90%, and the thinking-off-at-default-effort runs 2-12%. **XR7 is therefore
XR6 with `--notes-thinking unset`** — the notes calls carry the client's own `chat_template_kwargs` and render the
stream the main calls just warmed. No code change was needed; a regression test pins the alignment. Expected
notes-call cache share 85% or more of notes prompt tokens (the diagnostic's 89.5% is the ceiling: the request's
own tail cannot be warm); the trade registered: notes calls will think again (bounded by the 8,192-token notes cap
and the retry ladder), which is what `off` had been bought with — at 19K uncached tokens per cut it was a bad buy.

**Read:write follow-ons ranked (same evening, analysis only):** the notes path reads ~37 tokens per token written
(FAp: 233,674 / 6,264). With XR7's alignment the read is ~89% cache-warm; what remains is the count of calls.
Measured constraints: (1) **no cut is skippable** — across all 709 saved in-place notes replies (every proxy
session on disk), zero carried an empty RULES+CHANGES delta, so a "skip cuts that change nothing" heuristic would
have saved nothing on any run to date; (2) **fewer, deeper cuts are proven safe one layer down** — N32j35 (cut to
35% instead of 60%) halved the keeper's notes calls (23 to 14), kept 39/39 with one counter wrong for a stretch,
19% faster; the proxy equivalent is `--target-ratio 0.35`, registered here as **XR8 = XR7 at target-ratio 0.35**,
to run only if XR7 passes its gate (expected: notes calls per repair run 8-13 → 5-7, the same 40/40 clean and 7/7
audit, another minute or two less); (3) per-call keyword differences between call kinds are forbidden by the
cache finding — a notes-only effort flag would re-break the very alignment XR7 tests; (4) delegating notes to the
INT4 draft is parked: the stored values are checkable but the prose rules are not, and the gate is the whole
point.

**Arms** (repair task, thinking on, in-place notes, checks off, recite on tickets; server recipe unchanged):

- **XR7** = XR6 with `--notes-thinking unset`, on `repair-n40-s2x`: expected fixed 40/40, clean 40/40, audit 7/7
  (the gate; a clean-ticket loss rejects the change), notes_cached/notes_prompt 85% or more (XR6: 2.2%), 18.5
  minutes or less (XR6: 20.1).
- **XR7** on `repair-n40-s1x` at default effort: expected the same gate, 44 minutes or less (XR3: 47.1).
- **C32** on `repair-n40-s2x` (the summariser's missing seed-2x row, at its s1x settings): expected fixed 40/40,
  clean 33 or more (its s1x run lost the three notices once; seed 2x keeps the audit ticket), audit 0-7, 60-minute
  cap.
- **W200** on the 1M rules stream seed 0 (the charter's missing plain-window control at the 200K cap a dedicated
  card allows): expected to fall behind the proxy's 226/228, strongest in the last third; the measured size of the
  gap is the deliverable. 4-hour cap.

Order: XR7-s2x, XR7-s1x, C32-s2x, W200. Each repair arm's containers at 256 MiB; the memory-guard floor and the
room check stand. If XR7-s2x loses a clean ticket the change is reverted and XR7-s1x does not run.

### Campaign 17, registered 2026-10-13 evening before campaign 16 has finished: the window curve and the cut depth

Base recipe: XR7 if it passes its gate, else XR6 (denoted BASE below). All arms on `repair-n40-s2x`, thinking on,
in-place notes, checks off, recite on tickets, 256 MiB containers, the memory-guard floor and room check stand;
one run each; the server recipe unchanged.

- **XR8** = BASE at `--target-ratio 0.35` (cuts land deeper, about half as many notes calls; the harness-level
  precedent N32j35 halved them at full score). Runs only if XR7 passed its gate. Expected: fixed 40/40, clean
  40/40, audit 7/7, notes calls 5-7 (XR7 expects 8-13), one to three minutes faster than XR7-s2x.
- **X24** = BASE at context budget 24,576: expected fixed 40/40, clean 40/40, audit 7/7, more cuts than at 32K,
  runtime at most XR7-s2x + 5 min.
- **X16** = BASE at 16,384: the starvation end of the curve (the ledger harness refused `next` 121 times at 16K
  and self-edit read collapsed there). No quality bar is registered; the deliverable is the curve point and, if
  it fails, the failure mode read from the events (notes-call starvation vs. recall loss). Runtime cap 60 min.

Gate for the campaign: XR8 first (it changes the recipe); X24 and X16 are measurements and run regardless of
XR8's result, but against the recipe that won the gate.

**Campaign 16 partial result (XR7 on s2x, 21:35):** the gate holds — 40/40 fixed, **40/40 clean**, audit 7/7 —
and the notes cache read 217,152 of 237,916 prompt tokens (**91.2%**, expectation 85% or more; XR6: 2.2%). The
time bound missed: 38 min 9 s against the registered 18.5 (XR6: 20.1). The cause is in the counters: with
thinking unset-aligned, the ten notes calls generated **70,138** tokens (~7K of thinking per cut; XR6's notes
wrote ~2K). The alignment bought the read and paid for it in decode. The other way to align — XR4's recipe,
effort medium on every call, notes thinking off — hit 84-90% notes cache in campaigns 13d/14 without that decode,
but was never run on s2x. That cell is added to campaign 17 as its first arm.

**Added to campaign 17 (registered 21:40, before its launch):** **XR4 on `repair-n40-s2x`** (effort medium on
every call, notes thinking off — the cache alignment that does not think). Gate: fixed 40/40, clean 40/40, audit
7/7, notes cache 84% or more, notes written 10,000 tokens or less, 30 minutes or less (XR4-s1x: 29.5). If it
passes it is the recipe the window curve is read against; XR8 stays as registered (BASE = XR7, whose gate passed
tonight).

**XR4 on s2x (03:07): every bound met, and it is the fastest repair run on record** — 40/40 fixed, **40/40
clean**, audit 7/7, **15 min 38 s** (XR6: 20.1; XR7: 38.1), notes cache **90.1%** (99,008 of 109,869), notes
written **4,549** tokens (6 cuts; XR7's thinking notes wrote 70,138 on the same task). Effort medium aligns the
notes calls with the mains (same request fields) and keeps them from thinking: both halves of the problem solved
at once. **Change to the curve (registered as it happens):** X24 and X16 run on XR4's recipe (notes-thinking off,
`--effort medium`), not XR7's — after XR8 completes, the campaign pauses on its stop marker, the runner's
X24/X16 mapping is edited, and the campaign relaunches (completed arms are skipped by the runner). XR8 is
unaffected: it runs on XR7's recipe as registered.

**XR8 on s2x (03:36): the cut-depth gate passes — and its mechanism is refuted.** 40/40 fixed, **40/40 clean**,
audit 7/7, 28 min 53 s. But the cuts numbered **9** (XR7-s2x: 10), not the registered 5-7: the notes-call cadence
is driven by the 15K-token gather threshold, not by how deep each cut lands. The deeper cut is safe (the gate
says so) and buys nothing measurable; the read:write lever that remains is the gather threshold itself
(`--inplace-tokens`), not the target ratio.

**Incident, 03:40-03:57:** X24's first attempt was killed by hand four minutes in (to switch X24/X16 onto XR4's
recipe, as registered above). The kill removed the task's container but not the job: the agent's commands failed
instantly and it produced 1,732 archived turns in 21 minutes (XR8: 428 in 29), and the end-of-run bookkeeping
over that trajectory, beside the server, took host memory to 1.42 GiB — the server's memory guard stopped it
(graceful; exit 137; kernel log clean; Gemma restored at 03:58). The run was invalid anyway (no verifier result)
and its partials were deleted. The campaign relaunched at 04:00 with X24/X16 on XR4's recipe (XR4 and XR8 are
skipped by the runner: their results stand). Lesson recorded for the runner: an arm to be replaced must be
stopped at the queue level between arms, never by removing its container; and the room check's blind spot is
end-of-run client bookkeeping — the third time this class bites (campaign 12's summariser, 13c's cap, tonight).

**X24 on s2x (04:16, XR4's recipe at a 24,576-token window): the curve's middle point holds full quality** —
40/40 fixed, **40/40 clean**, audit 7/7, **13 min 5 s** (faster than the 32K run's 15:38; the smaller window
shortens every prompt), notes cache 90.2%, 6 cuts, notes written 4,399.

**X16 on s2x (04:46, XR4's recipe at a 16,384-token window): the starvation end, and the first imperfect proxy
row** — 40/40 fixed, **39/40 clean** (one rule-1 line wrong; R2/R3 intact), audit **7/7**, 29 min 48 s. The
registered failure mode is the one observed: **notes-call starvation** — 29 cuts (24K/32K: 6) with **zero**
in-place notes written (the 16K window never leaves the 15K-token gather threshold room), one full-rewrite
fallback failed, 2 recalls. The one clean-ticket loss is t20: the fix landed and its tests pass (6 run, 0 bad),
but one of its three changed lines missed the maintainer's marker — the standing rule from the first tickets
slipped exactly once, mid-run, while the archive still answered the audit 7/7 at the end. The curve on s2x: 32K →
40/40 in 15:38, 24K → 40/40 in 13:05, 16K → 39/40 in 29:48 — flat quality down to 24K, one-ticket degradation
with an honest signature at 16K.

**XR7 on s1x (22:11): the gate holds on the second seed too** — 40/40 fixed, **40/40 clean**, audit 7/7, 36 min 4 s
(bound: 44; XR3: 47.1). Notes calls read 175,572 prompt tokens, 160,576 of them cached (**91.5%**; XR3's notes
ran 81%), and wrote 28,286 (9 cuts). Both seeds: the change stands.

**C32 on s2x (22:44): the summariser's missing row, and it is full marks** — 40/40 fixed, **40/40 clean**, audit
7/7, 33 min 0 s (registered floor: clean 33 or more; its s1x run lost the three notices once). No summary broke
this time. The repair table's summariser column now reads 40/40 clean on both seeds.

**W200 on the 1M rules stream (02:32): the missing plain-window control, and the gap is measured.** 166 of 228
(72.8%), no void, 228 minutes. By type: final lists 24/25, current values 58/58, old values 40/58, who 15/29,
**rule 0/29**, procedure 29/29. The proxy's row on the same stream is 226/228 (X32p). The 60-answer gap
concentrates exactly where the design says it must: a 200K window slides past item 1's standing rule (0 of 29
rule answers) and loses old values and names; what fits in the window stays perfect (current 58/58, procedure
29/29). Campaign 16's four arms are the charter's control set complete: the proxy (both seeds), the summariser
(both seeds), and now the plain window at the largest cap a dedicated card allows.

### Campaign 18, design registered 2026-10-13 night before any generation: the 2M adversarial stream

The next ledger stream doubles the length and turns on every difficulty the generator has, plus one new one aimed
at the only silent-wrong class the fresh-text validation left standing (the notes reply that keeps a stale value
through a coincidental -52/+52 round trip while the real setter was never read).

Stream: 2,000,000 tokens, seed 0, memory mode, 2,000-token batches, density 3, `--words --pronouns --relative
--corrections --plans --rules --class-rule --surprise 8 --probes-every 20 --probes-k 5`, and the new
`--roundtrips 12`: twelve counters each get an ADD of -k and a later ADD of +k (net zero) with at least one SET
between them, placed so the pair spans a probe distance bin; the probes and the final list grade the true value
inside and after each decoy window (the reference ledger is exact by construction, as for every switch).

Arms (the repair gate recipe — XR7 or XR6 — denoted BASE; proxy at 32K window):

- **N2M**, the harness keeper on this stream: the comparison-table row.
- **X2M** = BASE through the proxy on this stream. Registered expectations: overall score at least 90% of the
  graded answers; silent-wrong notes (scored by `check_score.py` against the reference, the standing loop) at or
  under the 1M rate (1 in 1,435); the 12 round-trip decoys read directly from the scorer's accepted-and-wrong
  lines — the design's target is **0 of 12** slipping through; surprise audit at least 7 of 8; runtime cap 4
  hours. If a decoy slips, the next check rule is fitted against it and validated on the following campaign's
  streams, per the standing loop.

**Amended at launch (05:05, after campaign 17):** X2M's recipe is XR4's (notes-thinking off, `--effort medium` on
every call) — the winner of the repair head-to-head (15.6 min and 90.1% notes cache against XR7's 38.1 and
91.2%, both at 40/40 clean). The registration's "XR7 or XR6" choice predates that measurement. The ledger
configuration's checks (`near`), scan and recall labels are unchanged from X32g's runs.

Generation happens after the `--roundtrips` switch lands with its unit tests; the campaign launches only after
campaign 17's gate, one server, the memory floor and room check standing.

**Landed the same night:** the switch is in `make_sparse_prose_tasks.py` (decoy counters are reserved from the
quiet set to the end of the stream, so the final query reads the decoy value; four regression tests in
`test_make_sparse_roundtrips.py`, neighbouring generator tests green), and the stream itself is generated and in
place (`client-1m/tasks/sparse-memory/sparse-memory-t2000k-s0`: 993 batches, 2,000,864 tokens, 343 probes, 2,933
changes, all 12 decoys placed with windows of 123-176 batches and present in the final query). The campaign is
staged (`longrun-campaign18.sh`, `QUEUE18.txt`, `collect.sh`; arms N2M/X2M registered in the planner, which
validates both — its time estimates, 12.6 h and 23.9 h, come from the 2026-10-05 measurements and overstate: the
1M actuals ran about 50 minutes; the 4-hour caps stand).

**Attempt 1 invalid; relaunched 10:07.** The first N2M and X2M runs do not count: both were misrouted by
`second-comparison.sh`. Its proxy routing listed the X32* names one by one, so X2M's agent got the direct server
port and grew its window until the server refused a request at item ~97 (`ended_by=server_window`, 21/382); its
keeper-agent list likewise lacks N2M, which therefore ran as the plain truncating window (its 4-hour cut and the
259-answer snapshot were graded as designed, but the row is a window row, not the keeper row). The proxy itself
came up and served zero requests (its state directory is created on the first request, which is why none exists
for attempt 1). The campaign's own planning dry-run could not catch this: it checks the arm registry, not the two
routing lists. Fixed in `second-comparison.sh` (X2M joins the proxy-routed arms; N2M gets the current keeper
recipe) and checked against the resolved code paths; the invalid job directories were deleted and both arms
re-queued. Process lesson, now standing for any new arm: within the first minutes of an arm, read the job's
`config.json` and check the agent class and `api_base` against the design. The relaunch runs as the systemd unit
`ctx-campaign18.service` (the plain `nohup &` runner died with its launching shell at 10:03; the orphaned server
was stopped and the state directory set aside). One more `xe` fault line was logged during the 09:49 teardown
(e3:00.0, 09:59:26); the cards came back and the fault gate, scoped to the campaign's own start, is clear. N2M
starts after the standing gate (~10:35), X2M after it.

**N2M (13:04): the keeper finishes the 2M adversarial stream at 360/382 (94.2%)** in 173 min 41 s, run to the end
(no cap cut). By type: final lists 38/39, current values 89/98, old values 95/98, who 47/49, **rule 49/49**,
procedure 42/49; by rule condition 33/34 of the "overdrawn" questions and 327/348 of the rest. 1,737 calls
(1,407 main loop), 241K tokens written, 19.1M prompt tokens (77% from cache); 126 cuts, 330 notes calls (2
failed, 15 delta fallbacks, one sum corrected), the standing rules recited 50 times and every one kept. The
errors concentrate exactly where the stream's new teeth are: 9 current-value and 7 procedure answers wrong (the
correction/plan-switch items) against a perfect standing-rule score — the notes hold the invariants across two
million tokens; what slips is the most adversarial value tracking. Against the kinder 1M stream (228/228 for the
same keeper code) the 2M stream is the harder test by design, and the keeper's registered bar for it — set
before generation — was a finished run with the rule kept.

**X2M, second false start (13:04-13:09):** the routing fix of 10:05 was malformed — the edit produced
`[[ ... ]] || "$arm" == X2M ]]` (a command, always failing) instead of adding X2M inside the condition; the
syntax check passed and a grep count looked plausible, so X2M started direct again. The standing arm-start check
(read the job's `config.json`) caught it five minutes in; the run was killed, the line fixed and functionally
tested (X2M and the X32 arms route to the proxy, N2M/W200 stay direct), and X2M re-queued on the live campaign
at 13:09.

**X2M (15:59): the proxy finishes the 2M adversarial stream at 351/382 (91.9%)** in 169 min 9 s, registered cap
4 h. Against the registered card: overall score ≥ 90% — **met** (91.9%); the 12 round-trip decoys read from the
scorer's accepted-and-wrong lines — **met, 0 of 12** (none of the 14 accepted-wrong lines is a decoy counter,
and in the final query every asked decoy got its true value); surprise audit ≥ 7/8 — **met, exactly 7** (s5, one
old value, wrong); runtime — met. **Missed:** silent-wrong notes at or under the 1M rate — 14 accepted-wrong of
1,825 note lines (1 in 130; the 1M bar was 1 in 1,435). The 14 are all arithmetic slips on the adversarial
constructs — thirds, fractions, cross-counter references ("received what gupe37 stood at") — the class the
provenance checks do not see; none is a planted trap. Per the standing loop, the next check rule is fitted
against these lines and validated on a following campaign. One extra observation from a mid-window pass over the
notes history (not the registered metric): 4 of the 12 decoys sat at their decoy (pre-minus) value for three to
five consecutive notes versions before catching up — lag, not capture: by the final query every decoy carried
the truth.

By type, keeper (N2M) against proxy (X2M) on the same stream: final 38/39 both; current 89 vs 91; old value 95
vs 87; who 47 vs 48; rule 49 vs 48; procedure 42 vs 39. The proxy's 9-answer gap concentrates in old values —
recall quality at 2M, not rules (48/49 both ways on the standing rule; 33/34 of the "overdrawn" condition both).
X2M's cost: 1,211 calls, 125K tokens written in the main loop, 131 cuts (129 in place), 870 recalls, notes calls
read 6.34M tokens of which 89.2% came from the prefix cache — the XR4 recipe's alignment holds at 2M. Host
memory never went under 1.98 GiB; the kernel log is clean from campaign start to teardown; the runner's Gemma
restore at 16:10 found a clean kernel log but the service is a system unit and the runner has no sudo password —
the Gemma LAN service is down until the owner starts it (`sudo systemctl start
gemma4-26b-q8-quad-backends.service gemma4-26b-q8-quad-frontdoor.service`).

### The next check rule, fitted offline (2026-10-14, CPU-only; no GPU job ran)

Per the standing loop the first rule against campaign 18's 14 accepted-wrong lines is fitted and regression-checked
against the saved sessions. Of the 14, five are one class: **a third lost from a negative value, moved away from
zero** — `-129 - 43 = -172` for "lost a third of its value" (true `-129 + 43 = -86`; the generator's `third` op is
`state -= state // 3`, which always moves toward zero for negatives). The amounts check passes the 43 fairly (a
third of the start); the direction was never checked. The new rule (`third_loss_away_from_zero` in
`tools/ctxkeeper/notesdelta.py`) fires only when the NOTES hold a negative start, the line's own remark names the
fraction ("a third"), and the working subtracts `|start|/3`; the reply is then asked about with the toward-zero
rule spelled out. A stated-amount loss ("lost 15") does not match the phrase and stays untouched.

On X2M's saved replies (the fitting ground): accepted-and-WRONG **14 → 9** (all five fraction-direction lines now
asked about), accepted-and-right 1,376 unchanged, asked-about-and-right 393 unchanged, left-out 130 unchanged.
Against the code before the rule (1a60d6efd), every other saved proxy session the scorer can read gives identical
counts — nine sessions: the 240k pairs of X32n, X32n2 and X32q, X32g's 240k seed 1, and both 1M streams (X32n2-s0
and X32g-s1: 2,043 right, 2 wrong, 18 asked-right combined). The campaign 8-9 sessions predate the proxy's event log
and campaign 11's give the scorer no lines, so those cannot be checked this way. (The first version of this
paragraph said "every other saved session" after four had been run; the other five were run in the same day's
review.) The same review fixed the question the rule sends back: it read "a third of -129 is -43: add it", which
invites the very mistake; it now spells out the toward-zero sum (`-129 + 43 = -86`). The first commit also broke
the copy check: `notesdelta.py`'s checks are copied from the harness keeper (`clm_keeper.py`, tool
`sync_notesdelta.py`) and the rule had been added to the copy only. It now lives in the harness and is synced, so
the keeper arms get it too; one harness test whose example was this very mistake (`-93 - 31 (a third) = -124`,
accepted) now expects a question, and the remark-parsing it was written for is tested on a positive value. Proxy and
harness tests: 69 and 54, all passing. The nine
remaining accepted-wrong at 2M are the cross-counter staleness class ("received what gupe37 stood at", read stale)
and singletons (a "no change" claim against prose that states a number in words; a fraction-sum slip). Those need
value-at-time alignment, not another arithmetic rule, and stay open for the following campaign.

### Record correction and the Gemma restart (2026-10-14 evening)

The campaign 18 record above names one fault line at the attempt-1 teardown (e3:00.0, 09:59:26). The kernel log
holds more: at 09:59:26 both cards logged engine-memory CAT errors with fault responses (03:00.0 a compute-engine
reset, e3:00.0 a copy-engine reset), and at 10:05:48, when the orphaned server was stopped, 03:00.0 logged
"Schedule disable failed to respond", a GT reset and a devcoredump. The coredump was not copied before it expired,
so no evidence folder exists for it. Nothing followed: N2M and X2M ran about six hours afterwards with a clean
log, and the log is still clean. The owner then gave sudo for the Gemma system units; the LAN service was started
at 19:51 with the installed throughput recipe (8 x 4K slots per card), both cards loaded in about 25 s each, the
production health check passed and http://192.168.2.45:8000 answers. No fault line during or after the load.

### The cross-counter check: tried offline and closed (2026-10-14 evening, CPU-only)

Four of the nine silent-wrong lines left at 2M took another counter's value ("received exactly what gupe37 stood
at then") with the wrong amount. The check tried: when the turns or the line's remark say a thing took another
thing's value, the amount must be one that other thing held in the NOTES (before or during the reply) or one the
turns state for either. Replayed on X2M against the committed code: **0 of the 9 caught, 5 right lines newly
questioned** (accepted-and-right 1,376 → 1,371); the nine other readable sessions unchanged. Why: in the wrong
lines the NOTES already held the stale value of the source, so the copy agrees with the NOTES; in the questioned
lines the model had read the source's value at that moment from the turns, which the NOTES did not hold. A check
against the NOTES cannot separate the two. Reverted; the attempt is kept as
`patches/ctxkeeper-took-value-check-rejected-20261014.patch` with a DO-NOT-REPEAT row. What would catch this class
is the source's value at the item where it is taken, i.e. a per-item value history the notes do not keep; that is
a design change, not a check, and is not worth building for 4 lines in 1,825 on a synthetic construct.

### Campaign 19, registered 2026-10-14 before any run: the release gate for ctxkeeper 1.0.0

The proxy is packaged for others (`tools/ctxkeeper`: version 1.0.0, `pip install` from the public repository, a
Dockerfile, `--recipe agent|qwen`, a user README, `examples/long_chat.py`). The gate runs **what the README tells a
user to run**, installed the way a user installs it (pip from the public GitHub URL into a fresh venv; the Docker
image built from the same commit), against the research server of the campaigns (two-card FP8, 262K window,
recipe unchanged). Gemma is stopped for it and restored after.

- **G1, freeagent + `ctxkeeper --recipe qwen`, nothing else** (no `--recite-when`: a user does not know a task's
  ticket pattern), on `repair-n40-s2x`. Closest measured rows: XR4 (harness client, recite on tickets) 40/40 clean,
  7/7, 15.6 min; FAp (freeagent, XR6 configuration, recite on tickets) 40/40, 7/7, 33.3 min. Expected: fixed 40/40,
  clean 38 or more, audit 6 or more, 45 minutes or less. If clean falls under 38, the README recommends
  `--recite-when` for tasks whose instructions arrive in tool results, and says what was lost without it.
- **G2, `examples/long_chat.py` through the Docker image** (`--recipe qwen`, client thinking off), 300,000 tokens:
  more than the server's own 262K window. Expected 4/4 checks (codename and starting budget from the first
  message, current budget, standing rule kept).
- **G3, the README's OpenAI SDK snippet** through the pip-installed proxy: one plain reply and one tool call come
  back in the SDK's types.
- **G4, after the server is down: another model and server family.** Gemma 4 26B Q8 on llama.cpp (the LAN
  service, switched to its `balanced` recipe, 16K per request), `long_chat.py` through `ctxkeeper --recipe agent
  --budget 16384 --inplace-tokens 6000` at 100,000 tokens. No quality bar is registered (a first smoke test of a
  second model); the result decides whether the README may say "smoke-tested on llama.cpp". Gemma returns to its
  `throughput` recipe afterwards.

#### Campaign 19 run log

- **First attempt (c19), 2026-10-14 20:39: G1 void, not a result.** The server came up at 20:42:01 with 1.83 GiB of
  host memory free; a model download running beside it (`hf download`, about 1 GB resident) took the rest, and the
  server's memory guard stopped it at 1.50 GiB (floor 1.6) as G1 began. The agent's requests failed and it ended
  after 4 calls (1/40 fixed); the proxy had made no cut. G2 and G3 were skipped by the runner (server down); the
  kernel log was clean, so G4 ran on Gemma as registered. The runner now refuses to start while a `dl-*` download
  unit is active, and takes `RUN`, `G1JOB` and `SKIP_G4` so G1-G3 rerun unchanged as **c19b** once the download
  has finished.
- **G4 (c19), Gemma 4 26B Q8 on llama.cpp, `--recipe agent --budget 15360 --inplace-tokens 6000`: 4/4 in 4 min 28 s.**
  The runner passed `--budget 15360`, 1,024 under the registered 16,384, so a request plus the size estimate's error
  stays inside the 16K slot. `long_chat.py` at 100,000 tokens (50 reports; the history reached 101,671 tokens, 6.6
  times the view): codename VIOLET BEACON, current budget 7,812 ending in ROGER, starting budget 7,942 (said only in
  the first message, before 16 cuts). Proxy: 16 cuts, all in place, none failed or asked again, 97 messages
  archived, 0 recalls (the notes held the starting budget), notes read 132,140 prompt tokens of which 85,666 came
  from the server's cache, 422 tokens of notes written, 3.23 characters per token. The README may say
  "smoke-tested with Gemma 4 26B on llama.cpp": one run, one seed, an easy check, not a measurement.
- **Second attempt (c19b), 20:54: void, my error.** 44 s into the server's start, a one-off script of mine reading a
  GGUF file's header (beside the server) misparsed it and allocated without bound; host memory fell 0.5 GiB per
  half second and the guard stopped the server at 1.48 GiB before it was ready. Nothing ran. The rule already in
  force (nothing beside a starting or running research server) applies to one-off reads too. Rerun as **c19c**.
- **Third attempt (c19c), 21:03-21:46: G1, G2 and G3 pass; the gate is met.** Server ready at 21:05:44 with 3.25 GiB
  free (min 2.51, median 2.58 GiB over the run; nothing else on the host); kernel log clean; Gemma back on
  `throughput` at 21:46 (health check passed).

| Check | Registered | Result |
| --- | --- | --- |
| G1 freeagent + `ctxkeeper --recipe qwen`, no `--recite-when` | fixed 40, clean >= 38, audit >= 6, <= 45 min | **fixed 40/40, clean 40/40 (R1 38/38, R2 33/33, R3 27/27), audit 7/7, 30 min 54 s** |
| G2 `long_chat.py` 300K through the Docker image | 4/4 | **4/4**, history 304,552 tokens (more than the server's 262K window), 4 min 19 s |
| G3 README OpenAI SDK snippet | plain + tool call | **plain `ChatCompletion` (stop), tool call `shell {"command": "echo ok"}`, streaming in 1 chunk** (as the README says) |
| G4 (c19) Gemma 4 26B on llama.cpp, 100K | no bar | **4/4**, 4 min 28 s (above) |

  G1 detail: 305 model calls, 3,358,370 prompt tokens (FAp: 2.9M), 130,009 written, 44 ticket fetches, 33 FIXES
  lines. Proxy: 11 cuts, all in place; 524 messages archived; 0 recalls; 0 rules put back; 2 empty replies retried;
  notes read 224,647 prompt tokens, 203,840 of them from the server's cache (91%), 6,949 written. One notes reply
  was not applied (the 12th, 2 minutes before the end: "NOTES over twice the cap after the changes"); the proxy held
  the cut and carried on, as designed. G2: 24 cuts, all in place, 291 messages archived, 0 recalls; starting budget
  7,942 and codename VIOLET BEACON from the first message, current budget 6,289 ending in ROGER.

  **What this settles.** Installed the way the README says, with only `--recipe qwen`, the proxy matched the best
  hand-tuned repair runs. The tickets, and the three house rules they announce, reach the model inside tool
  results (the agent runs `next`), so without `--recite-when` the proxy never repeated the rules after a ticket;
  they sat only in the notes the model sees on every turn, and that was enough on this task (R1-R3 kept on every
  ticket they applied to). 30.9 min against FAp's 33.3 (recite on tickets, XR6 settings) and XR4's 15.6 (the
  harness client with thinking capped). The README keeps `--recite-when` as an option for instructions that arrive
  inside tool results, and says it was not needed here. Data:
  [`data/2026-10-14-context-campaign19/`](../data/2026-10-14-context-campaign19/) (`repair/G1c__repair-n40-s2x` is
  the result; `repair/G1__repair-n40-s2x` is the voided first try; proxy archives left out as in earlier campaigns).

### Campaign 20, registered 2026-10-15 01:10 before any run: well-known open-source agents through ctxkeeper

Owner, 2026-10-14: "you can test all the open source safe agents". `tools/agentbench` (built and plumbing-tested on
the CPU 2026-10-14/15, see its README) runs 12 open-source coding agents, pinned and as shipped, each in its own
container (task image, `--network none`, non-root, no capabilities, memory cap, one read-only socket to its proxy),
graded by the task's own verifier exactly as freeagent is. freeagent in the same harness is the control.

- **Task and server:** `repair-n40-s2x` (40 bugs, 44 tickets via `next`, 3 house rules, final audit of 7); the
  campaign-19 research server unchanged (two-card FP8, 262K, MTP 5, the lossless multi-user overlays).
- **Proxy: ctxkeeper 1.0.1** (`--recipe qwen` and nothing else, fresh state directory per run). 1.0.1 = 1.0.0 plus one
  fix found by the adapter work: a streamed reply was re-sent without vLLM's `reasoning` field, so streaming clients
  (9 of the 12 agents) never saw the model's thinking; it now passes `reasoning` and `reasoning_content` (new test;
  the old code fails it). The release follows this campaign.
- **Agents, in queue order:** freeagent (control), Goose 1.54.0, mini-swe-agent 2.4.6, Qwen Code 0.25.1, pi 1.2.0,
  ForgeCode 2.14.0, Open Interpreter rust-v0.0.56, OpenHands SDK 1.54.0, Hermes Agent 0.22.1, Kimi Code 2.2.0,
  Mistral Vibe 2.26.1, Cline CLI 3.0.71, OpenCode 1.19.0.
- **Decisions taken for this run (owner may change them; all in the agentbench README):** each agent as shipped
  (its own system prompt, tools and sampling; nobody's own compaction is on); one 32K proxy window for all (a heavy
  fixed prompt, up to ~20,800 tokens for Kimi Code, is part of that agent's result); Kimi Code keeps its one-line
  request-timeout patch (10 min to 1 h); ForgeCode runs although its usage tracking cannot be switched off (no network
  in the container, so nothing leaves); Open Interpreter as shipped (its task message is not the first user
  message, so ctxkeeper's kept head does not hold it; recorded, not patched); Codex CLI left out (Responses API only).
- **Concurrency and memory:** up to three agents at a time on one server (multi-user output identity was shown to
  64 users), so a run's wall time is not comparable to campaign 19's single-user 31 min; every agent, the control
  included, runs under the same conditions. An agent starts only while host memory leaves its plumbing-measured
  need plus 300 MiB above the server guard (1.6 GiB); a watchdog stops the newest agent below 1.80 GiB (that run is
  void, not a result). OpenCode needs ~1 GiB and runs only if that is ever free. Time limit 90 min per run (55 in
  campaign 19) because of the sharing.
- **Measured per agent:** fixed/clean of 40, rules R1-R3, audit of 7, tickets fetched, wall time, requests, whether
  every request carried the whole history (no compaction of its own), proxy cuts/recalls/rules put back, peak memory.
- **Expectations, written down now:** the control repeats campaign 19 (40/40, audit 6 or more). Agents with small
  fixed prompts that keep working until done (Goose, mini-swe-agent, pi, Qwen Code) reach 30 or more fixed; agents
  that stop at the first text-only reply may stop early on a 44-ticket task (scored as is, no "keep going" loop is
  added); Kimi Code and ForgeCode, with the heaviest fixed prompts, do worst. No agent is expected to break the
  proxy (every request answered, no restart).
- **Runner:** [`data/2026-10-15-context-campaign20/longrun-campaign20.sh`](../data/2026-10-15-context-campaign20/longrun-campaign20.sh)
  (stops Gemma, starts the server, schedules the queue, stops the server, puts Gemma back on `throughput`). Its
  scheduler, result lines and watchdog were dry-run on the CPU against the scripted model (`DRY=1`, 2026-10-15
  00:53-01:06): sequential runs, two at once, and a forced watchdog stop all behaved.

### Campaign 20 first launch stopped after 20 min; 20b registered 2026-10-15 01:36 before its run (launched 01:37)

**What happened (01:08-01:29).** The registration above was wrong on one point: the campaign-19 server runs
`--max-num-seqs 1` (the full 262K window), so it serves one request at a time; "up to three agents at once" only
queued them behind each other. Goose's second request (01:11:54; no `max_tokens`, no sampling fields, so the model's
defaults: temperature 1.0, top-k 20, top-p 0.95) then produced a reply that ran for 16 min at 18-24 tok/s with **zero
accepted draft tokens** in every 10 s interval (1,060 s; the draft only knows the 65K most common tokens, so the reply
had drifted into rare-token junk; without `max_tokens` vLLM allows up to the 262K window, i.e. hours). freeagent's
24th request waited behind it, hit freeagent's 900 s client timeout, and freeagent ended with 6 tickets fetched, 5/40
fixed, audit 0/7 (the control result is therefore void). Stopped at 01:29 (containers removed, proxies stopped, the
in-flight request aborted; server kept for diagnosis). None of the 22 earlier campaign servers' logs has a
zero-acceptance stretch of even 30 s.

**Diagnosis so far.** Goose alone with every request body kept (`c20/diag/`, 01:30-01:34, 74 requests in 4 min):
its second request took 1.5 s and every reply was normal. So the junk reply is not a fixed property of Goose's
request; with temperature 1.0 and no length limit a long reply can drift and never stop. Not yet known whether the
server contributed (no body or output of the bad request was kept). Follow-up after 20b: replay any captured runaway
body several times (default sampling, then fixed seeds) against the same server.

**Campaign 20b, changes only:** one agent at a time; every request body kept (`TAP=full`); 60 min limit per agent
(each one now has the server to itself; campaign 19's control took 31 min); a runaway stop: if the server has
logged drafting with zero accepted draft tokens for 300 s, the running agent is stopped and the event recorded in
`runaway-stops.txt` (its score stands as graded, marked "runaway stop"). Same agents, order, proxy, server settings
and expectations as registered above, except that a 40/40 control is expected in about 30 min. Output
`c20b/`. Worst case 13 h; expected ~5-7 h (agents that stop early take minutes).

### Campaign 20b results (01:37-04:00) and 20c registered 2026-10-15 04:06 before its run

20b ran seven agents one at a time; the other six were skipped by the runner's start rule (each agent's 4M-history
memory peak plus 300 MiB above the server guard; 2.37-2.46 GiB was free beside the server, OpenHands needed 2.44).
No runaway, no watchdog stop, no GPU fault line. Per agent (fixed / clean of 40, audit of 7, wall time, requests,
proxy cuts):

| Agent | Fixed | Clean | Rules R1 / R2 / R3 | Audit | Time | Requests | Cuts (failed) | Recalls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| freeagent (control) | 40 | 39 | 38/38, 32/33, 27/27 | 7/7 | 21.0 min | 271 | 8 (0) | 4 |
| Goose 1.54.0 | 40 | 40 | 38/38, 33/33, 27/27 | 7/7 | 24.0 min | 264 | 9 (0) | 22 |
| mini-swe-agent 2.4.6 | 40 | 40 | 38/38, 33/33, 27/27 | 7/7 | 13.8 min | 194 | 7 (0) | 0 |
| Qwen Code 0.25.1 | 40 | 39 | 37/38, 33/33, 27/27 | 7/7 | 33.1 min | 243 | 14 (0) | 2 |
| pi 1.2.0 | 39 | 39 | 37/37, 32/32, 26/26 | **0/7** | 27.8 min | 259 | 9 (0) | 8 |
| ForgeCode 2.14.0 | 0 | 0 | - | 0/7 | 1 min | 2 | - | - |
| Open Interpreter rust-v0.0.56 | 40 | 39 | 37/38, 33/33, 27/27 | 7/7 | 17.8 min | 185 | 5 (0) | 1 |


- **pi, audit 0/7: a wrong notes line, then the model deleted its own answer.** pi wrote `/app/AUDIT.md` with seven
  lines (message 492, after ticket 44 arrived at message 487), then went back for the two tickets it had skipped.
  The next in-place notes reply (covering messages 478-502, thinking off) said "no ticket 43 or 44 was ever printed",
  "no AUDIT ticket was ever received; file written on assumption, may be spurious", and under OPEN "consider removing
  spurious AUDIT.md". The model, seeing those notes and not the cut turns, tidied up: `rm -f AUDIT.md`. A silent-wrong
  notes line (the failure counted in the 2M stream, 1 in 130 lines) turned into a destructive action. pi's own
  ticket order was unusual (it fixed 40 after receiving 41, took 42 and 44 out of order), which may have made the
  stretch hard to summarize. Candidate follow-ups, not done: a notes check that a ticket or message the notes say
  never arrived is not in the cut material; notes should not propose deleting files.
- **ForgeCode: refused at the first request.** It sends two system messages (its instructions, then the system
  information); Qwen's chat template accepts a system message only at the start, so vLLM answered 400 "System
  message must be at the beginning" and ForgeCode stopped. It would fail the same way talking to the server
  directly. OpenHands' first request has the same shape. Fix in ctxkeeper (final 1.0.1, not in the build 20b ran):
  leading system messages are joined into one before the request goes upstream (`one_system_message`, new test;
  fails on the old code). Every other agent sends one system message, so for them the final code sends the same
  requests as the build they ran with.

**Campaign 20c, registered before its run:** the six skipped agents and ForgeCode, through the final 1.0.1
(`/mnt/fast-ai/venvs/ctxkeeper-1.0.1-final`, ctxkeeper.py sha256 df65d5c9ffaea3a0...), same server settings, one
at a time, 60 min limit, runaway stop, full request capture. Memory: an agent's need is now its plumbing non-file
memory at a ~1 MB history (this task's histories end below 1 MB) + 130 MiB; it starts with 100 MiB to spare above
the guard; the watchdog still stops it below 1.80 GiB (void). Order: OpenHands, Hermes Agent, Kimi Code, Mistral
Vibe, Cline, ForgeCode, OpenCode. Expectations: OpenCode (~0.84 GiB) cannot start beside this server on this
15.5 GiB host (recorded as not run); ForgeCode and OpenHands now get past their first request; Kimi Code (~20,800
fixed prompt tokens) leaves the least room in the 32K window and does worst; the rest 30 or more fixed.

**20c stopped at 04:05, 20d registered 04:07 before its run.** OpenHands' first request was refused (400):
it sends `reasoning_effort: "high"`, and Qwen3.8's template accepts only xhigh (its default), medium and low. Its
system message also comes as a list of text parts, for which ctxkeeper's memory note used to add a second system
message (the "two system messages" seen for OpenHands in the plumbing tests came from the proxy, not the agent).
Fixed in the final 1.0.1 (ctxkeeper.py sha256 38879dde54822c8a...): with `--effort` (in `--recipe qwen`) the
proxy's effort replaces a client's `reasoning_effort` (without `--effort` it is passed on); a text-parts system
message gets the memory note in place; two new tests, both fail on the previous code; 67 tests pass. Checked live
against the 20c server: an OpenHands-shaped request (text parts, effort high) and a ForgeCode-shaped one (two system
messages) both answered. No agent in 20b sent `reasoning_effort` or a text-parts system message (both would have
been refused), so the final code sends them the same requests. 20d = 20c's queue and settings with this build.

### Campaign 20d results (04:13-07:27) and 20e registered 2026-10-15 07:29 before its run

The first 20d launch (04:07) ended at once: the server's port probe hit a socket still in TIME_WAIT from the live
check of the fixed proxy (the known Errno 98); the runner now waits until no socket uses the port. Relaunched 04:13.
No runaway, no watchdog stop, no GPU fault line; free host memory stayed at or above 2.24 GiB.

| Agent | Fixed | Clean | Rules R1 / R2 / R3 | Audit | Time | Requests | Cuts (in place, failed) | Recalls | Peak MiB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenHands SDK 1.54.0 | 40 | 40 | 38/38, 33/33, 27/27 | 6/7 | 24.0 min | 210 | 6 (6, 0) | 0 | 418 |
| Hermes Agent 0.22.1 | 40 | 40 | 38/38, 33/33, 27/27 | 7/7 | 25.6 min | 240 | 12 (9, 0) | 8 | 436 |
| Kimi Code 2.2.0 | 40 | 40 | 38/38, 33/33, 27/27 | 7/7 | 38.1 min | 288 | 13 (12, 1) | 2 | 429 |
| Mistral Vibe 2.26.1 | 40 | 7 (grader, see below) | 37/38, 0/33, 27/27 | 0/7 (grader) | 19.3 min | 278 | 5 (5, 0) | 0 | 361 |
| Cline CLI 3.0.71 | 40 | 40 | 38/38, 33/33, 27/27 | 7/7 | 23.6 min | 283 | 12 (11, 1) | 11 | 447 |
| ForgeCode 2.14.0 | 25 | 25 | 23/23, 18/18, 12/12 | 0/7 (not reached) | 60 min limit | 223 | 69 (7, 0) | 2 | 176 |
| OpenCode 1.19.0 | not run: 2.29 GiB free, 2.52 needed (~0.84 GiB for the agent) | | | | | | | | |

- **OpenHands audit 6/7:** six lines, all right; one early ticket left out.
- **ForgeCode** worked through the fixed proxy (no refusal) and kept every rule, but reached ticket 29 of 44 in the
  60 minutes: its ~11,600-token fixed prompt leaves the least room in the 32K window of any agent that ran, and the
  proxy cut 69 times (62 of them not in place).
- **Mistral Vibe: a grading fault in the harness, not the agent.** Vibe wrote `/app/FIXES.md` (first line with its
  `write_file` tool, then `echo >>`) and `/app/AUDIT.md` (`write_file`), and its last command printed both, all
  33 FIXES lines and the 7 audit lines (right). The grader read both as empty. `RECIPES.txt`, first created by a shell
  `echo`, was graded normally (27/27). Cause, reproduced in a throwaway container with the harness's flags: the
  grader runs as root, but the container drops every capability, so root cannot read a file its owner made
  owner-only (`Permission denied`), which `write_file` evidently does; `docker exec --privileged` for the grading
  command reads it. Fixed in `tools/agentbench/run-agent-job.sh` (06:05, swapped in atomically; Cline and ForgeCode
  ran after it was written, Cline's job had started under the old copy and graded normally): the grading command
  runs with `--privileged` (the agent's processes are all killed first) and `ls -la /app` is saved as
  `verifier/app-files.txt`. No other run is affected: every other agent's FIXES and AUDIT lines were read (pi's
  AUDIT.md was deleted by pi, seen in its own commands).

**Campaign 20e, registered before its run:** Mistral Vibe once more, alone, with the fixed grader; everything else
as in 20d (final 1.0.1 proxy, same server settings, 60 min limit, runaway stop, full request capture). The 20d row
stays in the record as a harness fault. Expectation: about 40 fixed, 40 clean, audit 7/7 (what its 20d commands
show); `app-files.txt` should show FIXES.md and AUDIT.md as owner-only.

### Campaign 20e result and campaign 20 summary (2026-10-15 08:00)

**20e (Mistral Vibe with the fixed grader, 07:32-08:00):** fixed 40, clean 40, R1 38/38, R2 33/33, R3 27/27, audit
7/7, 25.5 min, 289 requests, 5 cuts (5 in place, 0 failed), peak 383 MiB. `verifier/app-files.txt` shows the cause
of the 20d reading: `FIXES.md` and `AUDIT.md` are `-rw-------` (made by `write_file`), `RECIPES.txt` is `-rw-r--r--`
(made by the shell). As expected.

**Campaign 20 in one table** (the valid run of each agent; ctxkeeper 1.0.1 `--recipe qwen`, 32K window, the
two-card FP8 server alone, 60 min limit; c20b = the build without the request fixes, which none of those agents
needed; c20d/e = final 1.0.1):

| Agent | Run | Fixed | Clean | Audit | Time | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| mini-swe-agent 2.4.6 | c20b | 40 | 40 | 7/7 | 13.8 min | |
| Open Interpreter rust-v0.0.56 | c20b | 40 | 39 | 7/7 | 17.8 min | its task message is not the first user message (kept head) and it still scored |
| freeagent (control) | c20b | 40 | 39 | 7/7 | 21.0 min | campaign 19: 40/40/7, 30.9 min (then shared nothing either) |
| Cline CLI 3.0.71 | c20d | 40 | 40 | 7/7 | 23.6 min | |
| Goose 1.54.0 | c20b | 40 | 40 | 7/7 | 24.0 min | its runaway reply in c20 did not recur |
| OpenHands SDK 1.54.0 | c20d | 40 | 40 | 6/7 | 24.0 min | needed final 1.0.1 (effort "high", text-parts system message) |
| Mistral Vibe 2.26.1 | c20e | 40 | 40 | 7/7 | 25.5 min | c20d graded empty by the harness fault |
| Hermes Agent 0.22.1 | c20d | 40 | 40 | 7/7 | 25.6 min | |
| pi 1.2.0 | c20b | 39 | 39 | 0/7 | 27.8 min | deleted its AUDIT.md after a wrong notes line |
| Qwen Code 0.25.1 | c20b | 40 | 39 | 7/7 | 33.1 min | |
| Kimi Code 2.2.0 | c20d | 40 | 40 | 7/7 | 38.1 min | ~20,800-token fixed prompt; expected to do worst, did not |
| ForgeCode 2.14.0 | c20d | 25 | 25 | - | 60 min limit | needed final 1.0.1 (two system messages); 69 cuts, ticket 29 of 44 |
| OpenCode 1.19.0 | c20f | 40 | 40 | 7/7 | 33.1 min | run alone later (20f) with 400 MiB RAM + swap; first skipped for host memory |

Against the registered expectations: the control repeated campaign 19 (40/40, 7/7, faster alone: 21 min). Ten of
the eleven other agents that ran fixed 39 or 40 (expected: 30 or more for the small-prompt agents; none stopped
early at a text-only reply); the two predicted worst split: Kimi Code full marks, ForgeCode out of time. The proxy
answered every request of every valid run; 2 of 93 in-place notes cuts were refused by the checks and held (Kimi,
Cline), none failed a run. Failures found and fixed on the way: a runaway reply with no length limit starving
other agents on a one-sequence server (runner: one agent at a time, runaway stop), three request shapes Qwen3.8's
template refuses (ctxkeeper 1.0.1), a grader that could not read owner-only files (agentbench), the server-port
TIME_WAIT race (runner). Open: the wrong notes line behind pi's deleted audit (silent-wrong notes, the program's
known weakness); OpenCode on a host with more free memory; one run per agent and one seed (no spread).

### Campaign 20f, registered 2026-10-15 13:36 before its run: OpenCode with a swap-backed memory cap

The one agent campaign 20 could not run. Same task, server settings, ctxkeeper 1.0.1 final (`--recipe qwen`), 60 min
limit and grader as 20d/e; one change: OpenCode's container gets 400 MiB of RAM with swap behind it
(`run-agent-job.sh` AGENT_MEM_SWAP=2g; the host has a 32 GiB swap file on the NVMe disk), so the part of its ~0.84
GiB that does not fit pages out instead of taking host memory. Start rule 1639 + 100 + 530 MiB; watchdog line 1720
MiB (81 above the server's 1.6 GiB guard; 1800 in 20b-e). Dry run first against `fake_agent_server.py` (no GPU).
Expectation: it runs to the end (the agent's own CPU work is small next to the model's replies, so paging costs
little time); fixed 30 or more like the other small-prompt agents. A watchdog stop or a memory-guard stop is a void
for host memory, recorded as such. Gemma stopped first and put back on its throughput recipe after.

### Campaign 20f result (13:37-14:18): OpenCode 40/40, 7/7

Server ready in 165 s with 2,966 MiB free (more than the 2.29 GiB of campaign 20, so OpenCode would have fit uncapped
this time; the cap was kept as registered). OpenCode 1.19.0: **fixed 40, clean 40, R1 38/38, R2 33/33, R3 27/27,
audit 7/7**, 33.1 min (agent 1,973 s, exit 0), 296 requests, whole history every time, 13 cuts (12 in place, 0
failed), 1 recall, container non-file peak 381 MiB inside the 400 MiB cap (it paged the rest). Host memory while the
server ran: min 1.90, median 2.05 GiB; no watchdog or guard stop. Kernel log clean; Gemma back on its throughput
recipe 14:13. Against the expectation: as expected (ran to the end, 30 or more). Data:
`data/2026-10-15-context-campaign20/c20f/`. The campaign-20 table above now carries this row: twelve of twelve agents
ran, eleven fixed 39 or 40.

### What the saved runs say about the owner's four questions (2026-10-16, CPU-only, no GPU job)

Read from the request logs of campaigns 12-20 before designing campaign 21 (scripts and tables:
`data/2026-10-16-context-campaign21/offline/`). (1) **Idle time to hide work in is small**: the server sat idle 12.8 %
of the 1M run (X32p; mostly harness overhead), 0.4-8.7 % in the campaign-20 agent runs; gaps between requests median
2-4 s. Notes work is the larger target: 38-42 % of the server's time in the 1M run (notes thinking on, 75 cuts, 93K
tokens written), 3-8 % in the agent runs (notes thinking off). With `--max-num-seqs 1` a background notes call can
only queue behind the next main call, so hiding it needs two sequences. (2) **The front of the view is already
static** in in-place mode: a cut keeps the opening messages and replaces only the notes and the turns they cover;
re-reading after cuts is ~4-10 % of uncached prompt tokens. The largest re-read cost (~66 % of uncached tokens in the
campaign-20 runs) is the server's 832-token cache block granularity, an engine setting, not a proxy one. (3) **A CPU
pre-pass that stubs old tool output** (simulated on the repair runs): for the model keeping its own notes it is a net
loss (the stubbed view stops matching the cache: 229K-565K more tokens re-read to save 15-45 s of notes); it can only
help a separate keeper that reads the turns fresh. (4) FAd's whole-history run decoded ~41 tok/s against 60-100 inside
a 32K view: most of the keeper's speed comes from the short view, not from fewer tokens read.

### Campaign 21, registered 2026-10-16 02:20 before any run: the window floor, and notes written in the background

Questions: how small a window ctxkeeper still works in, and where the speed/quality best point is; and whether writing
the notes in the background (right after a reply, while the agent's next request runs) saves time. Code: lab commit
`d1435071e` (ctxkeeper 1.1.0.dev0; every new option off by default, five-scenario equivalence with 1.0.1). Server:
the campaign 12-20 two-card research server unchanged except `--seqs 2` (so a background notes call can run beside a
main call; with MTP5 two batched requests are not bit-identical to solo, which the context lane allows: the measure is
the task score). One server for all arms; Gemma stopped first, restored on `throughput` only with a clean kernel log.
Every proxy runs `--log-calls` (one row per model call: kind, seconds, tokens read/cached/written), so the largest
single call (read + written) gives the window each run really needed.

Arms (queue order; one run each, one seed; runner `data/2026-10-16-context-campaign21/longrun-campaign21.sh`):
- **S08 smoke**: `long_chat.py` 60K tokens, `--recipe qwen --budget 8192 --inplace-tokens 3000 --notes-async defer
  --prewarm`. Gate for the background arms: the client finishes, at least one background notes result is applied,
  no proxy error. If it fails, A32d/A32dp/M32dp are skipped.
- **240K rules stream s0** (39 questions; X32p 39/39 in 8.5 min at seqs 1), X32p's options throughout (notes
  thinking on), `--inplace-tokens` = 0.458 x budget: **K32** (32,768, reference on this server), **A32d** (K32 +
  `--notes-async defer`), **A32dp** (A32d + `--prewarm`), then the window sweep **K16, K08, K06, K12, K24, K48, K64**
  (16,384 / 8,192 / 6,144 / 12,288 / 24,576 / 49,152 / 65,536). Cap 40 min each.
- **1M stream s0** (228 questions; X32p 226/228 in 49.6 min at seqs 1): **M32dp** = A32dp. Cap 100 min.
- **Repair task** `repair-n40-s2x`, harness client as X16/X24/XR4 (XR4 options, notes thinking off): **R16**
  (16,384, notes every 7,500 tokens: the 16K test X16 was not, its 15,000 threshold never fit), **R12**, **R48**.
  Cap 60 min.

Expectations, written before the runs: the stream holds 39/39 down to 12K and probably 8K (its notes stayed under
~400 tokens and its largest turn was 2,266 tokens in X32q); **6K fails** or nearly (opening + notes + largest turn
already ~3.4K of the 3.1K a 6K budget leaves after the reply reserve); time grows as the window shrinks (more cuts,
each with a thinking notes call) and flattens above 32K. Background notes cut A32d's time by 15-30 % against K32 on
this stream and M32dp's by 20-35 % against X32p's 49.6 min; prewarm adds a few percent at most. Repair: R16 40 clean
or 39 (the 21,855-token largest tool result cannot fit a 16K view; how the run copes is part of the result), R12 may
fail, R48 the same score as XR4 in about the same time. Decision rules: the smallest window whose score equals K32's
is the floor; background notes become a recipe default only if they save 10 % or more with no score loss on both
streams; anything below the floor is reported, not retried. Stopping early: `STOP-CAMPAIGN21`; no arm is rerun.

**Campaign 21 first launch (02:22-02:28), relaunched as c21b.** The server came up in 165 s (3.0 GiB free, settling at
2.1 GiB, as in campaigns 12 and 20). The smoke test passed its four questions but tested nothing: at an 8K window the
2,000-token reports forced ordinary cuts every turn (30 cuts, 0 in place), so no background notes were ever started,
and the gate skipped the background arms. Then the runner's room rule (512 MiB above the guard, from campaign 17)
stopped the queue at 464 MiB. Fixed before any arm ran: the smoke test is now S16 (16,384 window, notes every
5,000 tokens, 1,000-token reports, so notes are taken in place), and the room rule is 256 MiB (the task container's
cap; campaigns 12 and 20 ran their arms at this level). Nothing else changed.

**c21b smoke (S16, 02:38-02:43): the background path works, the server does not, with two requests at once.**
15 notes calls ran in the background, 15 applied, 0 discarded (the proxy side is right). But every main reply that
was written while a background notes or prewarm call ran beside it came back as 2,048 tokens of "!!!!"
(finish=length; the same replies alone are a few tokens), and one of the four final questions failed that way. The
server log shows vLLM's mixed prompt-and-decode step path (`R156 GDN split-mixed step executed`) at that time. This
research server (MTP5, prefix cache in align mode, the research overlays) had only ever served one request at a time;
the package's qualified multi-user mode avoids mixed steps (`B70_EXCLUSIVE_PREFILL`) and runs without MTP. Action at
02:45, before the arm after K32 started: A32d, A32dp and M32dp commented out of the queue (garbage would be scored as
memory loss); the window sweep is unaffected (one request at a time). Follow-up registered: a server configuration
check with `scripts/context/concurrency_check.py` (solo vs overlapped replies; garbage, different, same) on the
research server with `--overlay b70-exclusive-prefill`, then the background arms only on a configuration with no
garbage.

**c21b change at 03:35, before K06 ran:** K06 dropped from the queue. K08, 32 min in, had made 118 notes calls for
133 agent turns (notes 1,603 s against 280 s of agent calls: 85 % of the server's time) and had 20 of 39 answers
written, on course for its 40 min cap; a 6K window can only take more notes calls.

**c21b ended 03:42 by the host memory guard; the rest relaunched as c21c with `--seqs 1`.** K08 finished (graded
39/39, 39 min 38 s) and the guard stopped the server seconds later, at the run's end-of-task grading (1.59 GiB free;
the same end-of-run spike as c17-first). With `--seqs 2` this server sat at 1.72-1.84 GiB free during arms (median
1.77), about 0.3 GiB below the one-sequence campaigns (c12 median 2.13, c20f 2.05). The arms still to run need one
request at a time, so c21c runs them on `--seqs 1` (queue `QUEUE21c.txt`: K12, K24, K48, K64, R16, R12, R48; nothing
else changed). Kernel log clean; Gemma restored 03:46.

### Campaign 21 results (c21b 02:36-03:42 with `--seqs 2`, c21c 03:46-06:18 with `--seqs 1`; kernel log clean)

One run per arm, seed 0 / `repair-n40-s2x`; table from every model call the proxy logged
(`data/2026-10-16-context-campaign21/summarize_c21.py`, `results-c21.json`). "Largest call" = the most one request
read and wrote: the window the run really needed.

| arm | window | score | min | cuts (in place) | agent calls s | notes s (share) | largest call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| K08 | 8,192 | 39/39 | 39.6 | 146 (0) | 349 | 1,979 (85 %) | 7,360 |
| K12 | 12,288 | 39/39 | 24.3 | 85 (0) | 316 | 1,089 (78 %) | 8,430 |
| K16 | 16,384 | 39/39 | 10.3 | 35 (34) | 266 | 301 (53 %) | 11,718 |
| K24 | 24,576 | 38/39 | 8.8 | 23 (23) | 287 | 188 (40 %) | 15,200 |
| K32 | 32,768 | 39/39 | 8.7 | 17 (17) | 289 | 182 (39 %) | 18,997 |
| K48 | 49,152 | 39/39 | 8.1 | 11 (11) | 301 | 136 (31 %) | 25,885 |
| K64 | 65,536 | 39/39 | 10.0 | 8 (8) | 312 | 233 (43 %) | 36,397 |
| R12 | 12,288 | 40 fixed, 38 clean (R1 36/38), 7/7 | 29.6 | 47 (7) | 1,043 | 652 (38 %) | 15,159 |
| R16 | 16,384 | 40, 40, 7/7 | 35.1 | 19 (16) | 1,861 | 108 (6 %) | 17,057 |
| R48 | 49,152 | 40, 40, 7/7 | 22.5 | 6 (6) | 1,244 | 36 (3 %) | 29,740 |

(Repair at 24K and 32K, campaign 17: X24 40/40/40 7/7 13.1 min; XR4 40/40/40 7/7 15.6 min.) K32 repeated c13's
X32q in every proxy count (17 cuts, 292 archived, 10 recalls, notes 342,682 read / 17,146 written): the code and the
`--seqs 2` setting change nothing for one request at a time.

Against the expectations: the stream held its score at every size, **down to 8K** (expected: 6K fails, 8K probably
holds; 6K was not run, see above). Time is flat from 24K to 48K (8.1-8.8 min), rises above (64K: each turn reads
more, each notes call is bigger) and **climbs steeply below 16K: 2.8x at 12K, 4.5x at 8K**. The reason is in the
cuts column: at 12K and 8K no cut was taken in place. The window keeps room for the largest turn seen (2,266 tokens)
besides the reply reserve, so the turns never reached the scaled threshold before the ordinary cut fired, and every
cut rewrote the notes in full with thinking (~13 s each). That is a property of the threshold, not of the window:
`--inplace-fit` (campaign 23, K12f/K08f) tests the fix. K24's one miss is a single run's notes slip (the arms either
side of it held). On the repair task the floor is ~16K: R12 kept the fixes but missed the change marker twice
(38/40 clean); R16 was perfect but slow, from the agent, not the notes (notes 6 % of the time; 10 replies thought to
the 8,192-token cap, real deliberation, not garbage; 158K tokens written against R48's 99K): with less in view the
agent re-derives more. Repair times vary run to run more than the stream's (one run each). Decisions: the floor is
16K (8K on a stream whose notes are small and whose turns are short); the best speed is 24K-48K; 32K stays the
default. Host memory with `--seqs 1`: min 1.62, median 1.97 GiB over c21c.

### Campaign 22, registered 2026-10-16 02:30 before any run (to start after campaign 21): one card, and a smaller keeper

Questions: does ctxkeeper let the 27B model work on ONE card (the 26,624-token window that card holds beside the
weights), and can a different, cheaper model keep the notes for it. Keeper: LFM2.5-24B-A2B Q8_0 (about 2B active
parameters per token; package v4 build, `serve.sh fast`, its exact fast mode, 64K context, no prompt cache) on card 1,
loaded first; then the one-card Qwen server on card 0 (the 2026-10-10 one-card settings: cpu-embed, MTP5, mem 0.975,
window 26,624, seqs 1, `B70_ALLOW_BUSY_RENDER=1`). The client asks for 8,192 reply tokens, so every arm runs
`--budget 26624 --reply-reserve 8192 --notes-max-tokens 6144 --inplace-tokens 9000` (view up to ~17.4K, a little
over campaign 21's K16 view). A separate keeper gets a fixed system message (the same every call, so it is never a
blank slate about its job) and one message holding the opening messages, the current NOTES, what is still in the
agent's view, and the turns to note. Runner `data/2026-10-16-context-campaign22/longrun-campaign22.sh`.

Arms, one run each: **SL** smoke (`long_chat.py` 60K through the LFM2.5 keeper in the background; gate for the L
arms); 240K rules stream s0 with X32p's options: **O1** (Qwen keeps its own notes), **L1** (LFM2.5 keeps them), **L1d**
(L1 in the background: on a second card this runs truly beside the main call); repair task `repair-n40-s2x` with
XR4's options: **O1r**, **L1r**, **L1rp** (L1r + `--notes-prepass 2000`: long tool results cut to their start, end and
outcome lines before the keeper reads them). Caps 40 min (rules) and 60 min (repair).

Expectations: O1 39/39 and O1r 40 fixed / 39-40 clean (the view is close to K16/R16's), about 1.5-1.8x the two-card
times (one card decodes ~54 against ~90 tok/s). LFM2.5's notes are less reliable than Qwen's on the ledger stream:
L1 below 39/39, more checks refused and asked again; on the repair task, where notes are simpler, L1r close to O1r.
L1d faster than L1 by most of the keeper's time; prepass shortens the keeper's reading with no score change.
Decision: a separate small keeper is recommended only where its score equals the self-keeper's.

### Campaign 23, registered 2026-10-16 03:15 before any run (after campaign 21, before 22): background notes on a pure-step server

The c21b server plus `--overlay b70-exclusive-prefill` (B70_EXCLUSIVE_PREFILL=1: each step reads one request's
prompt alone or writes decode rows only, never both; from the multi-user work of 2026-10-04, where it made answers
equal to solo ones). Queue: **X** `concurrency_check.py` (three requests alone, then four overlapping pairs three
times; 24 overlapped replies compared with the solo ones) — any garbage stops the campaign before an arm runs;
**K32** (control: one request at a time, expected identical to c21b's K32 in every count); **S16** smoke (gate: 4/4
and background notes applied); **A32d**, **A32dp** (240K rules s0); **M32dp** (1M s0, cap 100 min). Runner
`data/2026-10-16-context-campaign23/longrun-campaign23.sh`.

Expectations: no garbage with pure steps (the mixed step is what the log showed); overlapped replies may still differ
from solo ones in a few tokens (MTP5 with two sequences was never batch-invariant). If replies differ, the async arms
are still run (the context lane scores answers), and the differences are reported. Background notes then save most
of the notes time that does not wait on the main call: A32d 15-30 % faster than K32 (8 min 43 s), M32dp 20-35 %
faster than X32p (49.6 min), same scores. Pure steps make a main call wait while a notes prompt is read; if that
eats the saving, it shows here.

**Added 04:25, before campaign 23 started: K12f and K08f.** c21's K12 (39/39, 24 min 15 s) and K08 (39/39, 39 min 38 s)
took 0 of 85 and 0 of 146 cuts in place: the scaled threshold (5,600 / 3,750) never fitted, because the window
reserves room for the largest turn seen (2,266 tokens here), so every cut was an ordinary one with the notes
rewritten in full (with thinking: 1,089 s and 1,979 s of notes). New option `--inplace-fit` (off by default): the
threshold is lowered to 3/4 of the room the window leaves (at least 1,000 tokens). K12f / K08f = K12 / K08 with it,
queued after A32dp; one request at a time, so they run even if the concurrency check fails (then only the smoke
test and the background arms are skipped). Expectation: most cuts in place, the same 39/39, and K12f near K16's
10 min; K08f faster than K08's 40 min but still the slowest.

### Campaign 23 so far (06:23-), and 23b registered 2026-10-16 06:40 before its run

**The concurrency check on the pure-step server (MTP5, `--seqs 2`, exclusive prefill): no garbage, but 23 of 24
overlapped replies differ from their solo replies, and the differences are not small drifts.** Some overlapped
replies splice two continuations mid-sentence ("To determine which team moved the most accurately answer this, I
will sum ...", "**Three Largest Moves:**\n1. Largest Moves:**\n1. ..."). Pure steps removed the "!!!!" but not this:
two sequences under MTP5 on this server are not safe to score. (The package's qualified multi-user mode runs with no
speculation; this matches its design.) Changes at 06:30, before any background arm ran: A32d, A32dp, M32dp moved out of
campaign 23 into 23b; K32 was skipped by the runner (its job name existed from campaign 21: the runs folder was
shared; from 23b each launch has its own folder); S16 had already started and is kept as a record of the async path
on this server; K12f and K08f (one request at a time) stay.

**23b**: the same runner and server with `MTP=0` (no draft model; decode is slower for every arm alike) and
`FA_PER_SEQ=1` (the per-sequence long-key attention overlay of the multi-user work), `--seqs 2`, pure steps. Queue: X
check (its solo replies are also compared with the MTP5 solos of campaign 23: equal means MTP5 alone is still exact),
K32 (sync control on this server), S16 smoke, A32d, A32dp. Expectations: no garbage and overlapped replies equal to
solo (the multi-user configuration was exact through 64 users); A32d/A32dp faster than this server's K32 by most of
the notes time that can overlap, same 39/39. No 1M run (its reference ran with MTP5).

**c23 S16 (06:27-06:31, pure steps, MTP5): "!!!!" again** in 10 of 64 main replies (2,048 tokens each, finish=length),
3/4 questions; 14 background notes applied, none discarded. So pure steps did not remove the garbage in the proxy's
real workload, although the check's 24 overlapped replies had none. The difference: a notes call and the agent's call
read the same long cached prefix at the same time (the check's pairs shared only a short system message). Before 23b
runs: `concurrency_check.py` gains a pair that shares one long cached prompt (B and D: the same 700 records, a
different question), and 23b's queue order is check, S16, A32d, A32dp, K32, with `CHECK_FAIL_STOP=1` (a garbage
result ends 23b before any arm). If the garbage follows the shared prefix with MTP off as well, the cause is the
prefix cache serving two sequences at once (align mode with the recurrent layers' state), and background notes on
one server wait for that fix; campaign 22's separate keeper on the other card does not share a server.

**c23 K12f / K08f (seed 0) and two lines added 06:56 before they ran.** K12f: 35/39 (3 wrong, 1 stale), 10 min 5 s,
70 cuts all in place (K12: 39/39, 24 min 15 s, none in place). K08f: **39/39, 13 min 8 s**, 136 of 152 cuts in place,
largest call 5,149 tokens (K08: 39/39, 39 min 38 s). Added to the queue while the server is up: K12f and K08f on seed
1 (46 questions; X32p 46/46 in 9.4 min), to tell whether K12f's four misses are the setting or one run.

### Campaign 23 and 23b results (06:23-07:24 MTP5; 07:24-08:28 no MTP; kernel log clean)

**The second sequence.** 23b (MTP0, `--seqs 2`, pure steps, per-sequence long-key attention): 36 of 36 overlapped
replies equal to their solo replies, including the two pairs that share one long cached prompt; no garbage. Its solo
replies equal campaign 23's MTP5 solos for B and C, but not A: **on the MTP5 `--seqs 2` server even a lone request
spliced once** ("1. night shift moved 5. night shift moved 584 ..." against MTP0's "1. night shift moved 584 ...").
So the fault is speculation with more than one sequence on this image, not the proxy and not mixed steps alone. (The
packages are not affected: their multi-user profile runs without speculation, their MTP profiles one sequence.)

**Background notes, measured on the 23b server** (240K rules s0; one run each; decode without MTP is slower for all):

| arm | score | min | cuts (in place) | agent calls s | notes s | the agent waited for notes |
| --- | --- | --- | --- | --- | --- | --- |
| K32 (notes in line) | 39/39 | 18.8 | 17 (17) | 523 | 552 | - |
| A32d (background, defer) | 39/39 | 16.1 (-14 %) | 16 (16) | 665 | 644 | 248 s |
| A32dp (+ prewarm) | 39/39 | 15.4 (-18 %) | 16 (16) | 659 | 607 | 216 s |

K32 here repeated the MTP5 K32 in every proxy count (17 cuts, 292 archived, 10 recalls, 342,682 / 17,146 notes
tokens): MTP5 one-sequence is still exact against MTP0. Against the expectations: the saving is at the low end of
the 15-30 % range. The agent's calls got slower (523 -> 665 s) because they share the server with the notes, and the
agent still waited 216-248 s for notes it needed before it could go on. Prewarm gave its few percent. Decision
(registered rule: 10 % or more with no score loss on both streams): **not a recipe default**. It saves 14-18 % only
on a server that can run two sequences correctly, and on this hardware that means giving up MTP, which costs far
more (the same run with MTP5 and in-line notes took 8.7 min). Where it can pay: servers without speculation, and a
separate keeper on its own card (campaign 22, L1d).

**The window floor with `--inplace-fit`** (c23, MTP5, one request at a time):

| arm | seed 0 | seed 1 | min (s0 / s1) | cuts in place |
| --- | --- | --- | --- | --- |
| K12f | 35/39 | 46/46 | 10.1 / 10.6 | 70/70, 68/72 |
| K08f | 39/39 | 45/46 | 13.1 / 13.1 | 136/152, 135/148 |
| (K12, K08 without it) | 39/39, 39/39 | - | 24.3, 39.6 | 0, 0 |
| (X32p at 32K) | 39/39 | 46/46 | 8.5 / 9.4 | |

`--inplace-fit` removes the small-window slowdown (8K: 3.0x faster, 1.5x the 32K time; largest call 5.1-5.3K
tokens). Quality: 81/85 at 12K and 84/85 at 8K over the two seeds, against 85/85 at 32K; K12f's four misses on seed 0
did not repeat on seed 1 (one run each: a notes slip, not yet a pattern). Decision: `--inplace-fit` becomes the
recommended setting for windows under 24K (it changes nothing at 32K on these streams); at 32K and above the
default stays as it is.

### Campaign 22 so far (08:28-), and 22b registered 2026-10-16 08:55 before its run

Both models loaded as planned: LFM2.5 ready in 21 s on card 1, then the one-card Qwen server in 150 s (5.9 GiB
host memory free beside both). **The LFM2.5 keeper wrote no notes in the smoke test**: every notes call came back
empty after 6,144 tokens (finish=length, ~59 s each). LFM2.5's chat template always opens a `<think>` block for a new
reply (`enable_thinking: false` changes nothing); llama.cpp's per-request `thinking_budget_tokens: 0` closes it at
once (tested on the running server: 8 tokens, no thinking, against 170 with). ctxkeeper gains `--notes-extra JSON`
(more fields for a separate keeper's requests; unit-tested: they go to the keeper only). Campaign 22 is stopped after its smoke
test (STOP file, 08:56; no arm had started) and everything moves to **22b**: the same runner with
`KEEPER_EXTRA={"thinking_budget_tokens":0}`, queue SL, O1, L1, L1d, O1r, L1r, L1rp (one restart either way; the
fixed smoke test runs first); everything else as registered for
22 (the expectations there stand; LFM2.5 now writes its notes without thinking, as the Qwen recipe's own notes do).

### Campaign 22b so far, and L1d dropped (2026-10-16 10:01)

- **O1** (Qwen3.8-27B FP8 on one card, its own keeper, 26,624-token window, rules stream s0): **39/39, 15.8 min**;
  28 cuts (27 in place, 1 failed), notes 440 s of 897 s server time (49 %), largest call 17.1K.
- **L1** (same, LFM2.5-24B-A2B Q8_0 on card 1 as the keeper, thinking closed): **19/39 (14 blank, 6 wrong), 38.3 min**;
  33 cuts (21 in place, 11 failed, 25 asked again), 8 full rewrites failed; notes 1,535 s on the keeper (100 calls,
  1.13M tokens read, none cached, 101K written). Two failure modes in `events.jsonl`: (a) the keeper answers as the
  agent (34 in-place replies and 16 full-notes replies were tool calls such as `cat /app/answers.json`, or the
  answers file itself) although it gets its own system message and the turns as quoted text, with no tools;
  (b) when it does use the layout it leaves names out (29 "names the turns do not mention" drops, many "mentioned 2
  times, 0 changes written") and writes amounts the turns do not state.
- **L1d dropped** at 3 min (SIGINT to its time-limit process, as the cap would): it is the same keeper writing in the
  background, so its score would repeat L1's and its timing would not apply to a usable keeper. Next: O1r as queued.
  Before L1r: a direct test on the idle keeper server of starting the keeper's reply with `NEW RULES` (an assistant
  prefill, which llama.cpp continues), to see whether (a) goes away.

### O1r result, the keeper-reply test, and campaign 22c registration (2026-10-16 10:28, before 22c runs)

- **O1r** (one-card Qwen, its own keeper, repair task): **40/40 fixed, 40/40 clean, audit 7/7, 21.1 min**; 11 cuts, all
  in place, none failed; notes 95 s of 1,204 s server time (8 %); largest call 14.0K. (Two cards at 32K: 15.6-16 min.)
- L1r (LFM2.5 keeper as in L1, repair) had started at 10:22, before the queue edit; it runs as registered. L1rp is
  removed from the 22b queue (`QUEUE22b.orig.txt` keeps the original).
- **Keeper-reply test** (scratch script, the L1 run's archive and notes history rebuilt into the requests the proxy
  sends, with the agent's real opening messages from a context snapshot; the idle keeper server, temperature 0). The
  last 10 notes windows: as sent, the keeper answered as the agent in 4 of 10 (a tool call, or a `{"thought": ...}`
  step); with the reply started as `NEW RULES` (an assistant message that llama.cpp continues), in 0 of 10. It
  then still wrote the notes inside the think block its template had opened, closed it and added a tool call
  (`</think><|tool_call_start|>[bash(command='echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT')]`), and it re-listed old
  values as "(no change)" lines. Cut at that tail, all three replies looked at parse as notes. With the first 8
  windows and a made-up opening the keeper never answered as the agent: the agent's own system message is what pulls
  it into the agent's role.
- New proxy option **`--notes-prefill`** (1.1.0.dev0, off by default, a separate keeper only): the keeper's request
  ends with an assistant message holding the layout's first heading (`NEW RULES` in place, `RULES` for a full
  rewrite); the proxy puts the heading back and cuts the reply at `</think>`, a tool-call marker or a
  `{"thought"` line. Unit test added (88 pass). The runner gained `KEEPER_PREFILL=1` and `RUNS_BASE`.
- **Campaign 22c**: the same runner and servers, `RUN=c22c KEEPER_EXTRA={"thinking_budget_tokens":0} KEEPER_PREFILL=1
  RUNS_BASE=$O/runs/c22c`, queue `L1r repair 2x 3600`, `L1rp repair 2x 3600` (prefill + `--notes-prepass 2000`),
  `L1 rules 0 2400`; launched when 22b has ended. Expectations: no keeper reply is a tool call; on repair the fixed
  keeper fixes 40 and keeps the rules on at least 38, audit at least 5 of 7, but takes longer than O1r's 21 min (the
  keeper reads every turn afresh at about 2K tokens/s and the agent waits for it); the pre-pass cuts the keeper's
  tokens read by at least 30 %. Stop rule: if the fixed L1r fixes fewer than 35 or keeps the rules on fewer than 35,
  L1rp and L1 are dropped (a pre-pass cannot rescue a keeper that loses the work).

### Campaign 22c results (2026-10-16 11:03-12:04): the small keeper with its reply started

| arm | keeper | task | result | wall | cuts (in place / failed) | notes calls / s | notes read (cached) |
|---|---|---|---|---|---|---|---|
| O1r (22b) | Qwen itself | repair | 40 fixed, 40 clean, audit 7/7 | 21.1 min | 11 (11 / 0) | - / 95 s (8 %) | cached |
| L1r (22b) | LFM2.5, as sent | repair | 40 fixed, 20 clean, audit 7/7 | 35.4 min | 13 (12 / 1) | 17 / 317 s | 0 cached |
| **L1r (22c)** | LFM2.5, `--notes-prefill` | repair | **39 fixed, 20 clean** (R1 36/37, R2 19/32, R3 17/26), **audit 0/7** (no audit file written) | 55.4 min | 19 (16 / 1) | 27 / 774 s | 299K, 0 cached |
| L1rp | prefill + pre-pass | repair | dropped by the stop rule at 1 min 56 s (SIGINT to its timeout, rc 120) | - | - | - | - |
| L1 (22c) | prefill | rules | dropped by the stop rule (removed from the queue; `QUEUE22c.orig.txt` keeps it) | - | - | - | - |

- The stop rule fired (clean 20 < 35), so L1rp and L1 were dropped. The first expectation held: no notes reply was
  rejected for a missing layout (22b's L1 had 60 such rejections, mostly tool calls or agent steps; 22b's L1r had 3). The rest did not: the started reply fixes
  the role, not the content.
- What the keeper wrote (notes history, last notes): it copies the request's instruction text into RULES as if it
  were a rule ("one line per standing rule, instruction, method or definition that those turns state ...", "one: line
  `name: value` per fact of STATE ..."), copies the agent's system message into RULES although told not to, and
  keeps only one of the NOTICE house rules (`# fixed` from ticket 7) in its own words. Ten notes replies were
  rejected for length (the copied text plus re-listed old lines run past the cap), one in-place merge came out over
  twice the cap, and two full rewrites failed.
- Conclusion for the separate-keeper question: an off-the-shelf 24B-A2B model is not a usable keeper here. On one
  card next to the 27B it was slower (35-55 min against 21) and lost the house rules on half the tickets, while the
  27B keeping its own notes did everything right; its notes cost little because they read the agent's own cached
  view, which a separate model cannot. A keeper trained for the job (the owner's suggestion) is the remaining route;
  not started.
- Gemma stopped at 11:03 and restored by the runner at the end (see the next line).

### ctxkeeper 1.1.0 released (2026-10-16 12:11)

- Tag `ctxkeeper-v1.1.0` at f3a981548: the 1.1.0.dev0 options (separate keeper, background notes, `--inplace-fit`,
  `--log-calls`), all off by default; the default path unchanged against 1.0.1 (73 old tests pass; request-level
  comparison over five setups identical). README: options under "Added in 1.1.0", the one-card and separate-keeper
  results.
- Checked from the public URLs: checksums, pip (wheel and archive), Docker build from the archive URL, and the demo
  through that image to the Gemma LAN server with a 4K view and `--inplace-fit`: 4/4 in 60 s
  (`data/2026-10-16-context-campaign22/release-1.1.0-check/`).

### Campaign 24 (2026-10-16 15:00, registered before any run): drafting with two requests, with all four multi-user fixes

- **Why.** Campaigns 21 and 23 concluded that MTP5 with `--seqs 2` corrupts replies. Neither server had
  `b70-fa-decode-per-seq` (and campaign 21 had no `b70-exclusive-prefill`). The 2026-10-04 multi-user work (repeated
  on a second server 2026-10-15) found drafting exact at 2 to 16 users on R314 with all four fixes: pure steps,
  per-sequence attention, `b70-gdn-state-width`, `b70-spec-resume-accepted`. What the context server adds is prefix
  caching (`align` + `b70-prefix-cache-exact`) and a shared long prompt, never tested with drafting and two requests.
- **Server:** campaign 23's (R314, TP2, 262K, `--seqs 2`, MTP5 with the INT4 draft and shortlist, `--fa-verify-rows`,
  all its overlays) plus `FA_PER_SEQ=1`. Runner `data/2026-10-16-context-campaign24/longrun-campaign24.sh` (campaign
  23's, plus `CHECK_REF`/`CHECK_STRICT`), ctxkeeper 1.1.0.
- **Queue:** X check (3 rounds; `--reference` = campaign 23b's MTP0 solo replies; `CHECK_STRICT=1 CHECK_FAIL_STOP=1`:
  any garbage or any reply different from solo or from the reference ends the campaign); S16 smoke; K32 (240K rules
  s0, notes in line: the control on this server); A32dp (`--notes-async defer --prewarm`).
- **Expectations:** check 0 garbage, 0 different, every solo reply equal to the MTP0 reference; K32 39/39 in about
  9 min (campaign 21's MTP5 K32: 8.7); A32dp 39/39 and 10-20 % faster than this K32. If the check fails, the memory
  and docs claim stands ("even with the four fixes") and the failing pairs are recorded.

### Campaign 24 result (15:10-15:16) and campaign 24b registration (15:20, before it runs)

- **Campaign 24's check failed, so the campaign stopped there** (K32 and A32dp not run). With all four multi-user
  fixes, 36 overlapped replies: **2 garbage, 27 different from solo**; every solo reply equal to campaign 23b's MTP0
  reference (one request at a time is exact on this server). It is deterministic: B beside C came back as the same
  garbage in rounds 0 and 2 ("moved the mostitems, we need to counttheenumber000..."), and every pair repeated its
  outcome. So the docs' claim stands; the four fixes are not enough on this server.
- **What differs from the exact 2026-10-15 multi-user server** (launch argv diff): this server has
  `--enable-prefix-caching --mamba-cache-mode align` + `b70-prefix-cache-exact` + retention interval, a 262,144-token
  window (33,024 there), 832-token steps (4,096), and pure-step prompt batching at its default (8 there). Images,
  every other env value, the draft (INT4 head, shortlist), compilation config, block size 64 and `--seqs 2` are the
  same.
- **Campaign 24b**, `data/2026-10-16-context-campaign24/mtp-multiseq-bisect.sh` (Gemma off once, one fresh server
  per line, the same check against the same reference): **P0** = campaign 24's server without prefix caching;
  **L33** = with prefix caching but 33K window, 4,096-token steps, prompt batching 8 (the exact server plus prefix
  caching); **E0** = the exact server's settings through this runner (control). Expectation: P0 and E0 clean, L33
  fails, i.e. prefix caching in align mode with drafting and two requests is the fault. If P0 fails, the window or
  step size is involved and the next lines split those.
