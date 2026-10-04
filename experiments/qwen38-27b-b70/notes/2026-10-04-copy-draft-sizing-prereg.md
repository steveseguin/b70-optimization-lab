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
