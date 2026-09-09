# The two-card divergences are a dozen fixed tie sites, not a diffuse effect

Read entirely out of ladder files already on disk - no cards, no new runs. The four powered arms
recorded complete token arrays for every request and for the sequential oracle, which is enough to
ask not just how often requests diverge but *where* and *into what*.

## What the 25 divergences actually are

Across the four arms, 25 divergent requests resolve to **12 distinct sites**, where a site is a
(prompt, token position, substitution) triple:

| prompt | token | substitution | times seen |
| --- | ---: | --- | ---: |
| `monitoring-c044` | 90 | `466 -> 5787` | 5 |
| `index-c041` | 77 | `10993 -> 24816` | 4 |
| `monitoring-c020` | 90 | `466 -> 5787` | 3 |
| `monitoring-c004` | 116 | `16484 -> 67205` | 2 |
| `benchmark-c011` | 12 | `3820 -> 3050` | 2 |
| `monitoring-c036` | 90 | `466 -> 5787` | 2 |
| `rollback-c042` | 38 | `16070 -> 24141` | 2 |
| six more | - | - | 1 each |

Three properties, all of them useful:

**A site always flips the same way.** Every occurrence of `monitoring-c044` diverging is the same
token at the same position becoming the same other token. Never a third candidate, never a different
position. That is what an exact two-way tie looks like: the two candidates are equal and the
tie-break goes one way or the other.

**Sites are shared across prompts.** Three different prompts - `monitoring-c044`, `-c020` and
`-c036` - flip `466 -> 5787` at position 90. They are variants of the same prompt family that have
converged to the same state by that point, so they are really one tie being hit three times.

**Nothing is a single-token substitution.** All 25 diverge for the rest of the completion once they
flip, which is expected: the continuation is conditioned on the changed token.

## Why this changes the experiment design

The powered arms accumulate events at about 0.7% of requests, which is why 20 passes of 64 users
yields only 9 control events and why nothing reached significance. But the rate is not uniform: it is
near zero on most prompts and around 6% on a handful. `monitoring-c044` appeared 80 times across the
four arms and flipped 5 times.

So the same statistics can be gathered far faster by filling the batch with the fragile prompts
instead of the whole suite. Sixty-four concurrent copies of a 6% site yields roughly four events per
pass against the current 0.45 - close to an order of magnitude, for the same card time. An experiment
that currently needs 60-80 passes per arm to separate the interventions would need under ten.

That is worth doing before any more full-suite ladders. It also makes a sharper question available:
the per-site flip probability is a real quantity that converges quickly, and comparing it across
interventions is a much finer instrument than counting whole-suite divergences.

## What it does not settle

It says nothing about which mechanism perturbs these sites. Both the norm and the collective are
shape-dependent, and either could move a tied logit. Answering that still needs the logits - the
ladder requests them with `logprob_content` but the field came back empty in these runs, so a
targeted run would need logprobs enabled to read the margin at the flipped token.

Evidence: `data/2026-09-08-divergence-positions.json`; analyser
`scripts/analyze-divergence-positions.py`.

---

## Correction (2026-09-09): the largest site is an insertion, not a substitution

The `466 -> 5787` reading above comes from comparing position by position, which
cannot distinguish a substitution from an inserted token. Alignment-based
re-analysis of every ladder on disk shows all 1295 occurrences of that site have
the same structure: the run emits `5787` at position 90 — the token the oracle
emits at position 95 — then emits `466`, the oracle's position-90 token, and
diverges from 92. The model does not choose between 466 and 5787; it emits one
five positions early and then the other. "A site always flips the same way" holds;
"that is what an exact two-way tie looks like" does not, for this site.

`rollback-c042` @38 and `index-c041` @77 do classify as substitutions in every
occurrence, so the tie reading stands for them. Across 2532 divergences in the 9B
and 4B ladders the split is 51% early-emission insertion, 46% substitution.

See `experiments/qwen35-4b-b70/notes/2026-09-09-divergence-classification-retrospective.md`.
