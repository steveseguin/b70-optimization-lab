# Copy-from-context drafting for one user: sized offline, build preregistered (2026-10-04)

## In plain words

Today the 27B drafts a few words ahead with a small built-in head, then checks them in one pass: about 3 words per
step, 90 tokens a second on two cards. When the answer repeats something already on the page (the prompt, or the
model's own earlier text), the next words can simply be copied from there as the draft. That draft costs nothing to
make, and every word is still checked by the full model, so the answer cannot change.

Replaying saved answers on the CPU says this is **worth 30 to 55 % on long-context work and nothing on short
prompts**, and with a strict matching rule it does not cost anything where it does not help.

## Sizing (a model on saved answers, not a measurement)

`scripts/qwen38-fp8-copy-draft-sizing.py`. A step with a copy draft costs one verify pass (29.5 ms); any other step
is a normal step (33 ms at the measured tokens per step).

| Prompts | Draft 5, match of 6 | Draft 8, match of 6 | Draft 16, match of 6 |
|---|---:|---:|---:|
| Long (2K to 8K tokens, continue repository text) | +30 % | +42 % | +54 % |
| Short ladder (31-token prompts) | +0.3 % | +0.4 % | +0.4 % |
| Published 12-prompt strict suite | 0.0 % | 0.0 % | 0.0 % |

With a looser rule (a match of 3 tokens) the long prompts gain a little more and the strict suite loses about 1 %.
The long suite is continuation of code and documents, which is the friendly case; rewriting, code editing and
quoting answers should sit between the two rows. The published single-user number (90 tok/s on the strict suite)
would not move; this is a second number for long-context use.

## Plan, written before it is built

1. **Drop-in first: 5 copied tokens, match of 6 or more.** Five is the shipped draft depth, so every tensor shape
   in the verify step is the one the shipped recipe already uses and the exactness gates carry over. The built-in
   head still drafts; a copy draft replaces its tokens when the rule fires.
2. **Gates:** strict 12 of 12, short ladder 64 of 64, long suite 64 of 64 against the frozen no-speculation
   reference, all at one user. Speed on the long suite against the shipped recipe on the same suite, two fresh
   servers.
3. **Keep it if** the long suite gains 10 % or more with every gate exact and the strict suite does not lose more
   than 1 %. Then try 8 and 16 tokens, which change the verify shapes and so need the same gates again.
4. **If the engine's asynchronous step pipeline makes the context one step stale** (the accepted tokens of the last
   step are not on the CPU when the next draft is placed), measure the acceptance with that lag before building
   around it.

## Result, 16:51 EDT: exact, free, and no faster. Closed in this form.

Two-card server, one user, shipped recipe with and without `b70-copy-draft` (5 copied tokens, match of 6 to 8).
Data: `data/2026-10-04-copy-draft/`.

| Gate | Without | With |
|---|---|---|
| Strict suite vs frozen reference | 12/12, 90.26 tok/s | 12/12, 89.91 tok/s |
| Short ladder vs frozen reference | 64/64 | 64/64 |
| Eight long prompts vs their no-speculation answers | 8/8 | 8/8 |
| Long prompts, decode after the first token (median) | 89.9 tok/s | 89.7 tok/s |

- **Exact and free:** every gate identical, and the one extra wait per step the engine needs costs nothing
  measurable (0.3 %).
- **No gain:** a copy draft was placed on 3.1 % of steps. Where it was, 2.97 of 5 tokens were accepted against 1.96
  for the built-in head overall. Per prompt the decode rate did not move (for example 138.7 vs 138.3, 48.3 vs 47.5).
- **Why the model was wrong:** it charged every non-copy step at the lane's average of about 3 tokens. On text that
  can be copied, the built-in head already predicts the copy and is accepted up to its depth of 5; the long prompts
  run at up to 139 tok/s without any help. Copying five tokens only matches what the head already does there.
- **By the rule above (10 % on the long suite): not kept.** The overlay stays in the repo, off.

**What is left of the idea:** only drafts *longer* than the head's depth can beat it, and only when a copy is
available; a fixed deeper draft would slow every other step. That needs a per-step draft length, which the
scheduler has a field for (`num_spec_tokens_to_schedule`). Size it from the control run's real steps per request
before building.


## Longer copy drafts, sized from the real run (17:20 EDT)

Conservative count on the eight long prompts, using the control run's real steps per request and crediting a copy
draft only with the tokens it would get accepted **beyond** the head's five:

| Copy draft length (only when a match of 6+ exists) | Steps saved | Gain on this suite, before the cost of a longer verify |
|---|---:|---:|
| 8 | 19 of 182 | +11.5 % |
| 16 | 38 of 182 | +26 % |
| 32 | 39 of 182 | +27 % |

Two of the eight prompts already run at the head's cap (5.33 tokens a step, 139 tok/s); on those a 16-token copy
would more than double the rate. Short prompts would not change.

A longer verify is not free (with speculation off, 16 rows cost about 13 ms more than one), so the draft must be
long **only on steps where a copy exists**. The synchronous step pipeline hands the scheduler each request's draft
as a list every step, which is where a per-step length is natural. First measurement, before any build: what the
synchronous pipeline costs one user on the shipped recipe (`MU_MODE=syncprobe`). If it is within 2 %, build the
variable-length draft there; if it costs more, the per-step length has to be done in the asynchronous pipeline.

## The synchronous pipeline costs 2.3 % (17:55 EDT)

