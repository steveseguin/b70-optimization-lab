# Multi-user preregistration: how many users at once still get exactly their solo answers (2026-10-04)

Written before the run. Runner:
[`../scripts/run-20261004-fp8-multiuser-campaign.py`](../scripts/run-20261004-fp8-multiuser-campaign.py).

## Why this, and why now

The single-user recipes are within a few percent of what the hardware allows
([sizing](2026-10-03-fp8-comm5b-result.md#where-the-27bs-remaining-speed-could-come-from-sized-added-2026-10-04)).
What has never been measured on the 27B FP8 is more than one user at a time; both package READMEs list it as
untested, and the one earlier screen (one card, two users, September 16) found speculation not output-identical at
two users.

Decoding here is limited by reading the weights from memory, not by arithmetic. A step that serves eight users
reads the same weights once. So total tokens per second should rise almost in step with the number of users, as
long as every user's answer stays exactly what they would have got alone. That last condition is the whole point:
a multi-user number counts only where it is lossless.

## What is measured

Two cards, the shipped image, 64 prompts, 128-token answers, each request once per pass, cache off.

| Stage | Server | Users at once |
| --- | --- | --- |
| `tp2-mtp0-s8` | no speculation, accepts 8 sequences | 1 (the oracle), then 2, 4, 8, twice each |
| `tp2-mtp5-s4` | shipped depth-5 speculation, accepts 4 sequences | 1 (the oracle), then 2, 4, twice each |

For every pass: how many of the 64 answers are token-for-token identical to the same request run alone on the same
server, and the total generated tokens divided by the pass's wall time.

## The rule

- A user count is **lossless** only if all 64 answers are identical to their solo answers in **both** passes.
- The result reported is the highest lossless user count and its total speed, per stage. A level with even one
  different answer is reported as not lossless, with the count.
- Speed is recorded, never a gate. Nothing is shipped or published from this run by itself: a multi-user profile
  would need its own acceptance through the package launcher.
- No server before or after, each server started once and stopped gracefully, no retry. A GPU fault line halts the
  run.

## Expectation, stated in advance

Without speculation, exact at 2, 4 and 8 users, with totals well above the single-user 34 tok/s and plausibly
above the single-user speculative 90 tok/s at eight users. With speculation, not exact at 2 users (as on one card in
September). If the no-speculation totals are large, the follow-up question is whether speculation can be made exact
under load; that is a separate campaign.

## Addendum, 01:30 EDT: the first pass was only a screen; the gate is rerun with 64 answers per level

The first run (`/mnt/fast-ai/bench-results/fp8-multiuser-20261004`) sent only as many requests as there were users,
so "exact" there means 2 of 2, 4 of 4 and 8 of 8 answers. That is a look, not a gate. What it showed, both passes:
without speculation 65 / 125 / 234 tok/s together at 2 / 4 / 8 users; with depth-5 speculation 229 tok/s together
at 4 users; every answer in that small sample equal to its solo answer.

The gate run (`MU_MODE=gate`) sends all 64 prompts at once to a server that runs N of them together, twice, and
compares every answer both with the same server's one-at-a-time answers and with the frozen single-user
no-speculation reference (`fp8-comm2-20260917/tp2-ag-mtp0-ladder.json`). Servers: no speculation at 8; depth-5
speculation at 2, 4 and 8. The rule above is unchanged: a level is lossless only if all 64 answers are identical in
both passes.
