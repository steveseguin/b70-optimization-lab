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