`MU_MODE=syncprobe`, shipped recipe, one user, strict suite twice per server: asynchronous (the default) against
`--no-async-scheduling`. Both 12/12 exact. See the campaign log for the two pairs of numbers; the synchronous
server ran at 88.2 tok/s. That is just over the 2 % line, so it is not a free switch for the published recipe.

**Decision.** Build the longer copy drafts in the synchronous pipeline first, because that is where a per-step
draft length already exists and the real gain can be measured quickly. If long prompts gain what the sizing says,
the result is a long-context profile that is faster there and 2.3 % slower on short prompts; the port to the
asynchronous pipeline (longer drafts while a copy run is under way, decided one step ahead) follows only if the
gain is real. A 17-row verify also needs the speculative recurrent kernel censused for that row count; the
September census script does not run on this image and has to be repaired first.

## Longer copy drafts: built (18:30 EDT), first arm preregistered

Built by reading the engine (helper agent), 27 CPU tests pass. How it works: the server is launched with more verify
slots than the head's depth (`num_speculative_tokens` = K) and the stock per-batch-size schedule keeps the head at 5
passes; in the synchronous pipeline the overlay lengthens a request's draft list to as many copied tokens as follow
the match (6 to K). Requests without a copy keep the 5-token draft and the 6-row verify.

**What the launch itself changes, even on steps with no copy** (so the control arm uses the same launch):
the recurrent layers reserve K+1 state slots and a wider convolution state per request, and from K = 10 the
attention block size moves from 832 to 896 tokens. K = 16 would also reach a different kernel for one recurrent
projection at 17 rows. **First arm: K = 9**, which keeps the block size, stays under that switch, and stays inside
state widths this lane has run before. Sized at about +11 % on the long suite.

**Test.** `MU_MODE=copydraft MU_COPY_K=9`: two fresh two-card servers, same launch (synchronous, 9 slots, head at 5),
one with long copy drafts and one without. Each: strict suite, the eight long prompts, the short ladder.

**Rule.** Both arms must be 12/12, 8/8 and 64/64 against the frozen references. Then the long-suite decode rate of
the copy arm against (a) its control and (b) the shipped asynchronous recipe (89.9 tok/s median on this suite).
Kept only if it beats the shipped recipe on the long suite by 5 % or more; the strict-suite cost of this launch is
reported beside it. An exact result here is exact by test; the by-construction claim for 7 to 10-row verifies also
needs the repaired speculative-kernel census (in progress).

## Longer copy drafts, fixed: exact on two fresh servers, +10 to +17 % on long prompts (21:00 EDT)

**Why the first K = 9 run gave wrong answers (found by reading the engine and the saved token streams).** After a
step accepts `a` tokens, the next step's recurrent layers read their starting state from column `a - 1` of a
state-slot table that is only as wide as that next step (`gdn_attn.py` builds it `[1, rows]`; the kernel indexes it
without a bound check). With the shipped depth `a` is at most 6 and the next step has 6 rows, so it never happens;
with a long copy draft `a` can be 7 to 10 while the next step has 6 rows, and the read lands past the end. All 12
wrong answers in the three suites follow a step that accepted six or more drafts and was followed by a narrower
step; answers with long acceptances not followed by a narrower step were exact. The same out-of-range read exists
in the stock engine at the very end of the context window (found once before, 2026-09-13, "R307 defect 1").

**Fix in the overlay:** after a long acceptance the next draft is padded (its last token repeated) so the step is at
least as wide as the tokens just accepted. Pad tokens are verified like any draft, so they cannot change output.
Plus `B70_FA_VERIFY_ROWS_MAX_Q=10`, so attention handles 9 and 10 verify rows with long keys one row at a time,
as it already does for 2 to 8.

**Result on image R313, two fresh two-card servers, same launch as before (synchronous, 9 slots, head at 5):**

| Gate | Server 1 | Server 2 | Control (no long drafts) | Shipped recipe (async, R313) |
|---|---|---|---|---|
| Strict suite vs frozen reference | 12/12 | 12/12, 87.30 tok/s | 12/12, 88.25 | 12/12, 90.31 |
| Long prompts vs no-speculation answers | 8/8 | 8/8 | 8/8 | 8/8 |
| Short ladder vs frozen reference | 64/64 | 64/64 | 64/64 | 64/64 |
| Long prompts, decode after first token: median / mean | 98.5 / 105.7 tok/s | 98.6 / 105.8 | 87.5 / 88.5 | 89.9 / 90.7 |

About 245 long drafts placed per server, 4.06 of 9 accepted on average, 47 width pads, none blocked.
Per prompt against the shipped recipe: prose4k 139.6 -> 195, docs4k 138.7 -> 164, docs6k 117.4 -> 149, docs8k 88.5
-> 98.6; prose2k, code2k and the two that answer in two tokens unchanged.

**By the rule (5 % over the shipped recipe on the long suite, every gate exact): kept, as a long-context
candidate.** Median +9.6 %, mean +16.5 % over the shipped recipe on long prompts; the price is 3.3 % on short
prompts (the synchronous pipeline and the wider launch). Not yet a package profile.

**Still owed before "exact by construction" can be said of it (and of the shipped depth-5 verify):** a census of
the attention kernel for 2 to 10 verify rows at contexts up to 1,536 tokens against one row at a time, and of the
recurrent layers' small FP16 projection for 1 to 16 rows. The recurrent kernel (R313 census), the main layers, the
normalisation and the output layer are covered.

**Next for this lever:** more slots (K = 16 changes the attention block size and one projection path, so it needs
the same gates), and moving it to the asynchronous pipeline to get the 2.3 % back.

